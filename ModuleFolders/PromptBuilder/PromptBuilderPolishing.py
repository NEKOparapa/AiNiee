import re
from types import SimpleNamespace

from Base.Base import Base
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
class PromptBuilderPolishing(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderPolishing, "common_system_zh_s", None) == None:
            with open("./Resource/Prompt/Polishing/common_system_zh_s.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderPolishing.common_system_zh_s = reader.read().strip()
        if getattr(PromptBuilderPolishing, "common_system_zh_t", None) == None:
            with open("./Resource/Prompt/Polishing/common_system_zh_t.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderPolishing.common_system_zh_t = reader.read().strip()


        # 如果输入的是字典，则转换为命名空间
        if isinstance(config, dict):
            namespace = SimpleNamespace()
            for key, value in config.items():
                setattr(namespace, key, value)
            config = namespace


        # 构造结果
        if config == None:
            result = PromptBuilderPolishing.common_system_zh_t
        elif  config.polishing_mode_selection == "source_text_polish":
            result = PromptBuilderPolishing.common_system_zh_s
        elif  config.polishing_mode_selection == "target_text_polish":
            result = PromptBuilderPolishing.common_system_zh_t
        else:
            result = PromptBuilderPolishing.common_system_zh_t

        return result

    # 获取系统提示词
    def build_system(config: TaskConfig) -> str:

        # 获取默认系统提示词
        PromptBuilderPolishing.get_system_default(config)

        # 构造结果
        if config == None:
            result = PromptBuilderPolishing.common_system_zh_t
        elif  config.polishing_mode_selection == "source_text_polish":
            result = PromptBuilderPolishing.common_system_zh_s
        elif  config.polishing_mode_selection == "target_text_polish":
            result = PromptBuilderPolishing.common_system_zh_t
        else:
            result = PromptBuilderPolishing.common_system_zh_t

        return result

    # 构造术语表
    def build_glossary_prompt(config: TaskConfig, input_dict: dict) -> str:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = []
        for v in config.prompt_dictionary_data:
            src_lower = v.get("src").lower() # 将术语表中的 src 转换为小写
            if any(src_lower in line.lower() for line in lines): # 将原文行也转换为小写进行比较
                result.append(v)

        # 数据校验
        if len(result) == 0:
            return ""

        # 避免空的默认内容
        if len(result) == 1 and (result[0]["src"] == ""):
            return ""

        # 初始化变量，以免出错
        glossary_prompt_lines = []

        # 添加开头
        glossary_prompt_lines.append(
            "\n###术语表"
            + "\n" + "原文|译文|备注"
        )

        # 添加数据
        for v in result:
            glossary_prompt_lines.append(f"{v.get("src")}|{v.get("dst")}|{v.get("info") if v.get("info") != "" else " "}")


        # 拼接成最终的字符串
        glossary_prompt = "\n".join(glossary_prompt_lines)

        return glossary_prompt

    # 构造禁翻表
    def build_ntl_prompt(config: TaskConfig, source_text_dict) -> str:

        # 获取禁翻表内容
        exclusion_list_data = config.exclusion_list_data.copy()


        exclusion_dict = {}  # 用字典存储并自动去重
        texts = list(source_text_dict.values())
        
        # 处理正则匹配
        for element in exclusion_list_data:
            regex = element.get("regex", "").strip()
            marker = element.get("markers", "").strip()
            info = element.get("info", "")
            
            # 检查是否写正则，如果写了，只处理正则
            if regex:
                # 避免错误正则，导致崩溃
                try:
                    # 编译正则表达式字符串为模式对象
                    pattern = re.compile(regex)
                    # 寻找文本中所有符合正则的文本内容
                    for text in texts:
                        for match in pattern.finditer(text):
                            markers = match.group(0)
                            # 避免重复添加
                            if markers not in exclusion_dict: 
                                exclusion_dict[markers] = info
                except re.error:
                    pass
            # 没写正则，只处理标记符        
            else:
                found = any(marker in text for text in texts)
                if found and marker not in exclusion_dict:  # 避免重复添加
                    exclusion_dict[marker] = info
        
        # 检查内容是否为空
        if not exclusion_dict :
            return ""

        # 构建结果字符串
        result = "\n###禁翻表，以下特殊标记符无需翻译"+ "\n特殊标记符|备注"


        for markers, info in exclusion_dict.items():
            result += f"\n{markers}|{info}" if info else f"\n{markers}|"
        
        return result


    # 构造文风要求
    def build_writing_style(config: TaskConfig) -> str:
        # 获取自定义内容
        writing_style = config.polishing_style_content

        profile = "\n###润色风格"

        profile += f"\n{writing_style}\n"


        return profile



    # 携带原文上文
    def build_pre_text(config: TaskConfig, input_list: list[str]) -> str:
        profile = "###上文内容\n"

        # 使用列表推导式，转换为字符串列表
        formatted_rows = [item for item in input_list]

        # 使用换行符将列表元素连接成一个字符串
        profile += f"{"\n".join(formatted_rows)}\n"

        return profile

    # 构建润色原文的前缀:
    def build_source_prefix(config: TaskConfig) -> str:
        profile = " ###这是你接下来的润色任务，文本如下\n"

        return profile

    # 构建润色译文的前缀:
    def build_translated_prefix(config: TaskConfig) -> str:
        profile_A = " ###原文文本\n"

        profile_B = "###这是你接下来的润色任务，初译文本如下\n"

        return profile_A , profile_B

    # 生成信息结构 - 通用
    def generate_prompt(config, source_text_dict: dict, translation_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础系统提示词
        if config.polishing_prompt_selection["last_selected_id"]  == PromptBuilderEnum.POLISH_COMMON:
            system = PromptBuilderPolishing.build_system(config)
        else:
            system = config.polishing_prompt_selection["prompt_content"]  # 自定义提示词


        # 如果开启术语表
        if config.prompt_dictionary_switch == True:
            glossary = PromptBuilderPolishing.build_glossary_prompt(config, source_text_dict)
            if glossary != "":
                system += glossary
                extra_log.append(glossary)

        # 如果开启禁翻表
        if config.exclusion_list_switch == True:
            ntl = PromptBuilderPolishing.build_ntl_prompt(config, source_text_dict)
            if ntl != "":
                system += ntl
                extra_log.append(ntl)

        # 如果启用润色风格功能
        if config.polishing_style_switch == True:
            writing_style = PromptBuilderPolishing.build_writing_style(config)
            if writing_style != "":
                system += writing_style
                extra_log.append(writing_style)


        # 如果加上文，获取上文内容
        previous = ""
        if config.polishing_pre_line_counts and previous_text_list:
            previous = PromptBuilderPolishing.build_pre_text(config, previous_text_list)
            if previous != "":
                extra_log.append(f"###上文内容\n{"\n".join(previous_text_list)}")


        # 构建待翻译文本

        if config.polishing_mode_selection == "source_text_polish":

            source_text = PromptBuilder.build_source_text(config,source_text_dict)
            pre_prompt = PromptBuilderPolishing.build_source_prefix(config) # 用户提问前置文本

            source_text_str = f"{previous}\n{pre_prompt}<textarea>\n{source_text}\n</textarea>"

        elif config.polishing_mode_selection == "translated_text_polish":
            source_text = PromptBuilder.build_source_text(config,source_text_dict)
            translation_text = PromptBuilder.build_source_text(config,translation_text_dict)
            pre_prompt_A,pre_prompt_B = PromptBuilderPolishing.build_translated_prefix(config) # 用户提问前置文本

            source_text_str = f"{previous}\n{pre_prompt_A}\n{source_text}\n{pre_prompt_B}<textarea>\n{translation_text}\n</textarea>"


        # 构建用户信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        # 构建预输入回复信息
        switch_A = config.few_shot_and_example_switch # 打开动态示例开关时
        if switch_A :
            messages.append({"role": "assistant", "content": "我完全理解了你的要求，我将遵循您的指示进行润色任务。"})

        return messages, system, extra_log
