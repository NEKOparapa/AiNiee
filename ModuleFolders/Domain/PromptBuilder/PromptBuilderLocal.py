from types import SimpleNamespace

from ModuleFolders.Base.Base import Base
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Service.TaskExecutor import TranslatorUtil


class PromptBuilderLocal(Base):

    def __init__(self) -> None:
        super().__init__()

    def _normalize_config(config: TaskConfig | dict | None) -> TaskConfig | SimpleNamespace | None:
        if not isinstance(config, dict):
            return config

        namespace = SimpleNamespace()
        for key, value in config.items():
            setattr(namespace, key, value)

        return namespace

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderLocal, "local_system_zh", None) is None:
            with open("./Resource/Prompt/Local/local_system_zh.txt", "r", encoding="utf-8") as reader:
                PromptBuilderLocal.local_system_zh = reader.read().strip()

        if getattr(PromptBuilderLocal, "local_system_en", None) is None:
            with open("./Resource/Prompt/Local/local_system_en.txt", "r", encoding="utf-8") as reader:
                PromptBuilderLocal.local_system_en = reader.read().strip()

        config = PromptBuilderLocal._normalize_config(config)
        if config is None or config.target_language in ("chinese_simplified", "chinese_traditional"):
            return PromptBuilderLocal.local_system_zh

        return PromptBuilderLocal.local_system_en

    # 获取系统提示词
    def build_system(config: TaskConfig, source_lang: str) -> str:
        PromptBuilderLocal.get_system_default(config)
        config = PromptBuilderLocal._normalize_config(config)

        en_sl, source_language, en_tl, target_language = TranslatorUtil.get_language_display_names(
            source_lang,
            config.target_language,
        )

        if config is None or config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = PromptBuilderLocal.local_system_zh
        else:
            result = PromptBuilderLocal.local_system_en
            source_language = en_sl
            target_language = en_tl

        return result.replace("{source_language}", source_language).replace("{target_language}", target_language).strip()

    # 构造术语表
    def build_glossary_prompt(config: TaskConfig, input_dict: dict) -> str:
        return PromptBuilder.build_glossary_prompt(config, input_dict)

    # 生成项目角色表 - LocalLLM
    def build_project_characters_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_project_characters_prompt(config, source_text_dict)

    # 生成项目术语表 - LocalLLM
    def build_project_terms_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_project_terms_prompt(config, source_text_dict)

    # 生成角色介绍 - LocalLLM
    def build_characterization_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_characterization(config, source_text_dict)

    # 生成背景设定 - LocalLLM
    def build_world_building_prompt(config: TaskConfig) -> str:
        return PromptBuilder.build_world_building(config)

    # 生成翻译风格 - LocalLLM
    def build_writing_style_prompt(config: TaskConfig) -> str:
        return PromptBuilder.build_writing_style(config)

    # 生成手动翻译示例 - LocalLLM
    def build_translation_example_prompt(config: TaskConfig) -> str:
        return PromptBuilder.build_translation_example(config)

    # 将不同部分的系统提示词拼接在一起，并记录额外日志
    def _append_system_section(system: str, extra_log: list[str], section: str, prepend_newline: bool = False) -> str:
        if section == "":
            return system

        system += f"\n{section}" if prepend_newline else section
        extra_log.append(section)
        return system

    # 生成最终提示词 - LocalLLM
    def generate_prompt_LocalLLM(
        config,
        source_text_dict: dict,
        previous_text_list: list[str],
        source_lang,
    ) -> tuple[list[dict], str, list[str]]:
        # 保留原签名，当前本地模型链路不使用上文 few-shot。
        _ = previous_text_list

        messages = []
        extra_log = []

        # 基础提示词
        system = PromptBuilderLocal.build_system(config, source_lang)

        # 术语表
        if getattr(config, "prompt_dictionary_switch", False):
            glossary = PromptBuilderLocal.build_glossary_prompt(config, source_text_dict)
            system = PromptBuilderLocal._append_system_section(system, extra_log, glossary, prepend_newline=True)

        # 项目角色表
        project_characters = PromptBuilderLocal.build_project_characters_prompt(config, source_text_dict)
        system = PromptBuilderLocal._append_system_section(system, extra_log, project_characters)

        # 项目术语表
        project_terms = PromptBuilderLocal.build_project_terms_prompt(config, source_text_dict)
        system = PromptBuilderLocal._append_system_section(system, extra_log, project_terms)

        # 角色介绍
        if getattr(config, "characterization_switch", False):
            characterization = PromptBuilderLocal.build_characterization_prompt(config, source_text_dict)
            system = PromptBuilderLocal._append_system_section(system, extra_log, characterization)

        # 背景设定
        if getattr(config, "world_building_switch", False):
            world_building = PromptBuilderLocal.build_world_building_prompt(config)
            system = PromptBuilderLocal._append_system_section(system, extra_log, world_building)

        # 翻译风格
        if getattr(config, "writing_style_switch", False):
            writing_style = PromptBuilderLocal.build_writing_style_prompt(config)
            system = PromptBuilderLocal._append_system_section(system, extra_log, writing_style)

        # 手动翻译示例
        if getattr(config, "translation_example_switch", False):
            translation_example = PromptBuilderLocal.build_translation_example_prompt(config)
            system = PromptBuilderLocal._append_system_section(system, extra_log, translation_example)

        source_text = PromptBuilder.build_source_text(config, source_text_dict)
        pre_prompt = PromptBuilder.build_userQueryPrefix(config)
        source_text_str = f"{pre_prompt}<textarea>\n{source_text}\n</textarea>"

        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        return messages, system, extra_log
