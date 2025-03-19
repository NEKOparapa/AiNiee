import re
from Base.Base import Base
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig


from DRWidget.TranslationExtractionCard.TranslationExtraction import TranslationExtraction
from DRWidget.GlossaryExtractionCard.GlossaryExtraction import GlossaryExtraction
from DRWidget.NoTranslateListExtractionCard.NoTranslateListExtraction import NoTranslateListExtraction
from DRWidget.RegexExtractionCard.RegexExtraction import RegexExtractor
from DRWidget.TagExtractionCard.TagExtraction import TagExtractor



class PromptBuilderDouble(Base):
    def __init__(self) -> None:
        super().__init__()


    # 获取双请求专用原文
    def get_source_text(self,source_text_dict: dict) -> str:

        # 构建待翻译文本 (添加序号)
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            # 检查是否为多行文本
            if "\n" in line:
                lines = line.split("\n")
                for sub_index, sub_line in enumerate(lines):
                    numbered_text = f"{index + 1}.{sub_index + 1}.{sub_line}"
                    numbered_lines.append(numbered_text)
            else:
                # 单行文本直接添加序号
                numbered_lines.append(f"{index + 1}.{line}")

        source_text_str = "\n".join(numbered_lines)

        return source_text_str


    # 获取双请求专用上文
    def get_previous_text(self,input_list: list[str]) -> str:

        profile = ""

        if input_list:
            # 使用列表推导式，转换为字符串列表
            formatted_rows = [item for item in input_list]

            # 使用换行符将列表元素连接成一个字符串
            profile += f"\n{"\n".join(formatted_rows)}\n"

        return profile

    # 获取双请求专用术语表
    def get_glossary(self,config: TranslatorConfig, input_dict: dict) -> str:

        # 读取配置文件
        config_user = self.load_config()
        prompt_dictionary_data = config_user["prompt_dictionary_data"].copy() 

        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = []
        for v in prompt_dictionary_data:
            src_lower = v.get("src").lower() # 将术语表中的 src 转换为小写
            if any(src_lower in line.lower() for line in lines): # 将原文行也转换为小写进行比较
                result.append(v)


        # 数据校验
        if len(result) == 0:
            return ""

        # 初始化变量，以免出错
        glossary_prompt_lines = []

        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            # 添加开头
            glossary_prompt_lines.append(
            ("\n" + "原文|译文|备注")
            )

            # 添加数据
            for v in result:
                glossary_prompt_lines.append(f"{v.get("src")}|{v.get("dst")}|{v.get("info") if v.get("info") != "" else " "}")

        else:
            # 添加开头
            glossary_prompt_lines.append(
            ("\n" + "Original Text|Translation|Remarks")
            )

            # 添加数据
            for v in result:
                glossary_prompt_lines.append(f"{v.get("src")}|{v.get("dst")}|{v.get("info") if v.get("info") != "" else " "}")


        # 拼接成最终的字符串
        glossary_prompt = "\n".join(glossary_prompt_lines)

        return glossary_prompt

    # 获取双请求专用禁翻表
    def build_ntl_prompt(self,config: TranslatorConfig, source_text_dict) -> str:

        # 读取配置文件
        config_user = self.load_config()
        exclusion_list_data = config_user["exclusion_list_data"].copy()


        exclusion_dict = {}  # 用字典存储并自动去重
        texts = list(source_text_dict.values())
        
        # 处理正则匹配
        for element in exclusion_list_data:
            regex = element.get("regex", "").strip()
            info = element.get("info", "")
            
            if regex:
                try:
                    pattern = re.compile(regex)
                    for text in texts:
                        for match in pattern.finditer(text):
                            markers = match.group(0)
                            if markers not in exclusion_dict:
                                exclusion_dict[markers] = info
                except re.error:
                    pass
        
        # 处理示例检查
        for element in exclusion_list_data:
            markers = element.get("markers", "").strip()
            info = element.get("info", "")
            
            if markers:
                # 检查示例是否存在于任意文本中
                found = any(markers in text for text in texts)
                if found and markers not in exclusion_dict:
                    exclusion_dict[markers] = info
        
        # 检查内容是否为空
        if not exclusion_dict :
            return ""

        # 构建结果字符串
        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = "\n标记符|备注"
        else:
            result = "\nMarker|Remarks"

        for markers, info in exclusion_dict.items():
            result += f"\n{markers}|{info}" if info else f"\n{markers}|"
        
        return result

    # 占位符替换
    def replace_message_content(self, replace_dict,messages, text=None):
        """
        根据替换字典对消息列表中的content字段及可选文本变量进行文本替换。
        
        参数:
        messages (list): OpenAI SDK格式的消息列表，每个消息是包含'role'和'content'的字典。
        replace_dict (dict): 替换规则字典，键为待替换文本，值为新文本。若值为空字符串则跳过替换。
        text (str, optional): 需要替换的额外文本变量，默认为None。
        
        返回:
        tuple: 包含两个元素的元组：
            - list: 替换后的消息列表
            - str: 替换后的文本变量（如果text参数被提供），否则为None
        """
        # 处理消息列表
        for message in messages:
            content = message.get('content', '')
            if content:
                new_content = content
                for old, new in replace_dict.items():
                    if new:
                        new_content = new_content.replace(old, new)
                message['content'] = new_content
        
        # 处理文本变量
        replaced_text = ""
        if text is not None:
            if text:  # 仅当文本非空时进行替换
                new_text = text
                for old, new in replace_dict.items():
                    if new:
                        new_text = new_text.replace(old, new)
                replaced_text = new_text
            else:
                replaced_text = text  # 保留空字符串
        
        return messages, replaced_text

    # 文本提取阶段
    def process_extraction_phase(self,config: TranslatorConfig,replace_dict,response_think,response_content,extra_logs):
        """处理提取阶段"""
        # 获取配置
        flow_design_list_config = config.flow_design_list

        # 提取器映射表
        self.EXTRACTOR_HANDLERS = {
            "TranslationExtraction":  PromptBuilderDouble._handle_translation_extraction,
            "ResponseExtraction": PromptBuilderDouble._handle_response_extraction,
            "ThoughtExtraction": PromptBuilderDouble._handle_think_extraction,
            "GlossaryExtraction": PromptBuilderDouble._handle_glossary_extraction,
            "NoTranslateListExtraction": PromptBuilderDouble._handle_NTL_extraction,
            "TagExtraction": PromptBuilderDouble._handle_tag_extraction,
            "RegexExtraction": PromptBuilderDouble._handle_rex_extraction
        }

        
        for card in flow_design_list_config["extraction_phase"]:
            extractor_type = card["settings"]["extractor_type"]
            handler = self.EXTRACTOR_HANDLERS.get(extractor_type)
            
            if handler:
                # 提取文本
                result =  handler(self,response_content,response_think,card["settings"])
                # 提取占位符
                placeholder = card["settings"]["placeholder"]

                # 更新到替换字典里
                if result:
                    replace_dict[placeholder] = result
                    extra_logs.append((placeholder + ":\n" + result+ "\n" ))

                card["settings"]["system_info"] = result
        

        return replace_dict,extra_logs
    

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
        text = Extraction.extract_tag(content,settings)
        return text
    
    def _handle_rex_extraction(self, content: str, think: str, settings: dict) -> str:
        """标签提取实现"""
        Extraction = RegexExtractor()
        text = Extraction.extract_rex(content,settings)
        return text
