import os
import re
import threading

from Base.Base import Base
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.TaskConfig.TaskType import TaskType
from ModuleFolders.TaskExecutor.TranslatorUtil import get_source_language_for_file
from ModuleFolders.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.ResponseExtractor.FormatExtractor import FormatExtractor
from ModuleFolders.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing
from ModuleFolders.PromptBuilder.PromptBuilderFormat import PromptBuilderFormat
from ModuleFolders.NERProcessor.NERProcessor import NERProcessor

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
        # 订阅表格派能任务事件
        self.subscribe(Base.EVENT.TABLE_FORMAT_START, self.handle_table_format_start)
        # 订阅术语提取任务事件
        self.subscribe(Base.EVENT.TERM_EXTRACTION_START, self.handle_term_extraction_start)

    # 响应接口测试开始事件
    def api_test_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.api_test, args = (event, data))
        thread.start()

    # 接口测试
    def api_test(self, event, data: dict):
        # 获取参数
        platform_tag = data.get("tag")
        platform_name = data.get("name")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        extra_body = data.get("extra_body",{})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")

        # 自动补全API地址
        if (platform_tag == "sakura" or platform_tag == "LocalLLM") and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
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
                "extra_body": extra_body
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

        # 获取参数
        platform_tag = data.get("tag")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        extra_body = data.get("extra_body",{})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")
        target_language = data.get("target_language")

        prompt_dictionary_data = data.get("prompt_dictionary_data")
        if not prompt_dictionary_data:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 自动补全API地址
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"


        # 解析并分割密钥字符串，并只取第一个密钥进行测试
        api_keys = re.sub(r"\s+","", api_key).split(",")
        api_key = api_keys[0]


        # 获取未翻译术语
        untranslated_items = [item for item in prompt_dictionary_data if not item.get("dst")]
        if not untranslated_items:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 分组处理（每组最多50个）
        group_size = 50
        translated_count = 0
        total_groups = (len(untranslated_items) + group_size - 1) // group_size

        # 输出整体进度信息
        print("")
        self.info(f" 开始术语表循环翻译 \n"
                f"├ 未翻译术语总数: {len(untranslated_items)}\n"
                f"├ 分组数量: {total_groups}\n"
                f"└ 每组上限: {group_size}术语")
        print("")

        # 构建平台配置
        platform_config = {
            "target_platform": platform_tag,
            "api_url": api_url,
            "api_key": api_key,
            "api_format": api_format,
            "model_name": model_name,
            "region": region,
            "access_key": access_key,
            "secret_key": secret_key,
            "extra_body": extra_body
        }

        # 分组翻译处理
        for group_idx in range(total_groups):
            start_idx = group_idx * group_size
            end_idx = start_idx + group_size
            current_group = untranslated_items[start_idx:end_idx]
            
            # 组处理开始日志
            print("")
            self.info(f" 正在处理第 {group_idx+1}/{total_groups} 组 \n"
                    f"├ 本组术语范围: {start_idx+1}-{min(end_idx, len(untranslated_items))}\n"
                    f"└ 实际处理数量: {len(current_group)}术语")
            print("")

            # 构造系统提示词
            system_prompt = (
                f"Translate the source text from the glossary into {target_language} line by line, maintaining accuracy and naturalness, and output the translation wrapped in a textarea tag:\n"
                "<textarea>\n"
                f"1.{target_language}text\n"
                "</textarea>\n"
            )

            # 构造消息内容，按行排列，并添加序号
            src_terms = [f"{idx+1}.{item['src']}" for idx, item in enumerate(current_group)]
            src_terms_text = "\n".join(src_terms)
            messages = [
                {
                    "role": "user",
                    "content": src_terms_text
                }
            ]

            # 请求发送日志
            print("")
            self.info(
                    f" 正在发送API请求...\n"
                    f"│ 平台类型: {platform_tag}\n"
                    f"│ 模型名称: {model_name}\n"
                    f"└ 目标语言: {target_language}")
            print("")

            # 发送翻译请求
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages,
                system_prompt,
                platform_config
            )

            # 如果请求失败，返回失败信息
            if skip:
                self.error(f"第 {group_idx+1}/{total_groups} 组翻译失败")
                self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                    "status": "error",
                    "message": f"第 {group_idx+1} 组翻译请求失败",
                    "updated_data": None
                })
                return

            # 如果请求成功，解析翻译结果
            try:
                # 提取译文结果
                textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', response_content, re.DOTALL)
                last_content = textarea_contents[-1]

                # 分行
                translated_terms = last_content.strip().split("\n")
                
                # 去除序号
                translated_terms = [re.sub(r'^\d+\.', '', term).strip() for term in translated_terms]

                # 检查翻译结果数量是否匹配
                if len(translated_terms) != len(current_group):
                    raise ValueError("翻译结果数量不匹配")
                    
            except Exception as e:
                self.error(f"翻译结果解析失败: {str(e)}")
                self.emit(Base.EVENT.GLOSS_TASK_DONE, {
                    "status": "error",
                    "message": f"第 {group_idx+1} 组结果解析失败",
                    "updated_data": None
                })
                return

            # 更新翻译结果
            for idx, item in enumerate(current_group):
                item["dst"] = translated_terms[idx]
            translated_count += len(current_group)

            # 进度更新日志
            print("")
            self.info(
                    f"├ 本组完成数量: {len(current_group)}\n"
                    f"├ 累计完成进度: {translated_count}/{len(untranslated_items)}\n"
                    f"└ 进度百分比: {translated_count/len(untranslated_items):.0%}")
            print("")

        # 全部完成
        self.info(f" 术语表翻译全部完成 \n"
                f"├ 总处理组数: {total_groups}\n"
                f"├ 总翻译术语: {translated_count}\n"
                f"└ 最终状态: {'成功' if translated_count == len(untranslated_items) else '失败'}")
        
        # 发送完成事件
        self.emit(Base.EVENT.GLOSS_TASK_DONE, {
            "status": "success",
            "updated_data": prompt_dictionary_data
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
        platform_config = config.get_platform_configuration("translationReq")
        file_source_lang = get_source_language_for_file(config.source_language, config.target_language, language_stats)

        # 翻译任务分割
        MAX_LINES = 10  # 最大行数
        LOG_WIDTH = 50  # 日志框的统一宽度
        total_items = len(items_to_translate)
        num_batches = (total_items + MAX_LINES - 1) // MAX_LINES

        self.info(f" 开始处理表格翻译任务: {os.path.basename(file_path)}")
        self.info(f"    总计 {total_items} 行文本, 将分为 {num_batches} 个批次处理。")

        for i in range(num_batches):
            start_index = i * MAX_LINES
            end_index = start_index + MAX_LINES
            batch_items = items_to_translate[start_index:end_index]
            
            batch_num = i + 1
            log_header = f" 批次 {batch_num}/{num_batches} "
            
            # 构建0基的数字序号原文词典
            source_text_dict = {str(idx): item['source_text'] for idx, item in enumerate(batch_items)}
            # 构建还原用索引地图
            index_map = [item['text_index'] for item in batch_items]

            # 为当前批次任务构建提示词内容
            messages, system_prompt, _ = PromptBuilder.generate_prompt(
                config, source_text_dict, [], file_source_lang
            )
            
            # 日志
            print(f"\n╔{'═' * (LOG_WIDTH-2)}")
            print(f"║{log_header.center(LOG_WIDTH-2)}")
            print(f"╠{'═' * (LOG_WIDTH-2)}")
            print(f"├─ 正在发送请求 (共 {len(batch_items)} 行)...")
            
            # 发送请求
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages, system_prompt, platform_config
            )

            # 检查请求是否失败
            if skip:
                print("├─ 请求失败，网络或API密钥错误。")
                print(f"└─ ❌ 跳过此批次。")
                continue

            # 日志输出
            print("├─ 收到回复，内容如下:")
            for line in response_content.strip().split('\n'):
                print(f"│  {line}")
            print(f"├{'─' * (LOG_WIDTH-2)}") # 添加一个分隔线

            # 提取和检查返回内容
            print("├─ 正在解析和校验回复...")
            response_dict = ResponseExtractor.text_extraction(self, source_text_dict, response_content)
            check_result, error_content = ResponseChecker.check_polish_response_content(self, config, response_content, response_dict, source_text_dict)
            
            if not check_result:
                print(f"├─ 内容校验失败: {error_content}")
                print(f"└─ ❌ 跳过此批次。")
                continue
            
            print(f"├─ 成功解析 {len(response_dict)} 条结果。")

            # 将字符串序号的字典转换回原始 text_index 的字典-
            restored_response_dict = {
                index_map[int(temp_idx_str)]: text
                for temp_idx_str, text in response_dict.items()
            }

            # 移除文本中的数字序号
            updated_items_for_ui = ResponseExtractor.remove_numbered_prefix(self, restored_response_dict)

            # 发送表格更新信号
            self.emit(Base.EVENT.TABLE_UPDATE, {
                "file_path": file_path,
                "target_column_index": 2,
                "updated_items": updated_items_for_ui
            })
            print(f"└─ ✅ 批次处理完成，已发送UI更新。")
            print("")

        # 更新软件状态
        Base.work_status = Base.STATUS.IDLE 
        self.info(f" 🐳 表格翻译任务已经全部完成")                            

    # 响应表格润色事件
    def handle_table_polish_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_table_polish, args=(data,), daemon=True)
        thread.start()

    # 表格文本的分批润色
    def process_table_polish(self, data: dict):
        """处理表格文件的批量翻译任务"""
        # 解包从UI传来的数据
        file_path = data.get("file_path")
        items_to_polish = data.get("items_to_polish")

        # 准备翻译配置
        config = TaskConfig()
        config.initialize()
        config.prepare_for_translation(TaskType.POLISH)
        platform_config = config.get_platform_configuration("polishingReq")
        polishing_mode_selection = config.polishing_mode_selection

        # 翻译任务分割
        MAX_LINES = 10  # 最大行数
        LOG_WIDTH = 50  # 日志框的统一宽度
        total_items = len(items_to_polish)
        num_batches = (total_items + MAX_LINES - 1) // MAX_LINES

        self.info(f" 开始处理表格润色任务: {os.path.basename(file_path)}")
        self.info(f"    总计 {total_items} 行文本, 将分为 {num_batches} 个批次处理。")

        for i in range(num_batches):
            start_index = i * MAX_LINES
            end_index = start_index + MAX_LINES
            batch_items = items_to_polish[start_index:end_index]
            
            batch_num = i + 1
            log_header = f" 批次 {batch_num}/{num_batches} "
            
            # 构建0基的数字序号原文词典
            source_text_dict = {str(idx): item['source_text'] for idx, item in enumerate(batch_items)}
            # 译文词典
            translation_text_dict = {str(idx): item['translation_text'] for idx, item in enumerate(batch_items)}
            # 构建还原用索引地图
            index_map = [item['text_index'] for item in batch_items]

            # 生成提示词内容
            messages, system_prompt, extra_log = PromptBuilderPolishing.generate_prompt(
                config,
                source_text_dict,
                translation_text_dict,
                [],
            )
            
            # 日志
            print(f"\n╔{'═' * (LOG_WIDTH-2)}")
            print(f"║{log_header.center(LOG_WIDTH-2)}")
            print(f"╠{'═' * (LOG_WIDTH-2)}")
            print(f"├─ 正在发送请求 (共 {len(batch_items)} 行)...")
            
            # 发送请求
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages, system_prompt, platform_config
            )

            # 检查请求是否失败
            if skip:
                print("├─ 请求失败，网络或API密钥错误。")
                print(f"└─ ❌ 跳过此批次。")
                continue

            # 日志输出
            print("├─ 收到回复，内容如下:")
            for line in response_content.strip().split('\n'):
                print(f"│  {line}")
            print(f"├{'─' * (LOG_WIDTH-2)}") # 添加一个分隔线


            # 根据润色模式调整文本对象
            if polishing_mode_selection == "source_text_polish":
                text_dict = source_text_dict
            elif polishing_mode_selection == "translated_text_polish":
                text_dict = translation_text_dict

            # 提取和检查返回内容
            print("├─ 正在解析和校验回复...")
            response_dict = ResponseExtractor.text_extraction(self, text_dict, response_content)
            check_result, error_content = ResponseChecker.check_polish_response_content(self, config, response_content, response_dict, text_dict)
            
            if not check_result:
                print(f"├─ 内容校验失败: {error_content}")
                print(f"└─ ❌ 跳过此批次。")
                continue
            
            print(f"├─ 成功解析 {len(response_dict)} 条结果。")

            # 将字符串序号的字典转换回原始 text_index 的字典-
            restored_response_dict = {
                index_map[int(temp_idx_str)]: text
                for temp_idx_str, text in response_dict.items()
            }

            # 移除文本中的数字序号
            updated_items_for_ui = ResponseExtractor.remove_numbered_prefix(self, restored_response_dict)

            # 发送表格更新信号
            self.emit(Base.EVENT.TABLE_UPDATE, {
                "file_path": file_path,
                "target_column_index": 3,
                "updated_items": updated_items_for_ui
            })
            print(f"└─ ✅ 批次处理完成，已发送UI更新。")
            print("")

        # 更新软件状态
        Base.work_status = Base.STATUS.IDLE 
        self.info(f" 🐳 表格润色任务已经全部完成")         


    # 响应表格排版事件
    def handle_table_format_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_table_format, args=(data,), daemon=True)
        thread.start()

    # 表格文本的全量排版
    def process_table_format(self, data: dict):
        """处理表格文件的全量排版任务"""

        # 解包从UI传来的数据
        file_path = data.get("file_path")
        items_to_format = data.get("items_to_format")
        original_selected_indices = data.get("selected_item_indices")

        if not items_to_format:
            self.warning("排版任务中止：没有需要处理的文本。")
            Base.work_status = Base.STATUS.IDLE
            return

        # 准备排版配置
        config = TaskConfig()
        config.initialize()
        config.prepare_for_translation(TaskType.FORMAT)
        platform_config = config.get_platform_configuration("formatReq")

        # 日志和准备工作
        LOG_WIDTH = 60  # 日志框的统一宽度
        total_items = len(items_to_format)
        
        self.info(f"▶️ 开始处理表格排版任务: {os.path.basename(file_path)}")
        self.info(f"   总计 {total_items} 行文本将一次性处理。")
        
        print(f"\n╔{'═' * (LOG_WIDTH-2)}")
        print(f"║{'表格文本排版'.center(LOG_WIDTH-2)}")
        print(f"╠{'═' * (LOG_WIDTH-2)}")

        # 构建完整的原文词典 (0-based str index)
        source_text_dict = {str(idx): item['source_text'] for idx, item in enumerate(items_to_format)}

        # 生成提示词
        messages, system_prompt, _ = PromptBuilderFormat.generate_prompt(
            config,
            source_text_dict,
        )
        
        # 发送单个、完整的请求
        print(f"├─ 正在发送请求 (共 {len(source_text_dict)} 行)...")
        requester = LLMRequester()
        skip, _, response_content, _, _ = requester.sent_request(
            messages, system_prompt, platform_config
        )

        # 处理请求失败的情况
        if skip:
            print("├─ ❌ 请求失败，可能是网络问题或API密钥错误。")
            print(f"└{'═' * (LOG_WIDTH-2)}")
            self.error("表格排版请求失败，任务已中止。")
            Base.work_status = Base.STATUS.IDLE  # 任务失败，重置状态
            return

        # 日志输出
        print("├─ 收到回复，内容如下:")
        for line in response_content.strip().split('\n'):
            print(f"│  {line}")
        print(f"├{'─' * (LOG_WIDTH-2)}") # 添加一个分隔线

        # 提取和检查返回内容
        print("├─ 正在解析和校验回复...")
        response_dict = FormatExtractor.text_extraction(self, response_content)
        """
        response_dict: 一个字典，键是内容的行号（字符串形式），值是另一个字典，
        包含 'text' (行文本) 和 'blank_lines_after' (该行后的空行数)。
        例如: {'0': {'text': '第一行', 'blank_lines_after': 2}, ...}
        """

        # 校验解析结果
        if not response_dict:
            print(f"└❌ 内容提取失败。\n")
            self.error("表格排版解析失败，任务已中止。")
            Base.work_status = Base.STATUS.IDLE # 任务失败，重置状态
            return
        
        print(f"├─ ✅ 成功解析 {len(response_dict)} 条结果。")

        # 发送单次表格更新信号
        self.emit(Base.EVENT.TABLE_FORMAT, {
            "file_path": file_path,
            "updated_items": response_dict,      
            "selected_item_indices": original_selected_indices, 
        })
        print(f"└ 🚀 已发送UI更新指令。\n")

        # 11. 任务完成，更新全局状态
        Base.work_status = Base.STATUS.IDLE 
        self.info(f"🐳 表格排版任务已完成！")

    # 响应术语提取事件，并启动新线程
    def handle_term_extraction_start(self, event, data: dict):
        thread = threading.Thread(target=self.process_term_extraction, args=(data,), daemon=True)
        thread.start()

    # 术语提取处理方法
    def process_term_extraction(self, data: dict):
        """在后台线程中执行术语提取的核心逻辑"""
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
        
        # 调用处理器的方法，传入数据和参数
        results = processor.extract_terms(
            items_data=items_data,
            language=params.get("language"),
            entity_types=params.get("entity_types")
        )
        
        self.info(f"术语提取完成，共找到 {len(results)} 个术语。")

        # 工作完成后，发射完成事件将结果传回UI线程
        self.emit(Base.EVENT.TERM_EXTRACTION_DONE, {"results": results})