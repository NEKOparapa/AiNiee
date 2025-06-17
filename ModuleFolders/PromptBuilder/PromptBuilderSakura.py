from types import SimpleNamespace

from Base.Base import Base
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder

class PromptBuilderSakura(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderSakura, "sakura_system_zh", None) == None:
            with open("./Resource/Prompt/Sakura/sakura_system_zh.txt", "r", encoding = "utf-8") as reader:
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
    def build_system(config: TaskConfig, _source_lang: str) -> str:
        PromptBuilderSakura.get_system_default(config)

        # 构造结果
        result = PromptBuilderSakura.sakura_system_zh


        return result



    # 构造术语表
    def build_glossary(config: TaskConfig, input_dict: dict) -> str:
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

    # 生成信息结构 - Sakura
    def generate_prompt_sakura(config,  source_text_dict: dict, previous_text_list: list[str], source_lang) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        system = PromptBuilderSakura.build_system(config, source_lang)


        # 如果开启术语表
        glossary = ""
        if config.prompt_dictionary_switch == True:
            glossary = PromptBuilderSakura.build_glossary(config, source_text_dict)
            if glossary != "":
                extra_log.append(glossary)

        # 构建待翻译文本
        source_text = PromptBuilder.build_source_text(config,source_text_dict)

        # 构建主要提示词
        if glossary == "":
            user_prompt = "将下面的日文文本翻译成中文：\n" + source_text
        else:
            user_prompt = (
                "根据以下术语表（可以为空）：\n" + glossary
                + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：\n" + source_text
            )

        # 构建指令列表
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        return messages, system, extra_log


