from types import SimpleNamespace

from Base.Base import Base
from ModuleFolders.TaskExecutor import TranslatorUtil
from ModuleFolders.TaskExecutor.TaskConfig import TaskConfig

class PromptBuilderLocal(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
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
        elif  config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderLocal.local_system_zh
        elif config.target_language not in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderLocal.local_system_en

        return result

    # 获取系统提示词
    def build_system(config: TaskConfig, source_lang: str) -> str:

        # 获取默认系统提示词
        PromptBuilderLocal.get_system_default(config)

        en_sl, source_language, en_tl, target_language = TranslatorUtil.get_language_display_names(source_lang, config.target_language)

        # 构造结果
        if config == None:
            result = PromptBuilderLocal.local_system_zh
        elif config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderLocal.local_system_zh
        elif config.target_language not in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderLocal.local_system_en
            source_language = en_sl
            target_language = en_tl

        return result.replace("{source_language}", source_language).replace("{target_language}", target_language).strip()
