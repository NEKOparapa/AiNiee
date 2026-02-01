import copy
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ModuleFolders.Base.Base import Base
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Service.TaskExecutor.TranslatorUtil import get_source_language_for_file
from ModuleFolders.Domain.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.Domain.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing
from ModuleFolders.Service.NERProcessor.NERProcessor import NERProcessor

# 简易请求器
class SimpleExecutor(Base):

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
        # 订阅术语提取任务事件
        self.subscribe(Base.EVENT.TERM_EXTRACTION_START, self.handle_term_extraction_start)
        # 订阅术语提取翻译事件
        self.subscribe(Base.EVENT.TERM_TRANSLATE_SAVE_START, self.handle_term_translate_save_start)

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
                "think_switch": data.get("think_switch"),
                "think_depth": data.get("think_depth"),
                "thinking_level": data.get("thinking_level"),
                "temperature": data.get("temperature"),
                "top_p": data.get("top_p")
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


    # 响应术语表翻译开始事件
    def glossary_translation_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.glossary_translation, args = (event, data))
        thread.start()

    # 术语表翻译
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

        # 获取未翻译术语
        untranslated_items = [item for item in prompt_dictionary_data if not item.get("dst")]
        if not untranslated_items:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 准备翻译配置
        config = TaskConfig()
        config.initialize()
        config.prepare_for_translation(TaskType.TRANSLATION)
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
                platform_config = config.get_platform_configuration("translationReq")
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

        # 准备翻译配置
        config = TaskConfig()
        config.initialize()
        config.prepare_for_translation(TaskType.TRANSLATION)
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
            current_platform_config = config.get_platform_configuration("translationReq")

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
            self.emit(Base.EVENT.TABLE_UPDATE, {
                "file_path": file_path,
                "target_column_index": 2, # 翻译列
                "updated_items": final_updated_items
            })
        else:
            self.warning(" 未获得任何有效翻译结果，表格未更新。")

        # 更新软件状态
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

        # 准备配置
        config = TaskConfig()
        config.initialize()
        config.prepare_for_translation(TaskType.POLISH)
        polishing_mode_selection = config.polishing_mode_selection
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
            current_platform_config = config.get_platform_configuration("polishingReq")
            
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
            if polishing_mode_selection == "source_text_polish":
                text_dict = source_text_dict
            else:
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
            self.emit(Base.EVENT.TABLE_UPDATE, {
                "file_path": file_path,
                "target_column_index": 3, # 润色列
                "updated_items": final_updated_items
            })
        else:
            self.warning(" 未获得任何有效润色结果，表格未更新。")

        Base.work_status = Base.STATUS.IDLE 
        self.info(f" 🐳 表格润色任务结束")     

    # 响应术语提取事件，并启动新线程
    def handle_term_extraction_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_term_extraction, args=(data,), daemon=True)
        thread.start()

    # 术语提取处理方法
    def process_term_extraction(self, data: dict):
        params = data.get("params", {})
        items_data = data.get("items_data", [])

        if not items_data:
            self.warning("术语提取任务中止：没有需要处理的文本。")
            self.emit(Base.EVENT.TERM_EXTRACTION_DONE, {"results": []})
            return

        self.info(f"开始处理术语提取任务... 参数: {params}")
        self.info(f"共收到 {len(items_data)} 条待处理数据。")

        # 实例化独立的处理器
        processor = NERProcessor()
        
        # 调用处理器的方法，传入正确的参数
        results = processor.extract_terms(
            items_data=items_data,
            model_name=params.get("model_name"), # 使用 model_name
            entity_types=params.get("entity_types")
        )
        
        self.info(f"术语提取完成，共找到 {len(results)} 个术语。")

        # 工作完成后，发射完成事件将结果传回UI线程
        self.emit(Base.EVENT.TERM_EXTRACTION_DONE, {"results": results})


    # 响应翻译并保存术语表的事件，启动新线程
    def handle_term_translate_save_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_term_translate_and_save, args=(data,), daemon=True)
        thread.start()

    def process_term_translate_and_save(self, data: dict):
        """
        使用线程池并发处理术语的上下文翻译和保存任务。
        """
        # 提取数据
        extraction_results = data.get("extraction_results", [])
        if not extraction_results:
            self.warning("术语翻译任务中止：未收到任何提取结果。")
            self.emit(Base.EVENT.TERM_TRANSLATE_SAVE_DONE, {"status": "no_result", "message": "未收到提取结果"})
            return

        self.info("▶️ 开始执行【基于上下文翻译并保存术语】任务...")

        # 提取所有唯一的“所在原文”(context)
        unique_contexts = sorted(list(set(result['context'] for result in extraction_results)))
        if not unique_contexts:
            self.warning("术语翻译任务中止：没有有效的上下文原文。")
            self.emit(Base.EVENT.TERM_TRANSLATE_SAVE_DONE, {"status": "no_result", "message": "没有有效的上下文"})
            return

        # 准备翻译配置
        config = TaskConfig()
        config.initialize()
        config.prepare_for_translation(TaskType.TRANSLATION)
        target_language = config.target_language
        # 从配置中获取实际线程数
        max_threads = config.actual_thread_counts

        # 将原文分批处理
        MAX_LINES = 20  # 每批最大原文行数
        LOG_WIDTH = 50  # 日志框统一宽度
        total_items = len(unique_contexts)
        num_batches = (total_items + MAX_LINES - 1) // MAX_LINES

        # 打印整体任务信息
        print(f"\n╔{'═' * (LOG_WIDTH-2)}")
        print(f"║{'基于上下文的术语翻译与保存'.center(LOG_WIDTH-2)}")
        print(f"╠{'═' * (LOG_WIDTH-2)}")
        print(f"├─ 独立上下文总数: {total_items}")
        print(f"├─ 将分为 {num_batches} 个批次处理")
        print(f"└─ 使用线程池并发数: {max_threads}")

        # 定义用于线程池的工作函数
        def process_batch(batch_contexts, batch_num, total_batches):
            """处理单个批次的请求、解析和返回结果"""
            log_header = f" 批次 {batch_num}/{total_batches} "
            print(f"\n╔{'═' * (LOG_WIDTH-2)}")
            print(f"║{log_header.center(LOG_WIDTH-2)}")
            print(f"╠{'═' * (LOG_WIDTH-2)}")
            
            user_content = "\n".join(batch_contexts)
            system_prompt = f"""你是一位专业的术语提取与翻译专家。你的任务是分析用户提供的文本，并提取和翻译文本中的术语，请遵循以下步骤：
1.  识别术语：从提供的文本中提取所有实体名词。类型包括但不限于：人名、地名、组织、物品、装备、技能、魔法、种族、生物等等。
2.  翻译术语：将每个识别出的术语准确翻译成“{target_language}”。
3.  标注类型：为每个术语附上简短的类型注释（例如：“女性人名”、“地名”、“组织”、“物品”）。

### 输出格式
以textarea标签格式输出，如:
<textarea>
原文1|译文1|注释1
原文2|译文2|注释2
...|...|...
</textarea>
"""
            messages = [{"role": "user", "content": user_content}]

            # 每次请求都获取一次配置，以确保能轮询API Key
            platform_config = config.get_platform_configuration("translationReq")
            
            print(f"├─ 正在向AI发送请求 (共 {len(batch_contexts)} 行)...\n")
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages, system_prompt, platform_config
            )

            if skip or not response_content:
                self.error(f"第 {batch_num} 批次请求失败或返回内容为空。")
                print(f"└─ ❌ 请求失败或无回复，跳过此批次。")
                return [] # 返回空列表表示失败

            print("├─ 收到回复，正在解析...")
            
            try:
                match = re.search(r'<textarea>(.*?)</textarea>', response_content, re.DOTALL)
                if not match:
                    self.warning(f"第 {batch_num} 批次回复中未匹配到 <textarea> 块。")
                    print(f"└─ ⚠️ 回复中未找到有效术语块。")
                    return []

                content_block = match.group(1).strip()
                lines = content_block.split('\n')
                
                batch_parsed_terms = []
                warnings_in_batch = False

                for line in lines:
                    line = line.strip()
                    if not line: continue
                    
                    parts = line.split('|')
                    if len(parts) == 3:
                        src, dst, info = [p.strip() for p in parts]
                        if src:
                            batch_parsed_terms.append({"src": src, "dst": dst, "info": info})
                    else:
                        self.warning(f"解析失败，批次 {batch_num} 中格式不符: {line}")
                        warnings_in_batch = True
                
                print(f"├─ 本批次成功解析 {len(batch_parsed_terms)} 条术语。")
                if warnings_in_batch:
                    print(f"└─ ⚠️ 批次处理完成，但有解析警告。")
                else:
                    print(f"└─ ✅ 批次处理完成。")
                
                return batch_parsed_terms
            except Exception as e:
                self.error(f"解析第 {batch_num} 批次响应时发生严重错误: {e}")
                print(f"└─ ❌ 解析时发生严重错误，跳过此批次。")
                return []

        all_parsed_terms = []
        
        # 使用线程池并发处理批次
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            # 提交所有任务
            futures = []
            for i in range(num_batches):
                start_index = i * MAX_LINES
                end_index = start_index + MAX_LINES
                batch_contexts = unique_contexts[start_index:end_index]
                # 提交任务到线程池
                future = executor.submit(process_batch, batch_contexts, i + 1, num_batches)
                futures.append(future)
            
            # 获取已完成任务的结果
            for future in as_completed(futures):
                try:
                    # 获取工作函数的返回结果
                    batch_results = future.result()
                    if batch_results:
                        all_parsed_terms.extend(batch_results)
                except Exception as e:
                    self.error(f"一个术语翻译批次在执行中遇到严重错误: {e}")
        
        # 后续处理逻辑保持不变
        print("") # 在日志末尾添加一个空行，使格式更美观
        self.info("所有批次处理完成，正在将结果保存到术语表...")
        if not all_parsed_terms:
            self.warning("所有批次均未能解析出任何有效术语。任务结束。")
            self.emit(Base.EVENT.TERM_TRANSLATE_SAVE_DONE, {"status": "no_result", "message": "未解析到有效术语"})
            return

        # 加载配置文件
        app_config = self.load_config()
        prompt_dictionary_data = app_config.get("prompt_dictionary_data", [])
        
        # 获取旧术语表信息
        existing_srcs = {item['src'] for item in prompt_dictionary_data}
        
        # 对比去重
        added_count = 0
        unique_new_terms = {term['src']: term for term in all_parsed_terms}.values()

        for term in unique_new_terms:
            if term['src'] not in existing_srcs:
                prompt_dictionary_data.append(term)
                existing_srcs.add(term['src'])
                added_count += 1
        
        # 更新保存术语表配置
        app_config["prompt_dictionary_data"] = prompt_dictionary_data
        self.save_config(app_config)
        
        # 日志输出
        self.info(f"🐳 术语翻译与保存任务已完成！成功添加 {added_count} 个新术语到术语表。")
        self.emit(Base.EVENT.TERM_TRANSLATE_SAVE_DONE, {
            "status": "success", 
            "message": f"成功添加 {added_count} 个新术语。",
            "added_count": added_count
        })