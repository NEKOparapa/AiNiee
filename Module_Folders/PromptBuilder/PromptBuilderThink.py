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

        # 构建指令词典文本
        dict_lines = []
        for item in result:
            src = item.get("src", "")
            dst = item.get("dst", "")
            info = item.get("info", None)

            if info == None:
                dict_lines.append(f"{src}->{dst}")
            else:
                dict_lines.append(f"{src}->{dst} #{info}")

        # 返回结果
        if dict_lines == []:
            return ""
        else:
            return (
                "术语表："
                + "\n" + "\n".join(dict_lines)
            )