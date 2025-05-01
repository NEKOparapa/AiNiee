import copy
import os
import re
import time
import itertools
import json # 确保导入 json
from typing import List, Tuple, Dict # 确保导入 Tuple 和 Dict

import rapidjson # 保持 rapidjson 导入，如果其他地方仍在使用
from rich import box
from rich.table import Table
from rich.markup import escape

from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderThink import PromptBuilderThink
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.PromptBuilder.PromptBuilderDouble import PromptBuilderDouble
from ModuleFolders.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter

# 导入 TextProcessor
from ModuleFolders.TextProcessor.TextProcessor import TextProcessor

class TranslatorTask(Base):

    def __init__(self, config: TranslatorConfig, plugin_manager: PluginManager,request_limiter: RequestLimiter) -> None:
        super().__init__()

        self.config = config
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter

        # 初始化消息存储
        self.messages = []
        self.messages_a = []
        self.messages_b = []
        self.system_prompt = ""
        self.system_prompt_a = ""
        self.system_prompt_b = ""

        # 输出日志存储
        self.extra_log = []
        # 双请求翻译的文本占位符替换字典
        self.replace_dict = {}
        # 前后缀处理信息存储
        self.prefix_codes = {}
        self.suffix_codes = {}
        # 占位符顺序存储结构
        self.placeholder_order = {}
        # 前后换行空格处理信息存储
        self.affix_whitespace_storage = {}

        # --- 修改：读取正则表达式并初始化 TextProcessor ---
        # 读取并编译正则表达式模式
        self.compiled_code_patterns_with_source = self._prepare_regex_patterns() #<-- 统一变量名
        # 创建 TextProcessor 实例，传递配置对象（可能包含译前/译后规则）
        self.text_processor = TextProcessor(config=self.config)
        # --- 修改 End ---


    # 读取正则库和禁翻表的正则，并进行预编译
    def _prepare_regex_patterns(self) -> List[Tuple[str, re.Pattern]]: # <--- 修改返回类型
        """准备所有需要使用的正则表达式模式，返回 (原始字符串, 编译后对象) 的元组列表"""
        patterns = []
        compiled_patterns_with_source = [] # 修改变量名

        # 从正则库加载基础正则
        regex_file_path = os.path.join(".", "Resource", "Regex", "regex.json")
        if os.path.exists(regex_file_path):
            try:
                with open(regex_file_path, 'r', encoding='utf-8') as f:
                    # 使用 rapidjson 加载以提高性能
                    data = rapidjson.load(f)
                    # 确保 data 是列表且 item 是字典
                    file_patterns = [item["regex"] for item in data if isinstance(item, dict) and "regex" in item]
                    patterns.extend(file_patterns)
            except (FileNotFoundError, rapidjson.JSONDecodeError, KeyError, TypeError) as e: # 添加 TypeError
                self.error(f"加载正则文件 '{regex_file_path}' 失败", e) # 使用 Base.error
        else:
            self.warning(f"正则文件未找到: '{regex_file_path}'") # 使用 Base.warning

        # 合并禁翻表数据 (确保 config.exclusion_list_data 是列表)
        exclusion_list_data = getattr(self.config, 'exclusion_list_data', [])
        exclusion_patterns = [] # 单独存储禁翻表的模式字符串
        if exclusion_list_data and isinstance(exclusion_list_data, list):
            for item in exclusion_list_data:
                # 确保 item 是字典
                if not isinstance(item, dict):
                    continue
                # 读取正则表达式
                if regex_str := item.get("regex"): # 使用 walrus 操作符简化
                    # 验证正则表达式有效性
                     try:
                         re.compile(regex_str) # 尝试编译但不存储
                         exclusion_patterns.append(regex_str)
                     except re.error as e:
                         self.warning(f"禁翻表中无效的正则表达式，已跳过: '{regex_str}', 错误: {e}") # 使用 Base.warning
                # 将标记符，转义为特殊字符并添加为普通匹配
                elif markers := item.get("markers"): # 使用 markers 字段
                     exclusion_patterns.append(re.escape(markers)) # 转义 markers

        patterns.extend(exclusion_patterns)

        # 编译所有模式
        for pattern_str in patterns:
            if pattern_str: # 跳过空字符串
                try:
                    # 编译并添加 (原始字符串, 编译对象)
                    compiled_pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                    compiled_patterns_with_source.append((pattern_str, compiled_pattern))
                except re.error as e:
                    self.warning(f"正则表达式编译失败，已跳过: '{pattern_str}', 错误: {e}") # 使用 Base.warning
                    continue # 跳过无效模式

        return compiled_patterns_with_source

    # 设置缓存数据
    def set_items(self, items: list[CacheItem]) -> None:
        self.items = items

    # 设置上文数据
    def set_previous_items(self, previous_items: list[CacheItem]) -> None:
        self.previous_items = previous_items

    # 消息构建预处理
    def prepare(self, target_platform: str, prompt_preset: int) -> None:

        # 生成上文文本列表
        self.previous_text_list = [v.source_text for v in self.previous_items]

        # 生成原文文本字典
        self.source_text_dict = {str(i): v.source_text for i, v in enumerate(self.items)}

        # 生成文本行数信息
        self.row_count = len(self.source_text_dict)

        # 触发插件事件 - 文本正规化
        self.plugin_manager.broadcast_event("normalize_text", self.config, self.source_text_dict)

        # --- 修改：使用 self.text_processor 实例 ---
        # 各种替换步骤，译前替换，提取首尾与占位中间代码
        # <--- 修正这里，传递编译好的模式 -->
        self.source_text_dict, self.prefix_codes, self.suffix_codes,self.placeholder_order,self.affix_whitespace_storage = self.text_processor.replace_all(
            self.config, self.source_text_dict, self.compiled_code_patterns_with_source # <--- 添加缺失的参数
        )
        # --- 修改 End ---

        # 生成请求指令
        if self.config.double_request_switch_settings == True:
            self.messages_a, self.system_prompt_a = self.generate_prompt_DRA()
            self.messages_b, self.system_prompt_b = self.generate_prompt_DRB()

        elif target_platform == "sakura":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_sakura(
                self.source_text_dict,
                self.previous_text_list,
            )
        elif target_platform == "LocalLLM":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_LocalLLM(
                self.source_text_dict,
                self.previous_text_list,
            )
        elif prompt_preset in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT,PromptBuilderEnum.THINK, PromptBuilderEnum.CUSTOM):
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt(
                self.source_text_dict,
                self.previous_text_list
            )

        # 预估 Token 消费
        self.request_tokens_consume = self.request_limiter.calculate_tokens(
            self.messages,
            self.messages_a,
            self.messages_b,
            self.system_prompt,
            self.system_prompt_a,
            self.system_prompt_b
            )

    # =============================================
    # --- generate_prompt* 系列函数保持不变 ---
    # =============================================
    # 生成信息结构 - 通用和思维链和推理模型(通用与推理模型与自定义使用同一提示词框架，除了系统提示词不同。思维链使用不同的框架，系统提示词也不同)
    def generate_prompt(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础系统提示词
        if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:  # 自定义提示词
            system = self.config.system_prompt_content

        elif self.config.prompt_preset == PromptBuilderEnum.THINK: # 推理模型提示词
            system = PromptBuilderThink.build_system(self.config)

        else:
            system = PromptBuilder.build_system(self.config)  # 通用与思维链提示词

        # 如果开启自动构建术语表
        if self.config.auto_glossary_toggle == True:
            glossary_criteria = PromptBuilder.build_glossary_extraction_criteria(self.config)
            if glossary_criteria != "":
                system += glossary_criteria
                extra_log.append(glossary_criteria)

        # 如果开启自动构建禁翻表
        if self.config.auto_exclusion_list_toggle == True:
            ntl_criteria = PromptBuilder.build_ntl_extraction_criteria(self.config)
            if ntl_criteria != "":
                system += ntl_criteria
                extra_log.append(ntl_criteria)

        # 如果开启术语表
        if self.config.prompt_dictionary_switch == True:
            glossary = PromptBuilder.build_glossary_prompt(self.config, source_text_dict)
            if glossary != "":
                system += glossary
                extra_log.append(glossary)

        # 如果开启禁翻表
        if self.config.exclusion_list_switch == True:
            ntl = PromptBuilder.build_ntl_prompt(self.config, source_text_dict)
            if ntl != "":
                system += ntl
                extra_log.append(ntl)


        # 如果角色介绍开关打开
        if self.config.characterization_switch == True:
            characterization = PromptBuilder.build_characterization(self.config, source_text_dict)
            if characterization != "":
                system += characterization
                extra_log.append(characterization)

        # 如果启用自定义世界观设定功能
        if self.config.world_building_switch == True:
            world_building = PromptBuilder.build_world_building(self.config)
            if world_building != "":
                system += world_building
                extra_log.append(world_building)

        # 如果启用自定义行文措辞要求功能
        if self.config.writing_style_switch == True:
            writing_style = PromptBuilder.build_writing_style(self.config)
            if writing_style != "":
                system += writing_style
                extra_log.append(writing_style)

        # 如果启用翻译风格示例功能
        if self.config.translation_example_switch == True:
            translation_example = PromptBuilder.build_translation_example(self.config)
            if translation_example != "":
                system += translation_example
                extra_log.append(translation_example)

        # 构建动态few-shot
        if self.config.few_shot_and_example_switch == True:

            # 获取默认示例前置文本
            pre_prompt = PromptBuilder.build_userExamplePrefix(self.config)
            fol_prompt = PromptBuilder.build_modelExamplePrefix(self.config)

            # 获取具体动态示例内容
            original_exmaple, translation_example_content = PromptBuilder.build_translation_sample(self.config, source_text_dict)
            if original_exmaple and translation_example_content:
                messages.append({
                    "role": "user",
                    "content": f"{pre_prompt}<textarea>\n{original_exmaple}\n</textarea>"
                })
                messages.append({
                    "role": "assistant",
                    "content": f"{fol_prompt}<textarea>\n{translation_example_content}\n</textarea>"
                })
                extra_log.append(f"原文示例已添加：\n{original_exmaple}")
                extra_log.append(f"译文示例已添加：\n{translation_example_content}")

        # 如果加上文，获取上文内容
        previous = ""
        if self.config.pre_line_counts and previous_text_list:
            previous = PromptBuilder.build_pre_text(self.config, previous_text_list)
            if previous != "":
                extra_log.append(f"###上文\n{"\n".join(previous_text_list)}")

        # 获取用户提问时的前置文本
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config)

        # 构建待翻译文本
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            # 检查是否为多行文本
            if "\n" in line:
                lines = line.split("\n")  # 需要与回复提取的行分割方法一致
                numbered_text = f"{index + 1}.[\n"
                total_lines = len(lines)
                for sub_index, sub_line in enumerate(lines):
                    # 不去除空白内容，保留\r其他平台的换行符，虽然AI回复不一定保留...
                    # 仅当 **只有一个** 尾随空格时才去除
                    sub_line = sub_line[:-1] if re.match(r'.*[^ ] $', sub_line) else sub_line
                    numbered_text += f'"{index + 1}.{total_lines - sub_index}.,{sub_line}",\n'
                numbered_text = numbered_text.rstrip('\n')
                numbered_text = numbered_text.rstrip(',')
                numbered_text += f"\n]"  # 用json.dumps会影响到原文的转义字符
                numbered_lines.append(numbered_text)
            else:
                # 单行文本直接添加序号
                numbered_lines.append(f"{index + 1}.{line}")

        source_text_str = "\n".join(numbered_lines)
        source_text_str = f"{previous}\n{pre_prompt}<textarea>\n{source_text_str}\n</textarea>"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        # 构建模型预输入回复信息，deepseek-reasoner 不支持该模型预回复消息
        if self.config.few_shot_and_example_switch == True:
            # 获取模型预输入回复前文
            fol_prompt = PromptBuilder.build_modelResponsePrefix(self.config)
            # 构建模型预输入回复信息
            messages.append({"role": "assistant", "content": fol_prompt})


        return messages, system, extra_log

    # 生成信息结构 - Sakura
    def generate_prompt_sakura(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        system = PromptBuilderSakura.build_system(self.config)


        # 如果开启术语表
        glossary = ""
        if self.config.prompt_dictionary_switch == True:
            glossary = PromptBuilderSakura.build_glossary(self.config, source_text_dict)
            if glossary != "":
                extra_log.append(glossary)


        # 构建主要提示词
        if glossary == "":
            user_prompt = "将下面的日文文本翻译成中文：\n" + "\n".join(source_text_dict.values())
        else:
            user_prompt = (
                "根据以下术语表（可以为空）：\n" + glossary
                + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：\n" + "\n".join(source_text_dict.values())
            )

        # 构建指令列表
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        return messages, system, extra_log

    # 生成信息结构 - LocalLLM
    def generate_prompt_LocalLLM(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        system = PromptBuilderLocal.build_system(self.config)

        # 术语表
        if self.config.prompt_dictionary_switch == True:
            result = PromptBuilder.build_glossary_prompt(self.config, source_text_dict)
            if result != "":
                system = system + "\n" + result
                extra_log.append(result)

        # 如果开启禁翻表
        if self.config.exclusion_list_switch == True:
            ntl = PromptBuilder.build_ntl_prompt(self.config, source_text_dict)
            if ntl != "":
                system += ntl
                extra_log.append(ntl)


        # 构建待翻译文本 (添加序号)
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            # 检查是否为多行文本
            if "\n" in line:
                lines = line.split("\n")
                numbered_text = f"{index + 1}.[\n"
                total_lines = len(lines)
                for sub_index, sub_line in enumerate(lines):
                    # 仅当 **只有一个** 尾随空格时才去除
                    sub_line = sub_line[:-1] if re.match(r'.*[^ ] $', sub_line) else sub_line
                    numbered_text += f'"{index + 1}.{total_lines - sub_index}.,{sub_line}",\n'
                numbered_text = numbered_text.rstrip('\n')
                numbered_text = numbered_text.rstrip(',')
                numbered_text += f"\n]"  # 用json.dumps会影响到原文的转义字符
                numbered_lines.append(numbered_text)
            else:
                # 单行文本直接添加序号
                numbered_lines.append(f"{index + 1}.{line}")

        source_text_str = "\n".join(numbered_lines)
        source_text_str = f"<textarea>\n{source_text_str}\n</textarea>"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )


        return messages, system, extra_log

    # 构造通用信息结构 第一次请求
    def generate_prompt_DRA(self):
        """构建通用消息结构"""

        # 获取流程设计配置
        request_cards = self.config.flow_design_list["request_phase_a"]

        messages = []
        system_content = ""

        for card in request_cards:
            if card["type"] == "DialogueFragmentCard":
                settings = card["settings"]

                role = settings["role"]
                content = settings["content"]


                # 记录系统消息
                if role == "system":
                    system_content = content

                # 只在角色不是 "system" 时才添加到 messages 列表
                if role != "system":
                    messages.append({
                        "role": role,
                        "content": content
                    })
                settings["system_info"] = content


        return messages, system_content

    # 构造通用信息结构 第二次请求
    def generate_prompt_DRB(self):
        """构建通用消息结构"""

        # 获取流程设计配置
        request_cards = self.config.flow_design_list["request_phase_b"]

        messages = []
        system_content = ""

        for card in request_cards:
            if card["type"] == "DialogueFragmentCard":
                settings = card["settings"]

                role = settings["role"]
                content = settings["content"]


                # 记录系统消息
                if role == "system":
                    system_content = content

                # 只在角色不是 "system" 时才添加到 messages 列表
                if role != "system":
                    messages.append({
                        "role": role,
                        "content": content
                    })
                settings["system_info"] = content

        return messages, system_content
    # =============================================
    # --- generate_prompt* 系列函数结束 ---
    # =============================================


    # 更新系统提示词的术语表内容(因为是特殊处理的补丁，很多判断要重新加入，后续提示词相关更新需要重点关注该函数，以免bug)
    def update_sysprompt_glossary(self,config,system_prompt,glossary_buffer_data, prompt_dictionary_data, source_text_dict):

        # 应用开关检查
        if config.prompt_dictionary_switch == False:
            return system_prompt

        # 本地接口不适用
        if config.target_platform == "sakura":
            return system_prompt

        if config.target_platform == "LocalLLM":
            return system_prompt

        # 复制数据
        dict1 = copy.deepcopy(glossary_buffer_data)
        dict2 = copy.deepcopy(prompt_dictionary_data)

        # 合并术语表
        merged = {item['src']: item for item in dict1} # 创建基于src的字典，优先保留prompt条目
        merged.update({item['src']: item for item in dict2})
        # 移除glossary条目中的count字段，保持格式
        result_dict =  [
            {"src": k, "dst": v["dst"], "info": v["info"]}
            for k, v in merged.items()
        ]

        # 生成符合条件的术语条目
        entries = []
        for item in result_dict:
            src = item.get("src", "")
            # 检查原文是否在任意源文本中出现
            if any(src in text for text in source_text_dict.values()):
                dst = item.get("dst", "")
                info = item.get("info", "")
                entries.append(f"{src}|{dst}|{info}")

        # 构建新术语表
        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            term_table = "###术语表\n原文|译文|备注"
        else:
            term_table = "###Glossary\nOriginal Text|Translation|Remarks"
        if entries:
            term_table += "\n" + "\n".join(entries)
            term_table += "\n\n"
        else:
            return system_prompt

        # 处理系统提示
        if "###术语表" in system_prompt:
            # 正则匹配术语表区块（含标题行）
            pattern = r'###术语表[^\#]*'
            return re.sub(pattern, term_table, system_prompt, flags=re.DOTALL)

        elif "###Glossary" in system_prompt:
            # 正则匹配术语表区块（含标题行）
            pattern = r'###Glossary[^\#]*'
            return re.sub(pattern, term_table, system_prompt, flags=re.DOTALL)

        else:
            # 直接拼接新术语表
            delimiter = "\n" if system_prompt and not system_prompt.endswith("\n") else ""
            return f"{system_prompt}{delimiter}\n{term_table}"


    # 生成日志行
    def generate_log_rows(self, error: str, start_time: int, prompt_tokens: int, completion_tokens: int, source: list[str], translated: list[str], extra_log: list[str]) -> tuple[list[str], bool]:
        rows = []

        if error != "":
            rows.append(error)
        else:
            rows.append(
                f"任务耗时 {(time.time() - start_time):.2f} 秒，"
                + f"文本行数 {len(source)} 行，提示消耗 {prompt_tokens} Tokens，补全消耗 {completion_tokens} Tokens"
            )

        # 添加额外日志
        for v in extra_log:
            rows.append(v.strip())

        # 原文译文对比
        pair = ""
        # 修复变量名冲突问题，将循环变量改为 s 和 t
        for idx, (s, t) in enumerate(itertools.zip_longest(source, translated, fillvalue=""), 1):
            pair += f"\n--- Text {idx} ---\n"
            # 处理原文和译文的换行，分割成多行
            s_lines = s.split('\n') if s is not None else ['']
            t_lines = t.split('\n') if t is not None else ['']
            # 逐行对比，确保对齐
            for s_line, t_line in itertools.zip_longest(s_lines, t_lines, fillvalue=""):
                pair += f"{s_line} [bright_blue]-->[/] {t_line}\n"

        rows.append(pair.strip())

        return rows, error == ""

    # 生成日志表格
    def generate_log_table(self, rows: list, success: bool) -> Table:
        table = Table(
            box = box.ASCII2,
            expand = True,
            title = " ",
            caption = " ",
            highlight = True,
            show_lines = True,
            show_header = False,
            show_footer = False,
            collapse_padding = True,
            border_style = "green" if success else "red",
        )
        table.add_column("", style = "white", ratio = 1, overflow = "fold")

        for row in rows:
            if isinstance(row, str):
                table.add_row(escape(row, re.compile(r"(\\*)(\[(?!bright_blue\]|\/\])[a-z#/@][^[]*?)").sub)) # 修复rich table不显示[]内容问题
            else:
                table.add_row(*row)

        return table


    # 启动任务
    def start(self) -> dict:
        if self.config.double_request_switch_settings == True:
            return self.unit_DRtranslation_task()
        else:
            return self.unit_translation_task()


    # 单请求翻译任务
    def unit_translation_task(self) -> dict:
        # 任务开始的时间
        task_start_time = time.time()

        while True:
            # 检测是否收到停止翻译事件
            if Base.work_status == Base.STATUS.STOPING:
                return {}

            # 检查是否超时，超时则直接跳过当前任务，以避免死循环
            if time.time() - task_start_time >= self.config.request_timeout:
                return {}

            # 检查 RPM 和 TPM 限制，如果符合条件，则继续
            if self.request_limiter.check_limiter(self.request_tokens_consume):
                break

            # 如果以上条件都不符合，则间隔 1 秒再次检查
            time.sleep(1)

        # 获取接口配置信息包
        platform_config = self.config.get_platform_configuration("singleReq")

        # 读取术语表更新系统提示词,因为核心流程限制，而加上的挫版补丁.....
        self.system_prompt = self.update_sysprompt_glossary(self.config,self.system_prompt,self.config.glossary_buffer_data, self.config.prompt_dictionary_data, self.source_text_dict)

        # 发起请求
        requester = LLMRequester()
        skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
            self.messages,
            self.system_prompt,
            platform_config
        )

        # 如果请求结果标记为 skip，即有运行错误发生，则直接返回错误信息，停止后续任务
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        # 提取回复内容
        if  self.config.target_platform != "sakura":
            response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content,self.config.target_language)
        else:
            response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction_sakura(self, self.source_text_dict, response_content)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config,
            self.config.target_platform,
            self.placeholder_order, # 传递 placeholder_order
            response_content,
            response_dict,         # 传递提取出的译文
            self.source_text_dict, # 传递原始（占位符处理后）的原文
        )

        # --- Debugging Placeholder Issue ---
        if self.is_debug() and not check_result and "未能正确保留全部的占位符" in error_content:
            self.debug(f"占位符检查失败! Task ID (approximated by first item index): {self.items[0].text_index if self.items else 'N/A'}")
            for key in self.placeholder_order:
                expected_placeholders = [p.get('placeholder', 'MISSING_PH') for p in self.placeholder_order.get(key, [])]
                actual_text = response_dict.get(key, "KEY_NOT_FOUND_IN_RESPONSE")
                if expected_placeholders: # 只打印包含预期占位符的 key
                    self.debug(f"  Key '{key}':")
                    self.debug(f"    Expected Placeholders: {expected_placeholders}")
                    self.debug(f"    Actual Text (after extraction): {repr(actual_text[:100])}...")
                    missing = [p for p in expected_placeholders if isinstance(actual_text, str) and p not in actual_text]
                    if missing:
                        self.debug(f"    [!] Missing: {missing}")
        # --- End Debugging ---


        # 去除回复内容的数字序号
        if  self.config.target_platform != "sakura":
            response_dict = ResponseExtractor.remove_numbered_prefix(self, self.source_text_dict, response_dict)


        # 模型回复日志
        if response_think:
            self.extra_log.append("模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("模型回复内容：\n" + response_content)

        # 检查译文
        if check_result == False:
            error = f"译文文本未通过检查，将在下一轮次的翻译中重新翻译 - {error_content}"

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        error,
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        list(self.source_text_dict.values()), # 确保传递列表
                        list(response_dict.values()),      # 确保传递列表
                        self.extra_log,
                    )
                )
            )
        else:
            # --- 修改：使用 self.text_processor 实例 ---
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.text_processor.restore_all(
                self.config, restore_response_dict, self.prefix_codes, self.suffix_codes, self.placeholder_order, self.affix_whitespace_storage
            )
            # --- 修改 End ---

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                with item.atomic_scope():
                    item.model = self.config.model
                    item.translated_text = response
                    item.translation_status = CacheItem.STATUS.TRANSLATED

            # 更新术语表与禁翻表到配置文件中
            self.config.update_glossary_ntl_config(glossary_result, NTL_result)

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        list(self.source_text_dict.values()), # 确保传递列表
                        list(response_dict.values()),      # 确保传递列表
                        self.extra_log,
                    )
                )
            )


        # 否则返回译文检查的结果
        if check_result == False:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }
        else:
            return {
                "check_result": check_result,
                "row_count": self.row_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }


    # 双请求翻译任务
    def unit_DRtranslation_task(self) -> dict:
        # 任务开始的时间
        task_start_time = time.time()

        while True:
            # 检测是否收到停止翻译事件
            if Base.work_status == Base.STATUS.STOPING:
                return {}

            # 检查是否超时，超时则直接跳过当前任务，以避免死循环
            if time.time() - task_start_time >= self.config.request_timeout:
                return {}

            # 检查 RPM 和 TPM 限制，如果符合条件，则继续
            if self.request_limiter.check_limiter(self.request_tokens_consume):
                break


            # 如果以上条件都不符合，则间隔 1 秒再次检查
            time.sleep(1)


        # 构造初始替换字典
        previous_text = PromptBuilderDouble.get_previous_text(self, self.previous_text_list) # 上文
        source_text_str = PromptBuilderDouble.get_source_text(self, self.source_text_dict) # 原文
        glossary = PromptBuilderDouble.get_glossary(self, self.config, self.source_text_dict) # 术语表
        code = PromptBuilderDouble.build_ntl_prompt(self, self.config, self.source_text_dict) # 禁翻表

        self.replace_dict = {
            "{original_text}":source_text_str,
            "{previous_text}":previous_text,
            "{glossary}":glossary,
            "{code_text}":code
        }


        # 进行文本占位符替换
        messages, system_content = PromptBuilderDouble.replace_message_content(self,
            self.replace_dict,
            self.messages_a,
            self.system_prompt_a
        )

        # 获取第一次平台配置信息包
        platform_config = self.config.get_platform_configuration("doubleReqA")
        model_a = platform_config["model_name"]

        # 发起第一次请求
        requester = LLMRequester()
        skip, response_think, response_content, prompt_tokens_a, completion_tokens_a = requester.sent_request(
            messages,
            system_content,
            platform_config
        )

        # 如果请求结果标记为 skip，即有运行错误发生，则直接返回错误信息，停止后续任务
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        # 提取回复内容
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content,self.config.target_language)

        # 更新术语表与禁翻表到配置文件中
        self.config.update_glossary_ntl_config(glossary_result, NTL_result)


        # 模型回复日志
        if response_think:
            self.extra_log.append("第一次模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("第一次模型回复内容：\n" + response_content)


        # 进行提取阶段,并更新替换字典
        self.replace_dict,self.extra_log = PromptBuilderDouble.process_extraction_phase(self,
            self.config,
            self.replace_dict,
            response_think,
            response_content,
            self.extra_log
        )


        # 进行第二次文本占位符替换
        messages, system_content = PromptBuilderDouble.replace_message_content(self,
            self.replace_dict,
            self.messages_b,
            self.system_prompt_b
        )


        # 获取第二次平台配置信息包
        platform_config = self.config.get_platform_configuration("doubleReqB")
        model_b = platform_config["model_name"]

        # 发起第二次请求
        requester = LLMRequester()
        skip, response_think, response_content, prompt_tokens_b, completion_tokens_b = requester.sent_request(
            messages,
            system_content,
            platform_config
        )


        # 如果请求结果标记为 skip，即有运行错误发生，则直接返回错误信息，停止后续任务
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        # 提取回复内容
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self,  self.source_text_dict, response_content,self.config.target_language)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config,
            self.config.request_b_platform_settings,
            self.placeholder_order, # 传递 placeholder_order
            response_content,
            response_dict,         # 传递提取出的译文
            self.source_text_dict  # 传递原始（占位符处理后）的原文
        )

        # --- Debugging Placeholder Issue ---
        if self.is_debug() and not check_result and "未能正确保留全部的占位符" in error_content:
            self.debug(f"占位符检查失败! Task ID (approximated by first item index): {self.items[0].text_index if self.items else 'N/A'}")
            for key in self.placeholder_order:
                expected_placeholders = [p.get('placeholder', 'MISSING_PH') for p in self.placeholder_order.get(key, [])]
                actual_text = response_dict.get(key, "KEY_NOT_FOUND_IN_RESPONSE")
                if expected_placeholders: # 只打印包含预期占位符的 key
                    self.debug(f"  Key '{key}':")
                    self.debug(f"    Expected Placeholders: {expected_placeholders}")
                    self.debug(f"    Actual Text (after extraction): {repr(actual_text[:100])}...")
                    missing = [p for p in expected_placeholders if isinstance(actual_text, str) and p not in actual_text]
                    if missing:
                        self.debug(f"    [!] Missing: {missing}")
        # --- End Debugging ---


        # 去除回复内容的数字序号
        response_dict = ResponseExtractor.remove_numbered_prefix(self, self.source_text_dict, response_dict)


        # 模型回复日志
        if response_think != "":
            self.extra_log.append("第二次模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("第二次模型回复内容：\n" + response_content)

        # 合并消耗和模型号
        prompt_tokens = prompt_tokens_a + prompt_tokens_b
        completion_tokens = completion_tokens_a + completion_tokens_b
        model = model_a + " and " + model_b

        # 检查译文
        if check_result == False:
            error = f"译文文本未通过检查，将在下一轮次的翻译中重新翻译 - {error_content}"

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        error,
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        list(self.source_text_dict.values()), # 确保传递列表
                        list(response_dict.values()),      # 确保传递列表
                        self.extra_log,
                    )
                )
            )
        else:
            # --- 修改：使用 self.text_processor 实例 ---
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.text_processor.restore_all( # 使用实例调用
                self.config,restore_response_dict, self.prefix_codes, self.suffix_codes, self.placeholder_order,self.affix_whitespace_storage
            )
            # --- 修改 End ---

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                with item.atomic_scope():
                    item.model = model
                    item.translated_text = response
                    item.translation_status = CacheItem.STATUS.TRANSLATED

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        list(self.source_text_dict.values()), # 确保传递列表
                        list(response_dict.values()),      # 确保传递列表
                        self.extra_log,
                    )
                )
            )


        # 否则返回译文检查的结果
        if check_result == False:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }
        else:
            return {
                "check_result": check_result,
                "row_count": self.row_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }