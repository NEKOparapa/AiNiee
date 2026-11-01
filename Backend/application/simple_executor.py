"""Synchronous small task services with explicit cancellation and result callbacks."""
import copy
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from Backend.application.execution_context import ExecutionContext
from Backend.core.log import LogMixin
from Backend.infrastructure.llm.llm_requester import LLMRequester
from Backend.domain.config.task_config import TaskConfig
from Backend.domain.languages import get_source_language_for_file
from Backend.domain.responses.response_extractor import ResponseExtractor
from Backend.domain.responses.response_checker import ResponseChecker
from Backend.domain.prompts.prompt_builder import PromptBuilder
from Backend.domain.prompts.prompt_builder_polishing import PromptBuilderPolishing
from Backend.domain.prompts.glossary_helper import GlossaryHelper
from Backend.domain.models.cache_item import TranslationStatus


class SimpleExecutor(LogMixin):
    @staticmethod
    def _configuration(role):
        return TaskConfig.from_snapshot(TaskConfig.read_snapshot(), interface_role=role)

    def _run_batches(self, batches, worker, config, context, operation, accept=None):
        """Keep at most one request per worker in flight; drain successful results on stop."""
        results, errors = [], []
        failed = processed = 0
        callbacks_enabled = True
        futures, handled = set(), set()
        executor = None

        def collect(future):
            nonlocal failed, processed, callbacks_enabled
            if future in handled or future.cancelled():
                return
            handled.add(future)
            try:
                result = future.result()
            except Exception as error:
                self.error(f"批次执行异常: {error}")
                result = None
            processed += 1
            if result is not None:
                results.append(result)
            elif not context.is_cancelled():
                failed += 1
            if callbacks_enabled:
                try:
                    if result is not None and accept:
                        accept(result)
                    if context.on_progress:
                        context.on_progress({
                            "operation": operation, "current": processed, "total": len(batches),
                            "success_batches": len(results), "failed_batches": failed,
                        })
                except Exception as error:
                    errors.append(str(error))
                    context.cancel()
                    callbacks_enabled = False

        try:
            max_workers = max(1, int(config.actual_thread_counts))
            executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=operation)
            next_index, pending = 0, set()
            while pending or (next_index < len(batches) and not context.is_cancelled()):
                while next_index < len(batches) and len(pending) < max_workers and not context.is_cancelled():
                    future = executor.submit(worker, next_index, batches[next_index])
                    pending.add(future)
                    futures.add(future)
                    next_index += 1
                if not pending:
                    break
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    collect(future)
        except Exception as error:
            errors.append(str(error))
            context.cancel()
            callbacks_enabled = False
        finally:
            if executor:
                executor.shutdown(wait=True, cancel_futures=context.is_cancelled())
                for future in futures:
                    collect(future)
        return results, failed, errors

    def api_test(self, data: dict, context=None) -> dict:
        context = context or ExecutionContext()
        result = {"failure": [], "success": []}
        try:
            self._api_test(data or {}, context, result)
            result["status"] = "cancelled" if context.is_cancelled() else "success"
        except Exception as error:
            self.error(f"接口测试失败: {error}")
            result.update(status="error", message=str(error))
        return result

    # 接口测试
    def _api_test(self, data: dict, context: ExecutionContext, result: dict):
        # 获取参数
        platform_tag = data.get("tag")
        platform_name = data.get("name")
        api_url = data.get("api_url", "")
        api_key = data.get("api_key")
        api_format = data.get("api_format", "")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        extra_body = data.get("extra_body", {})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")

        # 处理 API 地址
        if api_url:
            # 基础清洗
            api_url = api_url.strip().rstrip('/')

            # 裁剪冗余后缀
            redundant_suffixes = ["/chat/completions", "/completions", "/chat"]
            for suffix in redundant_suffixes:
                if api_url.endswith(suffix):
                    api_url = api_url[:-len(suffix)].rstrip('/')
                    break

            # 判断是否为 Anthropic 格式
            is_anthropic = (
                    platform_tag == "anthropic"
                    or api_format.lower() == "anthropic"
            )

            # 版本号后缀列表
            version_suffixes = ["/v1", "/v2", "/v3", "/v4", "/v5", "/v6"]

            # Anthropic 格式特殊处理：SDK 会自动拼接 /v1/messages，需要去掉用户输入的版本号
            if is_anthropic and auto_complete:
                for suffix in version_suffixes:
                    if api_url.endswith(suffix):
                        api_url = api_url[:-len(suffix)].rstrip('/')
                        break
            # 非 Anthropic 的自动补全 /v1 逻辑
            elif (platform_tag in ["sakura", "LocalLLM"]) or auto_complete:
                if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                    api_url += "/v1"

        # 测试结果
        failure = result["failure"]
        success = result["success"]

        # 解析并分割密钥字符串
        api_keys = re.sub(r"\s+", "", str(api_key or "")).split(",")

        # 轮询所有密钥进行测试
        for api_key in api_keys:
            if context.is_cancelled():
                break

            # 构建 Prompt
            messages = [
                {
                    "role": "user",
                    "content": "小可爱，你在干嘛"
                }
            ]
            system_prompt = "你接下来要扮演我的女朋友，名字叫欣雨，请你以女朋友的方式回复我。"

            # 打印日志
            self.print("")
            self.info("正在进行接口测试 ...")
            self.info(f"接口名称 - {platform_name}")
            self.info(f"接口地址 - {api_url}")
            self.info(f"接口密钥 - {'*'*(len(api_key)-8)}{api_key[-8:]}") # 隐藏敏感信息
            self.info(f"模型名称 - {model_name}")
            self.info(f"tls_switch - {data.get('tls_switch', False)}")
            if extra_body:
                self.info(f"额外参数 - {extra_body}")
            self.print(f"系统提示词 - {system_prompt}")
            self.print(f"信息内容 - {messages}")

            # 构建配置包
            platform_config = {
                "is_cancelled": context.is_cancelled,
                "target_platform": platform_tag,
                "api_url": api_url,
                "api_key": api_key,
                "api_format": api_format,
                "model_name": model_name,
                "region":  region,
                "access_key":  access_key,
                "secret_key": secret_key,
                "extra_body": extra_body,
                "extra_headers": data.get("extra_headers", {}),
                "tls_switch": data.get("tls_switch", False),
                "think_switch": data.get("think_switch"),
                "think_depth": data.get("think_depth"),
                "thinking_level": data.get("thinking_level"),
                "temperature": data.get("temperature"),
            }

            # 尝试请求前再次检查，避免日志/准备期间取消后仍发出请求。
            if context.is_cancelled():
                break
            requester = LLMRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
                messages,
                system_prompt,
                platform_config
            )

            # 测试成功
            if skip == False:
                self.info("接口测试成功 ...")
                self.info(f"接口返回信息 - {response_content}")
                # 储存结果
                success.append(api_key)

            # 测试失败
            else:
                self.error(f"接口测试失败 ... ")
                # 储存结果
                failure.append(api_key)

            self.print("")

        # 打印结果
        self.print("")
        self.info(f"接口测试结果：共测试 {len(api_keys)} 个接口，成功 {len(success)} 个，失败 {len(failure)} 个 ...")
        if len(failure) >0:
            self.error(f"失败的接口密钥 - {", ".join(failure)}")
        self.print("")

        return result

    def glossary_translation(self, data: dict, context=None) -> dict:
        data = data or {}
        context = context or ExecutionContext()
        result = {"status": "error", "updated_data": None}
        try:
            result = self._translate_glossary(data, context)
        except Exception as error:
            self.error(f"术语表翻译失败: {error}")
            result["message"] = str(error)
        return {**result, "table_id": data.get("table_id"), "request_id": data.get("request_id")}

    def _translate_glossary(self, data: dict, context: ExecutionContext) -> dict:
        prompt_dictionary_data = data.get("prompt_dictionary_data")
        if not prompt_dictionary_data:
            return {"status": "null", "updated_data": prompt_dictionary_data}
        untranslated_items = [
            item for item in prompt_dictionary_data
            if isinstance(item, dict) and not item.get("dst") and GlossaryHelper.is_row_valid(item)
        ]
        if not untranslated_items:
            return {"status": "null", "updated_data": copy.deepcopy(prompt_dictionary_data)}
        if context.is_cancelled():
            return {"status": "cancelled", "updated_data": None, "success_count": 0,
                    "total_count": len(untranslated_items)}
        config = self._configuration("translate")
        target_language = config.target_language
        groups = [untranslated_items[i:i + 50] for i in range(0, len(untranslated_items), 50)]
        total_groups = len(groups)

        def translate_group(group_idx: int, current_group: list) -> tuple:
            """处理单组翻译，成功返回 (group_idx, [(src, dst), ...])，失败返回 (group_idx, None)。"""
            group_num = group_idx + 1
            if context.is_cancelled():
                return None
            try:
                platform_config = config.get_active_platform_configuration()
                platform_config["is_cancelled"] = context.is_cancelled
                has_info = any(item.get("info") for item in current_group)
                system_prompt = (
                    "You are a glossary translation assistant.The user will send a glossary in this format:\n"
                    "1|Original text|Description\n"
                    "2|Original text|Description\n"
                    "3|Original text|Description\n"
                    f"Referring to the 'Description', only translate the 'Original text' into {target_language}. Strictly output the translation in the following format, wrapped in a <textarea> tag:\n"
                    "<textarea>\n"
                    "1.Translated text\n"
                    "2.Translated text\n"
                    "3.Translated text\n"
                    "</textarea>\n"
                ) if has_info else (
                    f"Translate the source text from the glossary into {target_language} line by line, maintaining accuracy and naturalness, and output the translation wrapped in a textarea tag:\n"
                    "<textarea>\n"
                    f"1.{target_language} text\n"
                    "</textarea>\n"
                )
                if has_info:
                    src_terms = [f"{idx+1}|{item['src']}|{item.get('info') or ''}" for idx, item in enumerate(current_group)]
                else:
                    src_terms = [f"{idx+1}.{item['src']}" for idx, item in enumerate(current_group)]
                src_terms_text = "\n".join(src_terms)
                messages = [{"role": "user", "content": src_terms_text}]
                if context.is_cancelled():
                    return None
                requester = LLMRequester()
                skip, _, response_content, _, _ = requester.sent_request(
                    messages, system_prompt, platform_config
                )
                if skip:
                    self.error(f"第 {group_num}/{total_groups} 组翻译请求失败")
                    return None
                textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', response_content, re.DOTALL)
                last_content = textarea_contents[-1]
                translated_terms = last_content.strip().split("\n")
                translated_terms = [re.sub(r'^\d+\.', '', term).strip() for term in translated_terms]
                if len(translated_terms) != len(current_group):
                    self.error(f"第 {group_num}/{total_groups} 组翻译结果数量不匹配")
                    return None
                pairs = [(item["src"], translated_terms[idx]) for idx, item in enumerate(current_group)]
                return pairs
            except Exception as e:
                self.error(f"第 {group_num}/{total_groups} 组异常: {e}")
                return None

        results, failed_groups, errors = self._run_batches(
            groups, translate_group, config, context, "glossary",
        )
        successful_pairs = [pair for pairs in results for pair in pairs]
        updated_data = None
        if successful_pairs:
            src_to_dst = dict(successful_pairs)
            updated_data = copy.deepcopy(prompt_dictionary_data)
            for item in updated_data:
                if isinstance(item, dict) and item.get("src") in src_to_dst and not item.get("dst"):
                    item["dst"] = src_to_dst[item["src"]]
        if errors:
            status = "partial" if successful_pairs else "error"
        elif context.is_cancelled():
            status = "cancelled"
        elif len(successful_pairs) == len(untranslated_items):
            status = "success"
        else:
            status = "partial" if successful_pairs else "error"
        return {
            "status": status, "updated_data": updated_data,
            "success_count": len(successful_pairs), "total_count": len(untranslated_items),
            "success_groups": len(results), "failed_groups": failed_groups,
            "operation_errors": errors,
            "message": "; ".join(errors) if errors else ("所有组翻译均未成功" if status == "error" else ""),
        }

    def process_table_translation(self, data: dict, context=None) -> dict:
        return self._process_table_jobs(data, context or ExecutionContext(), "translate")

    def process_table_polish(self, data: dict, context=None) -> dict:
        return self._process_table_jobs(data, context or ExecutionContext(), "polish")

    def _process_table_jobs(self, data, context, operation):
        data = data or {}
        jobs = data.get(f"{operation}_jobs")
        if not isinstance(jobs, list):
            return self._process_table(data, context, operation)
        results, errors, updates_by_file = [], [], {}
        item_field = "items_to_translate" if operation == "translate" else "items_to_polish"
        try:
            config = self._configuration(operation) if jobs and not context.is_cancelled() else None
            for job in jobs:
                if context.is_cancelled():
                    break
                request = {**data, **job, item_field: job.get(item_field, job.get("selected_items", []))}
                result = self._process_table(request, context, operation, config=config)
                results.append(result)
                errors.extend(result.get("operation_errors", []))
                if result.get("updated_items"):
                    updates_by_file.setdefault(result["file_path"], {}).update(result["updated_items"])
                if result.get("operation_errors"):
                    context.cancel()
                    break
        except Exception as error:
            errors.append(str(error))
        count = sum(len(items) for items in updates_by_file.values())
        if errors:
            status = "partial" if count else "error"
        elif context.is_cancelled():
            status = "cancelled"
        else:
            status = "success" if count else "empty"
        return {
            "operation": operation, "status": status, "view": data.get("view"),
            "updates_by_file": updates_by_file, "file_paths": list(updates_by_file),
            "updated_file_count": len(updates_by_file), "updated_item_count": count,
            "success_batches": sum(result["success_batches"] for result in results),
            "failed_batches": sum(result["failed_batches"] for result in results),
            "total_items": sum(len(job.get(item_field, job.get("selected_items", [])) or []) for job in jobs if isinstance(job, dict)),
            "translation_status": TranslationStatus.TRANSLATED if operation == "translate" else TranslationStatus.POLISHED,
            "operation_errors": errors, "message": "; ".join(errors),
        }

    def _process_table(self, data, context, operation, config=None):
        data = data or {}
        file_path = data.get("file_path")
        items = data.get("items_to_translate" if operation == "translate" else "items_to_polish") or []
        updated_items, errors = {}, []
        success_batches = failed_batches = 0
        translation_status = TranslationStatus.TRANSLATED if operation == "translate" else TranslationStatus.POLISHED
        try:
            if items and not context.is_cancelled():
                config = config or self._configuration(operation)
                source_language = get_source_language_for_file(
                    config.source_language, config.target_language, data.get("language_stats"),
                ) if operation == "translate" else None
                batches = [items[i:i + 20] for i in range(0, len(items), 20)]

                def worker(batch_idx, batch_items):
                    if context.is_cancelled():
                        return None
                    platform_config = config.get_active_platform_configuration()
                    platform_config["is_cancelled"] = context.is_cancelled
                    source = {str(i): item["source_text"] for i, item in enumerate(batch_items)}
                    index_map = [item["text_index"] for item in batch_items]
                    if operation == "translate":
                        reference = source
                        messages, system_prompt, _ = PromptBuilder.generate_prompt(config, source, [], source_language)
                    else:
                        reference = {str(i): item["translation_text"] for i, item in enumerate(batch_items)}
                        messages, system_prompt, _ = PromptBuilderPolishing.generate_prompt(config, source, reference)
                    if context.is_cancelled():
                        return None
                    skip, _, response_content, _, _ = LLMRequester().sent_request(messages, system_prompt, platform_config)
                    if skip:
                        return None
                    response = ResponseExtractor.text_extraction(self, reference, response_content)
                    checked, _ = ResponseChecker.check_polish_response_content(self, config, response_content, response, reference)
                    if not checked:
                        return None
                    restored = {index_map[int(index)]: text for index, text in response.items()}
                    result = ResponseExtractor.remove_numbered_prefix(self, restored)
                    return result or None

                def accept(result):
                    if context.on_result:
                        context.on_result({
                            "file_path": file_path, "target_column_index": 2,
                            "translation_status": translation_status, "updated_items": dict(result),
                        })

                results, failed_batches, errors = self._run_batches(
                    batches, worker, config, context, operation, accept,
                )
                success_batches = len(results)
                for result in results:
                    updated_items.update(result)
        except Exception as error:
            errors.append(str(error))
            self.error(f"表格{operation}任务失败: {error}")
        if errors:
            status = "partial" if updated_items else "error"
        elif context.is_cancelled():
            status = "cancelled"
        else:
            status = "success" if updated_items else "empty"
        return {
            "operation": operation, "status": status, "file_path": file_path,
            "updated_item_count": len(updated_items), "success_batches": success_batches,
            "failed_batches": failed_batches, "total_items": len(items),
            "updated_items": updated_items, "translation_status": translation_status,
            "operation_errors": errors, "message": "; ".join(errors),
        }
