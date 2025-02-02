from Base.Base import Base
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class PromptBuilderThink(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取系统提示词
    def build_system(config: TranslatorConfig) -> str:
        # 如果没有读取系统提示词，则从文件读取
        if getattr(PromptBuilderThink, "system", None) == None:
            with open("./Prompt/think_system.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderThink.system = reader.read().strip()

        # 根据源语言构造结果
        if config.target_language == "简中":
            result = PromptBuilderThink.system.replace("{target_language}", "简体中文")
        elif config.target_language == "繁中":
            result = PromptBuilderThink.system.replace("{target_language}", "繁體中文")
        else:
            result = PromptBuilderThink.system.replace("{target_language}", config.target_language)

        return result

    # 构造术语表
    def build_glossary(config: TranslatorConfig, input_dict: dict) -> tuple[str, str]:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = [
            v for v in config.prompt_dictionary_data
            if any(v.get("src") in lines for lines in lines)
        ]

        # 构建文本
        dict_lines = []
        for item in result:
            src = item.get("src", "")
            dst = item.get("dst", "")
            info = item.get("info", None)

            if info == None:
                dict_lines.append(f"{src} -> {dst}")
            else:
                dict_lines.append(f"{src} -> {dst} #{info}")

        # 返回结果
        if dict_lines == []:
            return ""
        else:
            return (
                "术语表："
                + "\n" + "\n".join(dict_lines)
            )

    # 构造角色介绍
    def build_characterization(config: TranslatorConfig, input_dict: dict) -> tuple[str, str]:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = [
            v for v in config.characterization_data
            if any(v.get("original_name") in lines for lines in lines)
        ]

        # 构建文本
        dict_lines = []
        for item in result:
            original_name = item.get("original_name", "")
            translated_name = item.get("translated_name", "")
            gender = item.get("gender", "")
            age = item.get("age", "")
            personality = item.get("personality", "")
            speech_style = item.get("speech_style", "")
            additional_info = item.get("additional_info", "")

            line = ""
            if original_name != "":
                line = line + f"{original_name}" + "，"
            if translated_name != "":
                line = line + f"译名：{translated_name}" + "，"
            if gender != "":
                line = line + f"性别：{gender}" + "，"
            if age != "":
                line = line + f"年龄：{age}" + "，"
            if personality != "":
                line = line + f"性格：{personality}" + "，"
            if speech_style != "":
                line = line + f"说话风格：{speech_style}" + "，"
            if additional_info != "":
                line = line + f"补充信息：{additional_info}" + "，"
            line = line.removesuffix("，")
            if line.strip() != "":
                dict_lines.append(line)

        # 返回结果
        if dict_lines == []:
            return ""
        else:
            return (
                "角色介绍："
                + "\n" + "\n".join(dict_lines)
            )

    # 构造世界观设定
    def build_world_building(config: TranslatorConfig) -> tuple[str, str]:
        return (
            "世界观设定："
            + "\n" + f"{config.world_building_content}"
        )

    # 构造行文措辞要求
    def build_writing_style(config: TranslatorConfig) -> tuple[str, str]:
        return (
            "行文措辞要求："
            + "\n" + f"{config.writing_style_content}"
        )

    # 构造翻译风格示例
    def build_translation_example(config: TranslatorConfig) -> tuple[str, str]:
        dict_lines = []
        for item in config.translation_example_data:
            src = item.get("src", "")
            dst = item.get("dst", "")

            if src != "" and dst != "":
                dict_lines.append(f"{src} -> {dst}")

        if dict_lines == []:
            return ""
        else:
            return (
                "翻译风格示例："
                + "\n" + "\n".join(dict_lines)
            )