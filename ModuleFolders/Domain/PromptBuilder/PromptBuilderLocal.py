import re
from types import SimpleNamespace

from ModuleFolders.Base.Base import Base
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.Config.FilePathConfig import prompt_path
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Service.TaskExecutor import TranslatorUtil
from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper


class PromptBuilderLocal(Base):
    # 中文目标语言列表
    CHINESE_TARGET_LANGUAGES = ("chinese_simplified", "chinese_traditional")

    # 系统预设提示词文件映射
    SYSTEM_PROMPT_FILES = {
        PromptBuilderEnum.COMMON: {
            "zh": ("Translate", "common_system_zh.txt"),
            "en": ("Translate", "common_system_en.txt"),
        },
        PromptBuilderEnum.COT: {
            "zh": ("Translate", "cot_system_zh.txt"),
            "en": ("Translate", "cot_system_en.txt"),
        },
        PromptBuilderEnum.THINK: {
            "zh": ("Translate", "think_system_zh.txt"),
            "en": ("Translate", "think_system_en.txt"),
        },
        PromptBuilderEnum.LOCAL: {
            "zh": ("Translate", "local_system_zh.txt"),
            "en": ("Translate", "local_system_en.txt"),
        },
    }

    def __init__(self) -> None:
        super().__init__()

    # 如果输入的是字典，则转换为命名空间
    def _normalize_config(config: TaskConfig | dict | None) -> TaskConfig | SimpleNamespace | None:
        if not isinstance(config, dict):
            return config

        namespace = SimpleNamespace()
        for key, value in config.items():
            setattr(namespace, key, value)

        return namespace

    # 获取目标语言配置
    def _get_target_language(config: TaskConfig | SimpleNamespace | None) -> str:
        return getattr(config, "target_language", "")

    # 判断目标语言是否为中文
    def _is_chinese_target(config: TaskConfig | SimpleNamespace | None) -> bool:
        return PromptBuilderLocal._get_target_language(config) in PromptBuilderLocal.CHINESE_TARGET_LANGUAGES

    # 缓存系统预设提示词内容，避免重复读取文件
    def _ensure_system_prompt_cache() -> None:
        if getattr(PromptBuilderLocal, "_system_prompt_cache", None) is not None:
            return

        cache = {}
        for preset_id, language_paths in PromptBuilderLocal.SYSTEM_PROMPT_FILES.items():
            cache[preset_id] = {}
            for language_key, path_parts in language_paths.items():
                with open(prompt_path(*path_parts), "r", encoding="utf-8") as reader:
                    cache[preset_id][language_key] = reader.read().strip()

        PromptBuilderLocal._system_prompt_cache = cache

    # 获取基础提示页保存的系统提示词选择
    def _get_prompt_selection(config: TaskConfig | SimpleNamespace | None) -> dict:
        selection = getattr(config, "translation_prompt_selection", {}) if config else {}
        if isinstance(selection, dict):
            return selection

        return {}

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(
        config: TaskConfig | dict | None,
        prompt_preset: int = PromptBuilderEnum.LOCAL,
    ) -> str:
        PromptBuilderLocal._ensure_system_prompt_cache()
        config = PromptBuilderLocal._normalize_config(config)

        preset_contents = PromptBuilderLocal._system_prompt_cache.get(
            prompt_preset,
            PromptBuilderLocal._system_prompt_cache[PromptBuilderEnum.LOCAL],
        )
        language_key = "zh" if config is None or PromptBuilderLocal._is_chinese_target(config) else "en"
        return preset_contents[language_key]

    # 替换提示词文本中的源语言和目标语言占位符
    def _replace_language_placeholders(
        prompt_text: str,
        config: TaskConfig | SimpleNamespace | None,
        source_lang: str,
    ) -> str:
        if not prompt_text:
            return ""

        config = PromptBuilderLocal._normalize_config(config)
        if config is None:
            return prompt_text

        en_sl, source_language, en_tl, target_language = TranslatorUtil.get_language_display_names(
            source_lang,
            config.target_language,
        )

        if not PromptBuilderLocal._is_chinese_target(config):
            source_language = en_sl
            target_language = en_tl

        return prompt_text.replace("{source_language}", source_language).replace("{target_language}", target_language)

    # 获取系统提示词
    def build_system(config: TaskConfig | dict | None, source_lang: str) -> str:
        config = PromptBuilderLocal._normalize_config(config)
        selection = PromptBuilderLocal._get_prompt_selection(config)
        prompt_preset = selection.get("last_selected_id", PromptBuilderEnum.COMMON)

        if prompt_preset in PromptBuilderLocal.SYSTEM_PROMPT_FILES:
            prompt_text = PromptBuilderLocal.get_system_default(config, prompt_preset)
        else:
            prompt_text = selection.get("prompt_content", "")

        return PromptBuilderLocal._replace_language_placeholders(prompt_text, config, source_lang).strip()

    # 构建原文
    def build_source_text(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_source_text(config, source_text_dict)

    # 构造术语表
    def build_glossary_prompt(config: TaskConfig, input_dict: dict) -> str:
        result = GlossaryHelper.collect_matched_rows(
            getattr(config, "prompt_dictionary_data", []),
            input_dict,
            include_invalid=False,
            case_sensitive=bool(getattr(config, "prompt_dictionary_match_case_sensitive", False)),
            whole_word=bool(getattr(config, "prompt_dictionary_match_whole_word", False)),
        )

        if not result:
            return ""

        if len(result) == 1 and result[0].get("src", "") == "":
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            glossary_prompt_lines = ["\n###术语表\n原文|译文|备注"]
        else:
            glossary_prompt_lines = ["\n###Glossary\nOriginal Text|Translation|Remarks"]

        for item in result:
            info = item.get("info", "")
            glossary_prompt_lines.append(f'{item.get("src", "")}|{item.get("dst", "")}|{info if info != "" else " "}')

        return "\n".join(glossary_prompt_lines)

    # 构造项目表（角色表、术语表）
    def _match_project_table_rows(
        rows: list[dict],
        source_text_dict: dict,
        key_field: str,
        fields_to_keep: tuple[str, ...],
    ) -> list[dict]:
        full_text = "\n".join(source_text_dict.values()) if source_text_dict else ""
        if not full_text:
            return []

        matched_rows = []
        seen_keys = set()

        for row in rows or []:
            if not isinstance(row, dict):
                continue

            key_value = str(row.get(key_field, "") or "").strip()
            if not key_value:
                continue

            normalized_row = {
                field_name: str(row.get(field_name, "") or "").strip()
                for field_name in fields_to_keep
            }

            try:
                pattern = re.compile(key_value, re.IGNORECASE)
                found_texts = set(match.group() for match in pattern.finditer(full_text))

                for match_text in found_texts:
                    if not match_text:
                        continue

                    current_row = normalized_row.copy()
                    current_row[key_field] = match_text
                    dedupe_key = tuple(current_row[field_name] for field_name in fields_to_keep)
                    if dedupe_key in seen_keys:
                        continue

                    matched_rows.append(current_row)
                    seen_keys.add(dedupe_key)
            except re.error:
                if key_value.lower() in full_text.lower():
                    dedupe_key = tuple(normalized_row[field_name] for field_name in fields_to_keep)
                    if dedupe_key in seen_keys:
                        continue

                    matched_rows.append(normalized_row)
                    seen_keys.add(dedupe_key)

        return matched_rows

    # 构建通用项目表片段
    def _build_project_table_prompt(
        config: TaskConfig,
        source_text_dict: dict,
        rows: list[dict],
        key_field: str,
        fields: tuple[str, ...],
        title_zh: str,
        title_en: str,
        header_zh: str,
        header_en: str,
        instruction: str = "",
    ) -> str:
        matched_rows = PromptBuilderLocal._match_project_table_rows(
            rows,
            source_text_dict,
            key_field,
            fields,
        )
        normalized_rows = []
        for row in matched_rows:
            normalized_rows.append([
                row.get(field, "") if row.get(field, "") else " "
                for field in fields
            ])

        if not normalized_rows:
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            prompt_lines = [f"\n###{title_zh}"]
            if instruction:
                prompt_lines.append(instruction)
            prompt_lines.append(header_zh)
        else:
            prompt_lines = [f"\n###{title_en}"]
            if instruction:
                prompt_lines.append(instruction)
            prompt_lines.append(header_en)

        for row in normalized_rows:
            prompt_lines.append("|".join(row))

        return "\n".join(prompt_lines)

    # 生成项目角色表 - LocalLLM
    def build_project_characters_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        # 统一称呼翻译开关：默认关闭。关闭时保持旧行为（仅注入角色表，无路由指令与称呼变体小节）
        if not bool(getattr(config, "character_name_unify_switch", False)):
            return PromptBuilderLocal._build_project_table_prompt(
                config,
                source_text_dict,
                getattr(config, "project_characters_data", []),
                "source",
                ("source", "recommended_translation", "gender", "note"),
                "角色表",
                "Character Table",
                "原文|推荐译名|性别|备注",
                "Original Text|Recommended Translation|Gender|Remarks",
            )

        character_prompt = PromptBuilderLocal._build_project_table_prompt(
            config,
            source_text_dict,
            getattr(config, "project_characters_data", []),
            "source",
            ("source", "recommended_translation", "gender", "note"),
            "角色表",
            "Character Table",
            "原文|推荐译名|性别|备注",
            "Original Text|Recommended Translation|Gender|Remarks",
            instruction=PromptBuilderLocal._get_character_table_instruction(config),
        )
        variants_prompt = PromptBuilderLocal._build_character_variants_prompt(config, source_text_dict)
        if variants_prompt:
            return character_prompt + variants_prompt
        return character_prompt

    # 角色表路由指令：强制使用推荐译名，保持全文一致
    def _get_character_table_instruction(config: TaskConfig) -> str:
        if PromptBuilderLocal._is_chinese_target(config):
            return (
                "翻译时，以下角色名必须严格使用「推荐译名」列，不得意译或更改，全文保持一致；"
                "同一角色的敬称/称呼变体（如 空太先輩、空太くん）必须复用本名的推荐译名。"
            )
        return (
            "When translating, the character names below MUST use the Recommended Translation column exactly; "
            "do not paraphrase or alter them. Keep them consistent throughout the text; "
            "honorific/variant forms of the same character (e.g. 空太先輩, 空太くん) must reuse the base name's recommended translation."
        )

    # 构建角色称呼变体小节 - LocalLLM（与通用版一致）
    def _build_character_variants_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        variants_map = getattr(config, "project_character_variants", {}) or {}
        if not variants_map or not source_text_dict:
            return ""

        full_text = "\n".join(source_text_dict.values())
        if not full_text:
            return ""

        translation_by_source = {
            str(row.get("source", "") or "").strip(): str(row.get("recommended_translation", "") or "").strip()
            for row in getattr(config, "project_characters_data", []) or []
            if isinstance(row, dict) and str(row.get("source", "") or "").strip()
        }

        matched_lines = []
        for base_name, variants in variants_map.items():
            recommended = translation_by_source.get(base_name, "")
            present_variants = [v for v in variants if v in full_text]
            if not present_variants:
                continue
            matched_lines.append((base_name, recommended, present_variants))

        if not matched_lines:
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            lines = [
                "\n###角色称呼变体",
                "以下称呼均为对应角色的变体（含敬称）。翻译时必须复用本名的推荐译名；"
                "敬称部分选择一种合理译法后全文保持一致，禁止同一称呼出现多种译法（如「先輩」不得时而「前辈」时而「学姐」）。",
                "本名|推荐译名|原文称呼变体",
            ]
        else:
            lines = [
                "\n###Character Name Variants",
                "The following are variant forms (including honorifics) of the corresponding characters. "
                "Their translations MUST reuse the recommended translation of the base name. "
                "Choose ONE consistent rendering for each honorific throughout the whole text; "
                "never mix translations of the same honorific.",
                "Base Name|Recommended Translation|Original Name Variants",
            ]

        for base_name, recommended, present_variants in matched_lines:
            lines.append(f"{base_name}|{recommended if recommended else ' '}|{'、'.join(present_variants)}")

        return "\n".join(lines)

    # 生成项目术语表 - LocalLLM
    def build_project_terms_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilderLocal._build_project_table_prompt(
            config,
            source_text_dict,
            getattr(config, "project_terms_data", []),
            "source",
            ("source", "recommended_translation", "category_path", "note"),
            "术语表",
            "Term Table",
            "原文|推荐译名|分类|备注",
            "Original Text|Recommended Translation|Category|Remarks",
        )

    # 生成角色介绍 - LocalLLM
    def build_characterization_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        matched_rows = []
        full_text = "\n".join(source_text_dict.values())
        
        # 使用 CharacterHelper 匹配角色
        for item in CharacterHelper.normalize_rows(getattr(config, "characterization_data", [])):
            matched_name = CharacterHelper.match_original_name(
                item.get("original_name", ""), 
                full_text,
                item.get(CharacterHelper.VALID_KEY, True)
            )
            if matched_name:
                new_item = item.copy()
                new_item["original_name"] = matched_name
                matched_rows.append(new_item)

        if not matched_rows:
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            profile = "\n###角色介绍"
            for value in matched_rows:
                original_name = value.get("original_name", "")
                translated_name = value.get("translated_name")
                gender = value.get("gender")
                age = value.get("age")
                personality = value.get("personality")
                speech_style = value.get("speech_style")
                additional_info = value.get("additional_info")

                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- 译名：{translated_name}"
                if gender:
                    profile += f"\n- 性别：{gender}"
                if age:
                    profile += f"\n- 年龄：{age}"
                if personality:
                    profile += f"\n- 性格：{personality}"
                if speech_style:
                    profile += f"\n- 说话方式：{speech_style}"
                if additional_info:
                    profile += f"\n- 补充信息：{additional_info}"
                profile += "\n"
        else:
            profile = "\n###Character Introduction"
            for value in matched_rows:
                original_name = value.get("original_name", "")
                translated_name = value.get("translated_name")
                gender = value.get("gender")
                age = value.get("age")
                personality = value.get("personality")
                speech_style = value.get("speech_style")
                additional_info = value.get("additional_info")

                profile += f"\n[{original_name}]"
                if translated_name:
                    profile += f"\n- Translated_name: {translated_name}"
                if gender:
                    profile += f"\n- Gender: {gender}"
                if age:
                    profile += f"\n- Age: {age}"
                if personality:
                    profile += f"\n- Personality: {personality}"
                if speech_style:
                    profile += f"\n- Speech_style: {speech_style}"
                if additional_info:
                    profile += f"\n- Additional_info: {additional_info}"
                profile += "\n"

        return profile

    # 生成背景设定 - LocalLLM
    def build_world_building_prompt(config: TaskConfig) -> str:
        world_building = getattr(config, "world_building_content", "")
        if not world_building:
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            profile = "\n###背景设定"
        else:
            profile = "\n###Background Setting"

        profile += f"\n{world_building}\n"
        return profile

    # 生成翻译风格 - LocalLLM
    def build_writing_style_prompt(config: TaskConfig) -> str:
        writing_style = getattr(config, "writing_style_content", "")
        if not writing_style:
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            profile = "\n###翻译风格"
        else:
            profile = "\n###Writing Style"

        profile += f"\n{writing_style}\n"
        return profile

    # 生成手动翻译示例 - LocalLLM
    def build_translation_example_prompt(config: TaskConfig) -> str:
        data = getattr(config, "translation_example_data", [])
        if len(data) == 0:
            return ""

        if PromptBuilderLocal._is_chinese_target(config):
            translation_example = "\n###翻译示例\n"
        else:
            translation_example = "\n###Translation Example\n"

        for index, pair in enumerate(data, start=1):
            original = pair.get("src", "")
            translated = pair.get("dst", "")

            if index > 1:
                translation_example += "\n"

            if PromptBuilderLocal._is_chinese_target(config):
                translation_example += f"  -原文{index}：{original}\n  -译文{index}：{translated}"
            else:
                translation_example += f"  -Original {index}: {original}\n  -Translation {index}: {translated}"

        return translation_example

    # 构建翻译前文
    def build_userQueryPrefix(config: TaskConfig) -> str:
        if PromptBuilderLocal._is_chinese_target(config):
            return " ###这是你接下来的翻译任务，原文文本如下\n"

        return " ###This is your next translation task, the original text is as follows\n"

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
        config = PromptBuilderLocal._normalize_config(config)

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

        source_text = PromptBuilderLocal.build_source_text(config, source_text_dict)
        pre_prompt = PromptBuilderLocal.build_userQueryPrefix(config)
        source_text_str = f"{pre_prompt}<textarea>\n{source_text}\n</textarea>"

        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        return messages, system, extra_log
