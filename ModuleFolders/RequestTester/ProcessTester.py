import json
import os
import re
import threading
import textwrap

from Base.Base import Base

from DRWidget.TranslationExtractionCard.TranslationExtraction import TranslationExtraction
from DRWidget.GlossaryExtractionCard.GlossaryExtraction import GlossaryExtraction
from DRWidget.NoTranslateListExtractionCard.NoTranslateListExtraction import NoTranslateListExtraction
from DRWidget.RegexExtractionCard.RegexExtraction import RegexExtractor
from DRWidget.TagExtractionCard.TagExtraction import TagExtractor
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester


# 改进点：不支持亚马逊云平台接口
class ProcessTester(Base):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 提取器映射表
        self.EXTRACTOR_HANDLERS = {
            "TranslationExtraction": self._handle_translation_extraction,
            "ResponseExtraction": self._handle_response_extraction,
            "ThoughtExtraction": self._handle_think_extraction,
            "GlossaryExtraction": self._handle_glossary_extraction,
            "NoTranslateListExtraction": self._handle_NTL_extraction,
            "TagExtraction": self._handle_tag_extraction,
            "RegexExtraction": self._handle_rex_extraction
        }

        # 全局文本替换表
        self.rex_list = {
            "{original_text}": "测试文本",
            "{previous_text}": "测试文本",
            "{glossary}": "测试文本",
            "{code_text}": "测试文本",
        }

        # 订阅流程测试开始事件
        self.subscribe(Base.EVENT.NEW_PROCESS_START, self.run_test_start)

    # 响应测试开始事件
    def run_test_start(self, event: int, data: dict):
        thread = threading.Thread(target=self.run_test, args=(event, data))
        thread.start()

    # 测试方法框架
    def run_test(self, event, config):
        success = False
        result = config  # 结果存储字典，本质还是原来的配置结构，只是更新其中的某些字段

        # 实现具体的流程测试逻辑
        try:
            # 实现具体的流程测试逻辑
            result, success = self.test_processor(config)

        except Exception as e:
            self.error("流程测试失败", e)

        # 触发事件，并返回数据
        self.emit(Base.EVENT.NEW_PROCESS_DONE, {
            "success": success,
            "result": result
        })

    # 具体测试方法
    def test_processor(self, config):

        breakpoint = int(config["test_target_breakpoint_position"])
        result = {}

        # 阶段1：第一个请求
        try:
            if breakpoint >= 1:

                self.print("\n\n")
                self.info("正在进行第一次请求测试-----------------------------------------")
                self.print("")

                result = self._process_phase_a(config)
                if breakpoint == 1:
                    return result, True
        except Exception as e:
            self.error("第一次请求测试失败", e)
            return result, False

        # 阶段2：提取阶段
        try:
            if breakpoint >= 2:

                # 打印日志
                self.print("\n\n")
                self.info("正在进行提取阶段测试-----------------------------------------")

                # 进行文本提取
                result = self._process_extraction_phase(config)

                # 打印日志
                self.log_rex_list()
                self.print("")

                if breakpoint == 2:
                    return result, True


        except Exception as e:
            self.error("提取流程测试失败", e)
            return result, False

            # 阶段3：第二个请求

        try:
            if breakpoint >= 3:
                self.print("\n\n")
                self.info("正在进行第二次请求测试-----------------------------------------")
                self.print("")

                result = self._process_phase_b(config)
        except Exception as e:
            self.error("第二次请求测试失败", e)
            return result, False

        return result, True

    # 处理第一阶段
    def _process_phase_a(self, config):

        # 初始化测试用文本
        self.rex_list = self.get_flow_Basic_settings()

        return self._generic_process_phase(config, "a")

    # 处理提取阶段
    def _process_extraction_phase(self, config):
        """处理提取阶段"""
        response_content = config["request_a_response_content"]
        response_think = config["request_a_response_think"]

        for card in config["extraction_phase"]:
            extractor_type = card["settings"]["extractor_type"]
            handler = self.EXTRACTOR_HANDLERS.get(extractor_type)

            if handler:
                # 提取文本
                result = handler(response_content, response_think, card["settings"])
                # 提取占位符
                placeholder = card["settings"]["placeholder"]

                # 更新到替换列表里
                if result:
                    self.rex_list[placeholder] = result

                card["settings"]["system_info"] = result

        config["actual_running_breakpoint_position"] = "2"

        return config

    # 处理第二阶段
    def _process_phase_b(self, config):
        return self._generic_process_phase(config, "b")

    def _generic_process_phase(self, config, phase_flag):
        """通用请求处理阶段"""
        # 获取平台配置
        platform_config = self.get_platform_config(phase_flag)

        # 构建消息列表
        messages, system_content = self._build_messages(config[f"request_phase_{phase_flag}"])

        # ================== 请求阶段日志 ==================

        if system_content:
            self.info("[系统提示词]\n")
            self.print(f"{system_content.strip()}\n")

        self.info("[消息内容]")
        self.print(json.dumps(messages, indent=2, ensure_ascii=False))  # 结构化JSON输出
        self.info("\n⌛ 正在进行接口请求...")

        # ================== 执行API调用 ==================


        #尝试请求
        requester = LLMRequester()
        skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
            messages,
            system_content,
            platform_config
        )

        # ================== 响应阶段日志 ==================
        self.print("")
        self.info(f"接口响应结果")

        if response_think:
            self.info("[思考过程]\n")
            self.print(f"{response_think.strip()}\n")

        self.info("[回复内容]\n")
        self.print(f"{response_content.strip()}\n")

        # 保存响应结果
        config[f"request_{phase_flag}_response_content"] = response_content
        config[f"request_{phase_flag}_response_think"] = response_think
        config["actual_running_breakpoint_position"] = phase_flag

        return config

    def _build_messages(self, request_cards):
        """构建通用消息结构"""
        messages = []
        system_content = ""

        for card in request_cards:
            if card["type"] == "DialogueFragmentCard":
                settings = card["settings"]

                role = settings["role"]
                content = settings["content"]

                # 替换文本占位符
                content = self.replace_content(self.rex_list, content)

                # 记录系统消息
                if role == "system":
                    system_content = content

                messages.append({
                    "role": role,
                    "content": content
                })
                settings["system_info"] = content

        return messages, system_content


    # 提取处理方法的实现
    def _handle_translation_extraction(self, content: str, think: str, settings: dict) -> str:
        """翻译提取实现"""
        Extraction = TranslationExtraction()
        text = Extraction.extract_tag(content)
        return text

    def _handle_response_extraction(self, content: str, think: str, settings: dict) -> str:
        """响应提取实现"""
        text = content
        return text

    def _handle_think_extraction(self, content: str, think: str, settings: dict) -> str:
        """思考提取实现"""
        text = think
        return text

    def _handle_glossary_extraction(self, content: str, think: str, settings: dict) -> str:
        """术语表提取实现"""
        Extraction = GlossaryExtraction()
        text = Extraction.extract_tag(content)
        return text

    def _handle_NTL_extraction(self, content: str, think: str, settings: dict) -> str:
        """禁翻表提取实现"""
        Extraction = NoTranslateListExtraction()
        text = Extraction.extract_tag(content)
        return text

    def _handle_tag_extraction(self, content: str, think: str, settings: dict) -> str:
        """标签提取实现"""
        Extraction = TagExtractor()
        text = Extraction.extract_tag(content, settings)
        return text

    def _handle_rex_extraction(self, content: str, think: str, settings: dict) -> str:
        """正则提取实现"""
        Extraction = RegexExtractor()
        text = Extraction.extract_rex(content, settings)
        return text

    # 获取配置信息
    def get_platform_config(self, platform):
        """获取指定平台的配置信息"""
        # 读取配置文件
        user_config = self.load_config()

        # 获取平台配置标识
        platform_tag = user_config.get(f"request_{platform}_platform_settings")

        # 读取平台基础配置
        platform_config = user_config["platforms"][platform_tag]
        api_url = platform_config["api_url"]
        api_keys = platform_config["api_key"]
        api_format = platform_config["api_format"]
        region = platform_config.get("region", "")
        access_key = platform_config.get("access_key", "")
        secret_key = platform_config.get("secret_key", "")
        model_name = platform_config["model"]
        extra_body = platform_config.get("extra_body", {})
        think_switch = platform_config.get("think_switch")
        think_depth = platform_config.get("think_depth")

        # 处理API密钥（取第一个有效密钥）
        cleaned_keys = re.sub(r"\s+", "", api_keys)
        api_key = cleaned_keys.split(",")[0] if cleaned_keys else ""

        # 自动补全API地址
        auto_complete = platform_config["auto_complete"]
        if (platform_tag == "sakura" or platform_tag == "LocalLLM")  and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"


        # 结构化输出请求参数
        self.info("[接口参数]")
        self.print(f"  → 接口地址: {api_url}")
        self.print(f"  → 模型名称: {model_name}")
        self.print(f"  → 额外参数: {extra_body}")
        self.print(f"  → 接口密钥: {'*' * (len(api_key) - 4)}{api_key[-4:]}")  # 隐藏敏感信息

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
            "think_switch":  think_switch,
            "think_depth": think_depth
        }


        return platform_config

    # 构建初始替换表
    def get_flow_Basic_settings(self):
        # 读取配置文件
        user_config = self.load_config()

        # 读取平台基础配置
        test_original_text = user_config["test_original_text"]
        test_preceding_text = user_config["test_preceding_text"]
        test_glossary = user_config["test_glossary"]
        test_no_translate_list = user_config["test_no_translate_list"]

        result = {
            "{original_text}": test_original_text,
            "{previous_text}": test_preceding_text,
            "{glossary}": test_glossary,
            "{code_text}": test_no_translate_list,
        }

        return result

    # 文本替换方法
    def replace_content(self, replace_dict, text=None):

        # 处理文本变量
        replaced_text = None
        if text is not None:
            if text:  # 仅当文本非空时进行替换
                new_text = text
                for old, new in replace_dict.items():
                    if new:
                        new_text = new_text.replace(old, new)
                replaced_text = new_text
            else:
                replaced_text = text  # 保留空字符串

        return replaced_text

    # 替换字典日志打印方法
    def log_rex_list(self):
        """优化后的结构化日志输出 (无右对齐，字典项间空行)"""
        # 基础参数配置
        max_key_width = max(len(str(k)) for k in self.rex_list.keys())  # 自动计算最大键长
        line_width = 80  # 每行最大字符数
        indent = ' ' * 4  # 换行缩进量

        # 构建日志内容
        log_lines = ["=" * line_width]
        log_lines.append("📖 字典内容 (共 {} 项)".format(len(self.rex_list)))
        log_lines.append("-" * line_width)

        for i, (key, value) in enumerate(self.rex_list.items(), 1):
            # 键值对基础行
            key_str = f"[{i}] {key}".ljust(max_key_width + 4)  # 带序号的键
            value_lines = textwrap.wrap(str(value), width=line_width)  # 使用固定行宽进行wrap

            # 首行特殊处理
            log_lines.append(f"{key_str} : {value_lines[0]}" if value_lines else f"{key_str} : ")

            # 后续换行处理，统一缩进
            for line in value_lines[1:]:
                log_lines.append(indent + line)  # 统一使用 indent 进行缩进

            log_lines.append("")  # 添加空行

        log_lines.append("=" * line_width)

        # 输出日志
        self.info("文本替换表内容:\n" + "\n".join(log_lines))
