from types import SimpleNamespace

import langcodes

from Base.Base import Base
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from PluginScripts.LanguageFilter import LanguageFilter


class PromptBuilderThink(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TranslatorConfig) -> str:
        if getattr(PromptBuilderThink, "think_system_zh", None) == None:
            with open("./Resource/Prompt/think_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderThink.think_system_zh = reader.read().strip()
        if getattr(PromptBuilderThink, "think_system_en", None) == None:
            with open("./Resource/Prompt/think_system_en.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderThink.think_system_en = reader.read().strip()


        # 如果输入的是字典，则转换为命名空间
        if isinstance(config, dict):
            namespace = SimpleNamespace()
            for key, value in config.items():
                setattr(namespace, key, value)
            config = namespace


        # 构造结果
        if config == None:
            result = PromptBuilderThink.think_system_zh
        elif config.prompt_preset == PromptBuilderEnum.THINK and config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderThink.think_system_zh
        elif config.prompt_preset == PromptBuilderEnum.THINK and config.target_language not in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderThink.think_system_en

        return result

    # 获取系统提示词
    def build_system(config: TranslatorConfig, source_lang: str) -> str:
        PromptBuilderThink.get_system_default(config)

        en_sl, source_language, en_tl, target_language = LanguageFilter.get_language_display_names(source_lang, config.target_language)

        # 构造结果
        if config == None:
            result = PromptBuilderThink.think_system_zh
        elif config.prompt_preset == PromptBuilderEnum.THINK and config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderThink.think_system_zh
        elif config.prompt_preset == PromptBuilderEnum.THINK and config.target_language not in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderThink.think_system_en
            source_language = en_sl
            target_language = en_tl

        return result.replace("{source_language}", source_language).replace("{target_language}", target_language).strip()

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
            info = item.get("info", "")

            if info == "":
                dict_lines.append(f"{src} -> {dst}")
            else:
                dict_lines.append(f"{src} -> {dst} #{info}")

        # 返回结果
        if dict_lines == []:
            return ""
        else:
            if config.target_language in ("chinese_simplified", "chinese_traditional"):
                return (
                    "###术语表"
                    + "\n" + "\n".join(dict_lines)
                )
            else:
                return (
                    "###Glossary"
                    + "\n" + "\n".join(dict_lines)
                )                
