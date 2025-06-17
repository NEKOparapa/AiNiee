from types import SimpleNamespace

from Base.Base import Base
from ModuleFolders.TaskExecutor import TranslatorUtil
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder

class PromptBuilderLocal(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderLocal, "local_system_zh", None) == None:
            with open("./Resource/Prompt/Local/local_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderLocal.local_system_zh = reader.read().strip()
        if getattr(PromptBuilderLocal, "local_system_en", None) == None:
            with open("./Resource/Prompt/Local/local_system_en.txt", "r", encoding = "utf-8") as reader:
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

    # 生成信息结构 - LocalLLM
    def generate_prompt_LocalLLM(config,  source_text_dict: dict, previous_text_list: list[str], source_lang) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        system = PromptBuilderLocal.build_system(config, source_lang)

        # 术语表
        if config.prompt_dictionary_switch == True:
            result = PromptBuilder.build_glossary_prompt(config, source_text_dict)
            if result != "":
                system = system + "\n" + result
                extra_log.append(result)
        
        # 构建待翻译文本
        source_text = PromptBuilder.build_source_text(config,source_text_dict)
        pre_prompt = PromptBuilder.build_userQueryPrefix(config) # 用户提问前置文本
        source_text_str = f"{pre_prompt}<textarea>\n{source_text}\n</textarea>"


        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )


        return messages, system, extra_log