import copy
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Service.TaskExecutor.TranslatorUtil import get_source_language_for_file
from ModuleFolders.Domain.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.Domain.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus

# 简易请求器
class SimpleExecutor(ConfigMixin, LogMixin, Base):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 订阅接口测试开始事件
        self.subscribe(Base.EVENT.API_TEST_START, self.api_test_start)
        # 订阅术语表翻译开始事件
        self.subscribe(Base.EVENT.GLOSS_TASK_START, self.glossary_translation_start)
        # 订阅表格翻译任务事件
        self.subscribe(Base.EVENT.TABLE_TRANSLATE_START, self.handle_table_translation_start)
        # 订阅表格润色任务事件
        self.subscribe(Base.EVENT.TABLE_POLISH_START, self.handle_table_polish_start)

    # 响应接口测试开始事件
    def api_test_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.api_test, args = (event, data))
        thread.start()

    # 接口测试
    def api_test(self, event, data: dict):
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
        failure = []
        success = []

        # 解析并分割密钥字符串
        api_keys = re.sub(r"\s+","", api_key).split(",")

        # 轮询所有密钥进行测试
        for api_key in api_keys:

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
                "target_platform": platform_tag,
                "api_url": api_url,
                "api_key": api_key,
                "api_format": api_format,
                "model_name": model_name,
                "region":  region,
                "access_key":  access_key,
                "secret_key": secret_key,
                "extra_body": extra_body,
                "tls_switch": data.get("tls_switch", False),
                "think_switch": data.get("think_switch"),
                "think_depth": data.get("think_depth"),
                "thinking_level": data.get("thinking_level"),
                "temperature": data.get("temperature"),
            }

            #尝试请求
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

        # 发送完成事件
        self.emit(Base.EVENT.API_TEST_DONE, {
            "failure": failure,
            "success": success,
        })

    # 响应术语表的简单翻译开始事件
    def glossary_translation_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.glossary_translation, args = (event, data))
        thread.start()

    # 术语表的简单翻译
    def glossary_translation(self, event, data: dict):

        # 获取表格数据
        prompt_dictionary_data = data.get("prompt_dictionary_data")
        if not prompt_dictionary_data:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 获取未翻译术语，错误项只保留在表格，不进入翻译任务。
        untranslated_items = [
            item for item in prompt_dictionary_data
            if not item.get("dst") and GlossaryHelper.is_row_valid(item)
        ]
        if not untranslated_items:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 准备翻译配置
        config = TaskConfig()
        config.initialize("translate")
        config.prepare_for_active_platform("translate")
        target_language = config.target_language
        max_threads = config.actual_thread_counts

        # 分组处理（每组最多50个）
        group_size = 50
        total_groups = (len(untranslated_items) + group_size - 1) // group_size

        # 输出整体进度信息
        print("")
        self.info(f" 开始术语表循环翻译 \n"
                f"├ 未翻译术语总数: {len(untranslated_items)}\n"
                f"├ 分组数量: {total_groups}\n"
                f"├ 每组上限: {group_size}术语\n"
                f"└ 并发线程数: {max_threads}")
        print("")

        def translate_group(group_idx: int, current_group: list) -> tuple:
            """处理单组翻译，成功返回 (group_idx, [(src, dst), ...])，失败返回 (group_idx, None)。"""
            group_num = group_idx + 1
            try:
                platform_config = config.get_active_platform_configuration()
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
                    src_terms = [f"{idx+1}|{item['src']}|{item['info']or''}" for idx, item in enumerate(current_group)]
                else:
                    src_terms = [f"{idx+1}.{item['src']}" for idx, item in enumerate(current_group)]
                src_terms_text = "\n".join(src_terms)
                messages = [{"role": "user", "content": src_terms_text}]
                requester = LLMRequester()
                skip, _, response_content, _, _ = requester.sent_request(
                    messages, system_prompt, platform_config
                )
                if skip:
                    self.error(f"第 {group_num}/{total_groups} 组翻译请求失败")
                    return (group_idx, None)
                textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', response_content, re.DOTALL)
                last_content = textarea_contents[-1]
                translated_terms = last_content.strip().split("\n")
                translated_terms = [re.sub(r'^\d+\.', '', term).strip() for term in translated_terms]
                if len(translated_terms) != len(current_group):
                    self.error(f"第 {group_num}/{total_groups} 组翻译结果数量不匹配")
                    return (group_idx, None)
                pairs = [(item["src"], translated_terms[idx]) for idx, item in enumerate(current_group)]
                return (group_idx, pairs)
            except Exception as e:
                self.error(f"第 {group_num}/{total_groups} 组异常: {e}")
                return (group_idx, None)

        successful_pairs = []
        success_groups = 0
        failed_groups = 0

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_group = {}
            for i in range(total_groups):
                start_idx = i * group_size
                end_idx = start_idx + group_size
                current_group = untranslated_items[start_idx:end_idx]
                future = executor.submit(translate_group, i, current_group)
                future_to_group[future] = i
            for future in as_completed(future_to_group):
                try:
                    group_idx, pairs = future.result()
                    if pairs is not None:
                        successful_pairs.extend(pairs)
                        success_groups += 1
                    else:
                        failed_groups += 1
                except Exception as e:
                    self.error(f"术语表组执行异常: {e}")
                    failed_groups += 1

        self.info(f" 所有组处理完毕。成功: {success_groups}, 失败: {failed_groups}")

        if not successful_pairs:
            self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                "status": "error",
                "message": "所有组翻译均未成功",
                "updated_data": None
            })
            return

        # 合并成功结果到完整数据
        src_to_dst = dict(successful_pairs)
        updated_data = copy.deepcopy(prompt_dictionary_data)
        for item in updated_data:
            if item.get("src") in src_to_dst and not item.get("dst"):
                item["dst"] = src_to_dst[item["src"]]

        if len(successful_pairs) == len(untranslated_items):
            status = "success"
        else:
            status = "partial"

        self.info(f" 术语表翻译完成 \n"
                f"├ 成功术语: {len(successful_pairs)}/{len(untranslated_items)}\n"
                f"└ 状态: {status}")
        self.emit(Base.EVENT.GLOSS_TASK_DONE, {
            "status": status,
            "updated_data": updated_data,
            "success_count": len(successful_pairs),
            "total_count": len(untranslated_items)
        })

    # 响应表格翻译开始事件，并启动新线程
    def handle_table_translation_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_table_translation, args=(data,), daemon=True)
        thread.start()

    # 表格文本的分批翻译
    def process_table_translation(self, data: dict):
        """处理表格文件的批量翻译任务"""
        # 解包从UI传来的数据
        file_path = data.get("file_path")
        items_to_translate = data.get("items_to_translate")
        language_stats = data.get("language_stats")
        update_event = data.get("update_event", Base.EVENT.TABLE_BASIC_UPDATE)
        done_event = data.get("done_event")

        # 准备翻译配置
        config = TaskConfig()
        config.initialize("translate")
        config.prepare_for_active_platform("translate")
        max_threads = config.actual_thread_counts # 获取并发线程数
        
        # 预计算源语言
        file_source_lang = get_source_language_for_file(config.source_language, config.target_language, language_stats)

        # 翻译任务分割
        MAX_LINES = 20  
        total_items = len(items_to_translate)
        num_batches = (total_items + MAX_LINES - 1) // MAX_LINES

        self.info(f" 开始处理表格翻译任务: {os.path.basename(file_path)}")
        self.info(f"    总计 {total_items} 行文本, 将分为 {num_batches} 个批次处理。")
        self.info(f"    并发线程数: {max_threads} (结果将在任务完成后统一刷新)")

        # 用于汇总所有批次结果的字典
        final_updated_items = {}
        # 成功/失败计数
        success_batches = 0
        failed_batches = 0

        # 定义单个批次的工作函数
        def translate_worker(batch_idx, batch_items):
            batch_num = batch_idx + 1
            # 重新获取配置以支持Key轮询
            current_platform_config = config.get_active_platform_configuration()

            # 构建字典和索引
            source_text_dict = {str(idx): item['source_text'] for idx, item in enumerate(batch_items)}
            index_map = [item['text_index'] for item in batch_items]

            # 构建提示词
            messages, system_prompt, _ = PromptBuilder.generate_prompt(
                config, source_text_dict, [], file_source_lang
            )
            
            # 简单的进度日志
            print(f" -> [批次 {batch_num}] 正在发送请求 ({len(batch_items)}行)...")
            
            # 发送请求
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages, system_prompt, current_platform_config
            )

            if skip:
                print(f" <- [批次 {batch_num}] ❌ 请求失败")
                return None

            # 解析和校验
            response_dict = ResponseExtractor.text_extraction(self, source_text_dict, response_content)
            check_result, _ = ResponseChecker.check_polish_response_content(
                self, config, response_content, response_dict, source_text_dict
            )
            
            if not check_result:
                print(f" <- [批次 {batch_num}] ❌ 校验不通过")
                return None
            
            # 还原序号
            restored_response_dict = {
                index_map[int(temp_idx_str)]: text
                for temp_idx_str, text in response_dict.items()
            }

            # 移除前缀并返回
            updated_items = ResponseExtractor.remove_numbered_prefix(self, restored_response_dict)
            print(f" <- [批次 {batch_num}] ✅ 完成 (解析出 {len(updated_items)} 条)")
            return updated_items

        # 执行线程池
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_batch = {}
            # 提交任务
            for i in range(num_batches):
                start_index = i * MAX_LINES
                end_index = start_index + MAX_LINES
                batch_items = items_to_translate[start_index:end_index]
                
                future = executor.submit(translate_worker, i, batch_items)
                future_to_batch[future] = i

            # 处理结果（此处仅收集，不更新UI）
            for future in as_completed(future_to_batch):
                try:
                    result = future.result()
                    if result:
                        final_updated_items.update(result)
                        success_batches += 1
                    else:
                        failed_batches += 1
                except Exception as e:
                    self.error(f"批次执行异常: {e}")
                    failed_batches += 1

        self.info(f" 所有批次处理完毕。成功: {success_batches}, 失败: {failed_batches}")
        
        # 任务全部完成后，统一发送一次UI更新事件
        if final_updated_items:
            self.info(f" 正在将 {len(final_updated_items)} 条翻译结果写入表格...")
            self.emit(update_event, {
                "file_path": file_path,
                "target_column_index": 2, # 翻译列
                "translation_status": TranslationStatus.TRANSLATED,
                "updated_items": final_updated_items
            })
        else:
            self.warning(" 未获得任何有效翻译结果，表格未更新。")

        # 更新软件状态
        if done_event is not None:
            self.emit(done_event, {
                "operation": "translate",
                "status": "success" if final_updated_items else "empty",
                "file_path": file_path,
                "updated_item_count": len(final_updated_items),
                "success_batches": success_batches,
                "failed_batches": failed_batches,
                "total_items": total_items,
            })

        Base.work_status = Base.STATUS.IDLE 
        self.info(f" 🐳 表格翻译任务结束")                         

    # 响应表格润色事件
    def handle_table_polish_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_table_polish, args=(data,), daemon=True)
        thread.start()

    # 表格文本的分批润色
    def process_table_polish(self, data: dict):
        """处理表格文件的批量润色任务"""
        # 解包数据
        file_path = data.get("file_path")
        items_to_polish = data.get("items_to_polish")
        update_event = data.get("update_event", Base.EVENT.TABLE_BASIC_UPDATE)
        done_event = data.get("done_event")

        # 准备配置
        config = TaskConfig()
        config.initialize("polish")
        config.prepare_for_active_platform("polish")
        max_threads = config.actual_thread_counts

        # 任务分割
        MAX_LINES = 20
        total_items = len(items_to_polish)
        num_batches = (total_items + MAX_LINES - 1) // MAX_LINES

        self.info(f" 开始处理表格润色任务: {os.path.basename(file_path)}")
        self.info(f"    总计 {total_items} 行文本, 将分为 {num_batches} 个批次处理。")
        self.info(f"    并发线程数: {max_threads} (结果将在任务完成后统一刷新)")

        # 结果汇总字典
        final_updated_items = {}
        success_batches = 0
        failed_batches = 0

        # 定义工作函数
        def polish_worker(batch_idx, batch_items):
            batch_num = batch_idx + 1
            current_platform_config = config.get_active_platform_configuration()
            
            source_text_dict = {str(idx): item['source_text'] for idx, item in enumerate(batch_items)}
            translation_text_dict = {str(idx): item['translation_text'] for idx, item in enumerate(batch_items)}
            index_map = [item['text_index'] for item in batch_items]

            messages, system_prompt, _ = PromptBuilderPolishing.generate_prompt(
                config, source_text_dict, translation_text_dict, []
            )
            
            print(f" -> [批次 {batch_num}] 正在发送请求 ({len(batch_items)}行)...")
            
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages, system_prompt, current_platform_config
            )

            if skip:
                print(f" <- [批次 {batch_num}] ❌ 请求失败")
                return None

            # 确定校验基准
            text_dict = translation_text_dict

            # 解析校验
            response_dict = ResponseExtractor.text_extraction(self, text_dict, response_content)
            check_result, _ = ResponseChecker.check_polish_response_content(
                self, config, response_content, response_dict, text_dict
            )
            
            if not check_result:
                print(f" <- [批次 {batch_num}] ❌ 校验不通过")
                return None
            
            # 还原和清理
            restored_response_dict = {
                index_map[int(temp_idx_str)]: text
                for temp_idx_str, text in response_dict.items()
            }
            updated_items = ResponseExtractor.remove_numbered_prefix(self, restored_response_dict)
            print(f" <- [批次 {batch_num}] ✅ 完成 (解析出 {len(updated_items)} 条)")
            return updated_items

        # 执行线程池
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_batch = {}
            for i in range(num_batches):
                start_index = i * MAX_LINES
                end_index = start_index + MAX_LINES
                batch_items = items_to_polish[start_index:end_index]
                
                future = executor.submit(polish_worker, i, batch_items)
                future_to_batch[future] = i
            
            for future in as_completed(future_to_batch):
                try:
                    result = future.result()
                    if result:
                        final_updated_items.update(result)
                        success_batches += 1
                    else:
                        failed_batches += 1
                except Exception as e:
                    self.error(f"批次执行异常: {e}")
                    failed_batches += 1

        self.info(f" 所有批次处理完毕。成功: {success_batches}, 失败: {failed_batches}")

        # 统一发送 UI 更新
        if final_updated_items:
            self.info(f" 正在将 {len(final_updated_items)} 条润色结果写入表格...")
            self.emit(update_event, {
                "file_path": file_path,
                "target_column_index": 2, # 译文列
                "translation_status": TranslationStatus.POLISHED,
                "updated_items": final_updated_items
            })
        else:
            self.warning(" 未获得任何有效润色结果，表格未更新。")

        if done_event is not None:
            self.emit(done_event, {
                "operation": "polish",
                "status": "success" if final_updated_items else "empty",
                "file_path": file_path,
                "updated_item_count": len(final_updated_items),
                "success_batches": success_batches,
                "failed_batches": failed_batches,
                "total_items": total_items,
            })

        Base.work_status = Base.STATUS.IDLE 
        self.info(f" 🐳 表格润色任务结束")     


