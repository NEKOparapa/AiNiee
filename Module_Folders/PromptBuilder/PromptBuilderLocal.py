from types import SimpleNamespace

from Base.Base import Base
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig
from Module_Folders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum

class PromptBuilderLocal(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TranslatorConfig) -> str:
        if getattr(PromptBuilderLocal, "local_system_zh", None) == None:
            with open("./Resource/Prompt/local_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderLocal.local_system_zh = reader.read().strip()
        if getattr(PromptBuilderLocal, "local_system_en", None) == None:
            with open("./Resource/Prompt/local_system_en.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderLocal.local_system_en = reader.read().strip()


        # 如果输入的是字典，则转换为命名空间
        if isinstance(config, dict):
            namespace = SimpleNamespace()
            for key, value in config.items():
                setattr(namespace, key, value)
            config = namespace


        # 构造结果
        if config == None:
            result = PromptBuilderLocal.local_system_zh
        elif  config.cn_prompt_toggle == True:
            result = PromptBuilderLocal.local_system_zh
        elif config.cn_prompt_toggle == False:
            result = PromptBuilderLocal.local_system_en

        return result

    # 获取系统提示词
    def build_system(config: TranslatorConfig) -> str:
        PromptBuilderLocal.get_system_default(config)

        pair = {
            "日语": "Japanese",
            "英语": "English",
            "韩语": "Korean", 
            "俄语": "Russian",
            "简中": "Simplified Chinese",
            "繁中": "Traditional Chinese"
        }

        source_language = config.source_language
        target_language = config.target_language

        # 构造结果
        if config == None:
            result = PromptBuilderLocal.local_system_zh
        elif config.cn_prompt_toggle == True:
            result = PromptBuilderLocal.local_system_zh
        elif config.cn_prompt_toggle == False:
            result = PromptBuilderLocal.local_system_en
            source_language = pair[config.source_language]
            target_language = pair[config.target_language]

        return result.replace("{source_language}", source_language).replace("{target_language}", target_language).strip()
