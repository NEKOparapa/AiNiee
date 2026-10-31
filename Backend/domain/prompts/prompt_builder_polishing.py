from Backend.core.base import Base
from Backend.domain.prompts.glossary_helper import GlossaryHelper
from Backend.domain.config.tables import TableConfigHelper
from Backend.domain.text.regex import RegexSwitchHelper
from Backend.domain.prompts.prompt_builder import PromptBuilder
from Backend.domain.prompts.prompt_builder_enum import PromptBuilderEnum
from Backend.domain.prompts.character_helper import CharacterHelper
from Backend.core.paths import prompt_path
from Backend.domain.config.task_config import TaskConfig


class PromptBuilderPolishing(Base):
    def __init__(self) -> None:
        super().__init__()

    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderPolishing, "common_system_zh_t", None) is None:
            with open(prompt_path("Polishing", "common_system_zh_t.txt"), "r", encoding="utf-8") as reader:
                PromptBuilderPolishing.common_system_zh_t = reader.read().strip()

        return PromptBuilderPolishing.common_system_zh_t

    def build_system(config: TaskConfig) -> str:
        return PromptBuilderPolishing.get_system_default(config)

    def build_glossary_prompt(config: TaskConfig, input_dict: dict) -> str:
        result = GlossaryHelper.collect_matched_table_rows(config, input_dict)

        if not result:
            return ""

        if len(result) == 1 and result[0]["src"] == "":
            return ""

        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            glossary_prompt_lines = [
                "\n###术语表",
                "原文|译文|备注",
            ]
        else:
            glossary_prompt_lines = [
                "\n###Glossary",
                "Original Text|Translation|Remarks",
            ]

        for item in result:
            info = item.get("info") if item.get("info") != "" else " "
            glossary_prompt_lines.append(f"{item.get('src')}|{item.get('dst')}|{info}")

        return "\n".join(glossary_prompt_lines)

    def build_ntl_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        exclusion_list_data = TableConfigHelper.get_enabled_rows(config, "exclusion_list")

        exclusion_dict = {}
        texts = list(source_text_dict.values())

        for element in exclusion_list_data:
            info = element.get("info", "")
            pattern = RegexSwitchHelper.build_re_pattern(element, "markers")
            if pattern is None:
                continue

            for text in texts:
                for match in pattern.finditer(text):
                    matched_marker = match.group(0)
                    if matched_marker and matched_marker not in exclusion_dict:
                        exclusion_dict[matched_marker] = info

        if not exclusion_dict:
            return ""

        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = "\n###禁翻表，以下原文保持不变\n原文|备注"
        else:
            result = "\n###Non-Translation List, keep the following source text unchanged\nSource text|Remarks"

        for markers, info in exclusion_dict.items():
            result += f"\n{markers}|{info}" if info else f"\n{markers}|"

        return result

    def build_pre_text(config: TaskConfig, input_list: list[str]) -> str:
        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            profile = "###上文内容\n"
        else:
            profile = "###Previous text\n"

        profile += "\n".join(input_list) + "\n"
        return profile

    def build_translated_prefix(config: TaskConfig) -> tuple[str, str]:
        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            return " ###原文文本\n", "###这是你接下来的润色任务，初译文本如下\n"

        return " ###Original text\n", "###This is your next polishing task, the draft translation is as follows\n"

    # 生成项目角色表 - Polishing
    def build_project_characters_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_project_characters_prompt(config, source_text_dict)

    # 生成项目术语表 - Polishing
    def build_project_terms_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_project_terms_prompt(config, source_text_dict)

    # 生成项目禁翻表 - Polishing
    def build_project_non_translate_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilder.build_project_non_translate_prompt(config, source_text_dict)

    def generate_prompt(
        config,
        source_text_dict: dict,
        translation_text_dict: dict,
        previous_text_list: list[str],
    ) -> tuple[list[dict], str, list[str]]:
        messages = []
        extra_log = []

        # 基础提示词
        if config.polishing_prompt_selection["last_selected_id"] == PromptBuilderEnum.POLISH_COMMON:
            system = PromptBuilderPolishing.build_system(config)
        else:
            system = config.polishing_prompt_selection["prompt_content"]

        # 术语表
        if TableConfigHelper.has_enabled_tables(config, "prompt_dictionary"):
            glossary = PromptBuilderPolishing.build_glossary_prompt(config, source_text_dict)
            if glossary:
                system += glossary
                extra_log.append(glossary)

        # 禁翻表
        if TableConfigHelper.has_enabled_tables(config, "exclusion_list"):
            ntl = PromptBuilderPolishing.build_ntl_prompt(config, source_text_dict)
            if ntl:
                system += ntl
                extra_log.append(ntl)

        # 项目角色表
        project_characters = PromptBuilderPolishing.build_project_characters_prompt(config, source_text_dict)
        if project_characters:
            system += project_characters
            extra_log.append(project_characters)

        # 项目术语表
        project_terms = PromptBuilderPolishing.build_project_terms_prompt(config, source_text_dict)
        if project_terms:
            system += project_terms
            extra_log.append(project_terms)

        # 项目禁翻表
        project_non_translate = PromptBuilderPolishing.build_project_non_translate_prompt(config, source_text_dict)
        if project_non_translate:
            system += project_non_translate
            extra_log.append(project_non_translate)

        # 角色介绍
        if getattr(config, "characterization_switch", False):
            characterization = PromptBuilder.build_characterization(config, source_text_dict)
            if characterization:
                system += characterization
                extra_log.append(characterization)

        previous = ""
        if getattr(config, "polishing_pre_line_counts", 0) and previous_text_list:
            previous = PromptBuilderPolishing.build_pre_text(config, previous_text_list)
            if previous:
                extra_log.append(f"###上文内容\n{'\n'.join(previous_text_list)}")

        source_text = PromptBuilder.build_source_text(config, source_text_dict)
        translation_text = PromptBuilder.build_source_text(config, translation_text_dict)
        pre_prompt_a, pre_prompt_b = PromptBuilderPolishing.build_translated_prefix(config)
        source_text_str = (
            f"{previous}\n"
            f"{pre_prompt_a}\n"
            f"{source_text}\n"
            f"{pre_prompt_b}<textarea>\n{translation_text}\n</textarea>"
        )

        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        if config.few_shot_and_example_switch:
            if config.target_language in ("chinese_simplified", "chinese_traditional"):
                messages.append(
                    {
                        "role": "assistant",
                        "content": "我已完全理解你的要求，会按照指示执行润色任务。",
                    }
                )
            else:
                messages.append(
                    {
                        "role": "assistant",
                        "content": "I have fully understood your requirements and will follow your instructions to perform the polishing task.",
                    }
                )

        return messages, system, extra_log
