from types import SimpleNamespace

from Base.Base import Base
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig


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
