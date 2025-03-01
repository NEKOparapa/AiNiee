from types import SimpleNamespace

from Base.Base import Base
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig


class PromptBuilderSakura(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TranslatorConfig) -> str:
        if getattr(PromptBuilderSakura, "sakura_system_zh", None) == None:
            with open("./Resource/Prompt/sakura_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderSakura.sakura_system_zh = reader.read().strip()


        # 如果输入的是字典，则转换为命名空间
        if isinstance(config, dict):
            namespace = SimpleNamespace()
            for key, value in config.items():
                setattr(namespace, key, value)
            config = namespace


        # 构造结果
        result = PromptBuilderSakura.sakura_system_zh

        return result

    # 获取系统提示词
    def build_system(config: TranslatorConfig) -> str:
        PromptBuilderSakura.get_system_default(config)

        # 构造结果
        result = PromptBuilderSakura.sakura_system_zh


        return result



    # 构造术语表
    def build_glossary(config: TranslatorConfig, input_dict: dict) -> str:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result: list[dict] = [
            v for v in config.prompt_dictionary_data
            if any(v.get("src", "") in lines for lines in lines)
        ]

        if len(result) == 0:
            return ""

        # 构建指令词典文本
        dict_lines = []
        for item in result:
            src = item.get("src", "")
            dst = item.get("dst", "")
            info = item.get("info", "")

            if info == "":
                dict_lines.append(f"{src}->{dst}")
            else:
                dict_lines.append(f"{src}->{dst} #{info}")

        # 如果指令词典文本不为空
        if dict_lines != []:
            dict_lines_str = "\n".join(dict_lines)
        else:
            return ""

        return dict_lines_str
