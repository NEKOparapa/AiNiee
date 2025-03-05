import copy
import os
import re
import time
import itertools

import rapidjson as json
from rich import box
from rich.table import Table
from typing import List, Dict, Tuple

from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig
from ModuleFolders.Translator.TranslatorRequester import TranslatorRequester
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderThink import PromptBuilderThink
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.PromptBuilder.PromptBuilderDouble import PromptBuilderDouble
from ModuleFolders.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Cache.CacheManager import CacheManager



class TranslatorTask(Base):

    def __init__(self, config: TranslatorConfig, plugin_manager: PluginManager, 
                 request_limiter: RequestLimiter, cache_manager: CacheManager) -> None:
        super().__init__()

        self.config = config
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter
        self.cache_manager = cache_manager

        # 初始化消息存储
        self.messages = []
        self.messages_a = []  
        self.messages_b = []    
        self.system_prompt = ""  
        self.system_prompt_a = ""  
        self.system_prompt_b = ""  
        self.regex_dir = "./Resource/Regex/regex.json" 

        # 初始化辅助数据结构
        self.extra_log = []
        self.replace_dict = {}
        # 占位符顺序存储结构
        self.placeholder_order = {}

        # 预处理正则表达式
        self.code_pattern_list = self._prepare_regex_patterns()
        self.prefix_pattern, self.suffix_pattern = self._build_patterns()


    def _load_regex_patterns(self, json_file_path: str) -> List[str]:
        """从JSON文件加载正则表达式"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [item["regex"] for item in data if isinstance(item, dict) and "regex" in item]
        except Exception as e:
            print(f"加载正则表达式失败: {str(e)}")
            return []


    def _prepare_regex_patterns(self) -> List[str]:
        """准备所有需要使用的正则表达式模式"""
        patterns = []

        # 从文件加载基础正则
        file_patterns = self._load_regex_patterns(self.regex_dir)
        patterns.extend(file_patterns)

        # 处理禁翻表数据
        exclusion_patterns = []
        for item in self.config.exclusion_list_data:
            if regex := item.get("regex"):
                exclusion_patterns.append(regex)
            else:
                # 转义特殊字符并添加为普通匹配
                exclusion_patterns.append(re.escape(item["markers"]))
        patterns.extend(exclusion_patterns)

        return patterns

    def _build_patterns(self) -> Tuple[re.Pattern, re.Pattern]:
        """构建前后缀正则表达式对象"""
        if not self.code_pattern_list:
            return re.compile(""), re.compile("")

        # 为每个模式添加空白匹配能力
        enhanced_patterns = [
            fr"\s*{p}\s*"  # 允许前后有任意空白
            if not any(c in p for c in ("^", "$", "\\s"))  # 避免重复空白匹配
            else p
            for p in self.code_pattern_list
        ]

        combined = "|".join(enhanced_patterns)
        return (
            re.compile(fr"^(?:{combined})+", re.IGNORECASE|re.MULTILINE),
            re.compile(fr"(?:{combined})+$", re.IGNORECASE|re.MULTILINE)
        )


    def _build_special_placeholder_pattern(self) -> re.Pattern:
        """构建特殊占位符匹配的正则表达式"""
        enhanced_patterns = []
        for p in self.code_pattern_list:
            # 若模式不包含边界或空白控制，则添加空白匹配
            if not any(c in p for c in ("^", "$", "\\s")):
                enhanced = fr"\s*{p}\s*"
            else:
                enhanced = p
            enhanced_patterns.append(enhanced)
        combined = "|".join(enhanced_patterns)
        return re.compile(combined, re.IGNORECASE | re.MULTILINE)


    def replace_all(self, target_platform, text_dict: Dict[str, str], prefix_pattern: re.Pattern, suffix_pattern: re.Pattern) -> Tuple[Dict[str, str], Dict, Dict]:
        """执行全部替换操作"""
        processed = {k: v for k, v in text_dict.items()}
        prefix_codes, suffix_codes = {}, {}
        
        # 初始化占位符字典
        self.placeholder_order.clear()

        if self.config.auto_process_text_code_segment:
            # 处理前后缀
            processed, prefix_codes, suffix_codes = self._process_affixes(
                processed, prefix_pattern, suffix_pattern)
            
            # 新增特殊文本占位替换
            processed = self._replace_special_placeholders(target_platform,processed)

        if self.config.pre_translation_switch:
            processed = self.replace_before_translation(processed)

        return processed, prefix_codes, suffix_codes

    def restore_all(self, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict) -> Dict[str, str]:
        """执行全部还原操作"""
        restored = text_dict.copy()

        if self.config.auto_process_text_code_segment:
            restored = self._restore_affixes(restored, prefix_codes, suffix_codes)
            restored = self._restore_special_placeholders(restored)

        if self.config.post_translation_switch:
            restored = self.replace_after_translation(restored)

        return restored

    def _replace_special_placeholders(self, target_platform, text_dict: Dict[str, str]) -> Dict[str, str]:
        """特殊文本占位替换

        Args:
            target_platform: 目标平台名称，例如 "sakura" 或其他
            text_dict: 包含文本的字典

        Returns:
            替换占位符后的文本字典
        """
        pattern = self._build_special_placeholder_pattern()

        new_dict = {}
        for key, text in text_dict.items():
            placeholders: List[Dict[str, str]] = []
            count = 0  # 用于跟踪替换次数

            def replacer(match: re.Match) -> str:
                nonlocal count
                if count >= 3:
                    return match.group()  # 超过3次不替换

                original = match.group()
                count += 1
                if target_platform == "sakura":
                    # Sakura 平台使用下箭头，并根据 count 增加数量
                    placeholder = "↓" * count
                else:
                    # 其他平台使用原始的占位符格式
                    placeholder = f"""{{_placeholder{count}_}}"""

                # 记录占位符和原始文本的映射关系
                placeholders.append({
                    "placeholder": placeholder,
                    "original": original
                })
                return placeholder

            # 执行正则替换并保存映射关系
            processed_text = pattern.sub(replacer, text)
            self.placeholder_order[key] = placeholders
            new_dict[key] = processed_text

        return new_dict
    

    def _restore_special_placeholders(self, text_dict: Dict[str, str]) -> Dict[str, str]:
        """占位符还原"""

        new_dic = {}

        for key, text in text_dict.items():
            placeholders = self.placeholder_order.get(key, [])
            
            if not placeholders:
                new_dic[key] = text

            else:
                for item in placeholders:
                    placeholder_text = item.get("placeholder")
                    original_text = item.get("original") 

                    text = text.replace(placeholder_text, original_text, 1)

                new_dic[key] = text
        
        # 检查未能正确替换用
        for value in new_dic.values():
            if isinstance(value, str): 
                placeholder_pattern = r'placeholder'

                if re.search(placeholder_pattern, value):
                    pass
                    #print("bug------")


        return new_dic



    def _process_affixes(self, text_dict: Dict[str, str], prefix_pat: re.Pattern, suffix_pat: re.Pattern) -> Tuple[Dict[str, str], Dict, Dict]:
        """处理前后缀提取"""
        prefixes = {}
        suffixes = {}
        
        for key, text in text_dict.items():
            # 前缀提取（保留原始空白）
            prefix_matches = []
            while (match := prefix_pat.search(text)) and match.start() == 0:
                prefix_matches.append(match.group())  # 保留原始内容（包括换行符）
                text = text[match.end():]
            prefixes[key] = prefix_matches

            # 后缀提取（保留原始空白）
            suffix_matches = []
            while (match := suffix_pat.search(text)) and match.end() == len(text):
                suffix_matches.insert(0, match.group())  # 保留原始内容
                text = text[:match.start()]
            suffixes[key] = suffix_matches

            # 检查中间文本是否为空,避免提取完前后缀后内容为空（暂时解决方法）
            if not text:
                has_prefix = len(prefix_matches) > 0
                has_suffix = len(suffix_matches) > 0

                if has_prefix and has_suffix:
                    # 比较总字符长度
                    prefix_len = sum(len(p) for p in prefix_matches)
                    suffix_len = sum(len(s) for s in suffix_matches)
                    
                    if prefix_len <= suffix_len:
                        # 还原前缀并清空
                        text = ''.join(prefix_matches)
                        prefixes[key] = []
                    else:
                        # 还原后缀并清空
                        text = ''.join(suffix_matches)
                        suffixes[key] = []
                elif has_prefix:
                    # 仅还原前缀
                    text = ''.join(prefix_matches)
                    prefixes[key] = []
                elif has_suffix:
                    # 仅还原后缀
                    text = ''.join(suffix_matches)
                    suffixes[key] = []

            text_dict[key] = text

        return text_dict, prefixes, suffixes


    def _restore_affixes(self, text_dict: Dict[str, str], prefixes: Dict, suffixes: Dict) -> Dict[str, str]:
        """还原前后缀（保留原始空白）"""
        for key in text_dict:
            # 直接拼接保留原始空白
            prefix_str = ''.join(prefixes.get(key, []))
            suffix_str = ''.join(suffixes.get(key, []))
            
            # 保留中间内容的原始前后空白
            restored = f"{prefix_str}{text_dict[key]}{suffix_str}"
            text_dict[key] = restored
            
        return text_dict


    # 译后替换
    def replace_before_translation(self, text_dict: dict) -> dict:
        data: list[dict] = self.config.pre_translation_data

        for k in text_dict:
            for v in data:
                if v.get("src", "") in text_dict[k]:
                    text_dict[k] = text_dict[k].replace(v.get("src", ""), v.get("dst", ""))

        return text_dict

    # 译前替换
    def replace_after_translation(self, text_dict: dict) -> dict:
        data: list[dict] = self.config.post_translation_data

        for k in text_dict:
            for v in data:
                if v.get("src", "") in text_dict[k]:
                    text_dict[k] = text_dict[k].replace(v.get("src", ""), v.get("dst", ""))

        return text_dict


    # 设置缓存数据
    def set_items(self, items: list[CacheItem]) -> None:
        self.items = items

    # 设置上文数据
    def set_previous_items(self, previous_items: list[CacheItem]) -> None:
        self.previous_items = previous_items

    # 消息构建预处理
    def prepare(self, target_platform: str, prompt_preset: int) -> None:

        # 生成上文文本列表
        self.previous_text_list = [v.get_source_text() for v in self.previous_items]

        # 生成原文文本字典
        self.source_text_dict = {str(i): v.get_source_text() for i, v in enumerate(self.items)}

        # 生成文本行数信息
        self.row_count = len(self.source_text_dict)

        # 触发插件事件 - 文本正规化
        self.plugin_manager.broadcast_event("normalize_text", self.config, self.source_text_dict)

        # 各种替换步骤，译前替换，提取首位代码段
        self.source_text_dict, self.prefix_codes, self.suffix_codes = self.replace_all(target_platform, self.source_text_dict, self.prefix_pattern, self.suffix_pattern)

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
        elif prompt_preset in (PromptBuilderEnum.THINK,):
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_think(
                self.source_text_dict,
                self.previous_text_list
            )
        elif prompt_preset in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT, PromptBuilderEnum.CUSTOM):
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt(
                self.source_text_dict,
                self.previous_text_list
            )

        # 预估 Token 消费,暂时版本，双请求无法正确计算tpm与tokens消耗
        self.request_tokens_consume = self.request_limiter.calculate_tokens(
            self.messages,
            self.messages_a, 
            self.messages_b,   
            self.system_prompt,
            self.system_prompt_a,
            self.system_prompt_b
            )

    # 生成指令
    def generate_prompt(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:
            system = self.config.system_prompt_content
        else:
            system = PromptBuilder.build_system(self.config)

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

        # 获取默认示例前置文本
        pre_prompt = PromptBuilder.build_userExamplePrefix(self.config)
        fol_prompt = PromptBuilder.build_modelExamplePrefix(self.config)

        # 获取默认示例，并构建动态few-shot
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

        # 获取提问时的前置文本
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config)
        # 获取模型预输入回复前文
        fol_prompt = PromptBuilder.build_modelResponsePrefix(self.config)

        # 构建待翻译文本 (添加序号)
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            numbered_lines.append(f"{index + 1}. {line}") # 添加序号和 "." 分隔符
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
        messages.append({"role": "assistant", "content": fol_prompt})


        return messages, system, extra_log

    # 生成指令 - 思考模型
    def generate_prompt_think(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:
            system = self.config.system_prompt_content
        else:
            system = PromptBuilderThink.build_system(self.config)

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


        # 如果角色介绍开关打开
        if self.config.characterization_switch == True:
            characterization = PromptBuilder.build_characterization(self.config, source_text_dict)
            if characterization:
                system += characterization
                extra_log.append(characterization)

        # 如果启用自定义世界观设定功能
        if self.config.world_building_switch == True:
            world_building = PromptBuilder.build_world_building(self.config)
            if world_building:
                system += world_building
                extra_log.append(world_building)

        # 如果启用自定义行文措辞要求功能
        if self.config.writing_style_switch == True:
            writing_style = PromptBuilder.build_writing_style(self.config)
            if writing_style:
                system += writing_style
                extra_log.append(writing_style)

        # 如果启用翻译风格示例功能
        if self.config.translation_example_switch == True:
            translation_example = PromptBuilder.build_translation_example(self.config)
            if translation_example:
                system += translation_example
                extra_log.append(translation_example)


        # 如果加上文，获取上文内容
        previous = ""
        if self.config.pre_line_counts and previous_text_list:
            previous = PromptBuilder.build_pre_text(self.config, previous_text_list)
            if previous:
                extra_log.append(f"###上文\n{"\n".join(previous_text_list)}")

        # 获取提问时的前置文本
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config)


        # 构建待翻译文本
        source_text_str = "\n".join(source_text_dict.values())
        source_text_str = f"{previous}\n{pre_prompt}<textarea>\n{source_text_str}\n</textarea>"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        return messages, system, extra_log

    # 生成指令 Sakura
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

    # 生成指令 LocalLLM
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


        # 构建待翻译文本
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            numbered_lines.append(f"{index + 1}. {line}") # 添加序号和 "." 分隔符
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
                role_mapping = {
                    "系统": "system",
                    "用户": "user",
                    "模型": "assistant"
                }

                role = role_mapping.get(settings["role"], "user")
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
                role_mapping = {
                    "系统": "system",
                    "用户": "user",
                    "模型": "assistant"
                }

                role = role_mapping.get(settings["role"], "user")
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

    # 更新系统提示词的术语表内容(因为是特殊处理的补丁，很多判断要重新加入，后续提示词相关更新需要重点关注该函数，以免bug)
    def update_sysprompt_glossary(self,config,system_prompt, prompt_dictionary_data, source_text_dict):

        # 应用开关检查
        if config.prompt_dictionary_switch == False:
            return system_prompt
        
        # 本地接口不适用
        if config.target_platform == "sakura":
            return system_prompt

        if config.target_platform == "LocalLLM":
            return system_prompt


        # 生成符合条件的术语条目
        entries = []
        for item in prompt_dictionary_data:
            src = item.get("src", "")
            # 检查原文是否在任意源文本中出现
            if any(src in text for text in source_text_dict.values()):
                dst = item.get("dst", "")
                info = item.get("info", "")
                entries.append(f"{src}|{dst}|{info}")
        
        # 构建新术语表
        if config.target_language in ("简中", "繁中"):
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
        for source, translated in itertools.zip_longest(source, translated, fillvalue = ""):
            pair = pair + "\n" + f"{source} [bright_blue]-->[/] {translated}"
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
                table.add_row(row)
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
        self.system_prompt = self.update_sysprompt_glossary(self.config,self.system_prompt, self.config.prompt_dictionary_data, self.source_text_dict)

        # 发起请求
        requester = TranslatorRequester(self.config, self.plugin_manager)
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
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config.response_check_switch,
            response_content,
            response_dict,
            self.source_text_dict,
            self.config.source_language
        )

        # 模型回复日志
        if response_think != "":
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
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )
        else:
            # 各种还原步骤
            # 先复制一份，以免影响原有数据，response_dict 为字符串字典，所以浅拷贝即可
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.restore_all(restore_response_dict, self.prefix_codes, self.suffix_codes)

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                item.set_model(self.config.model)
                item.set_translated_text(response)
                item.set_translation_status(CacheItem.STATUS.TRANSLATED)

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
                        self.source_text_dict.values(),
                        response_dict.values(),
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
        requester = TranslatorRequester(self.config, self.plugin_manager)
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
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)
        # 更新术语表与禁翻表到配置文件中
        self.config.update_glossary_ntl_config(glossary_result, NTL_result)


        # 模型回复日志
        if response_think != "":
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
        requester = TranslatorRequester(self.config, self.plugin_manager)
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
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config.response_check_switch,
            response_content,
            response_dict,
            self.source_text_dict,
            self.config.source_language
        )

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
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )
        else:
            # 各种还原步骤
            # 先复制一份，以免影响原有数据，response_dict 为字符串字典，所以浅拷贝即可
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.restore_all(restore_response_dict, self.prefix_codes, self.suffix_codes)

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                item.set_model(model)
                item.set_translated_text(response)
                item.set_translation_status(CacheItem.STATUS.TRANSLATED)

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
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

