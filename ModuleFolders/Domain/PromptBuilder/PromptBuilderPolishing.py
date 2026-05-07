import re

from ModuleFolders.Base.Base import Base
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper
from ModuleFolders.Config.FilePathConfig import prompt_path
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig


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
        result = GlossaryHelper.collect_matched_rows(
            getattr(config, "prompt_dictionary_data", []),
            input_dict,
            include_invalid=False,
        )

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
        exclusion_list_data = config.exclusion_list_data.copy()

        exclusion_dict = {}
        texts = list(source_text_dict.values())

        for element in exclusion_list_data:
            regex = element.get("regex", "").strip()
            marker = element.get("markers", "").strip()
            info = element.get("info", "")

            if regex:
                try:
                    pattern = re.compile(regex)
                    for text in texts:
                        for match in pattern.finditer(text):
                            markers = match.group(0)
                            if markers not in exclusion_dict:
                                exclusion_dict[markers] = info
                except re.error:
                    pass
            else:
                found = any(marker in text for text in texts)
                if found and marker not in exclusion_dict:
                    exclusion_dict[marker] = info

        if not exclusion_dict:
            return ""

        if config.target_language in ("chinese_simplified", "chinese_traditional"):
            result = "\n###禁翻表，以下特殊标记符无须翻译\n特殊标记符|备注"
        else:
            result = "\n###Non-Translation List,Leave the following marked content untranslated\nSpecial marker|Remarks"

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
        if config.prompt_dictionary_switch:
            glossary = PromptBuilderPolishing.build_glossary_prompt(config, source_text_dict)
            if glossary:
                system += glossary
                extra_log.append(glossary)

        # 禁翻表
        if config.exclusion_list_switch:
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
        if getattr(config, "pre_line_counts", 0) and previous_text_list:
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
