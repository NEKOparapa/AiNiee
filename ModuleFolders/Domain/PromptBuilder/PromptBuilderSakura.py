import re
from types import SimpleNamespace

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.FilePathConfig import prompt_path
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder

class PromptBuilderSakura(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderSakura, "sakura_system_zh", None) == None:
            with open(prompt_path("Sakura", "sakura_system_zh.txt"), "r", encoding = "utf-8") as reader:
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
        result = GlossaryHelper.collect_matched_rows(
            getattr(config, "prompt_dictionary_data", []),
            input_dict,
            include_invalid=False,
        )

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
        if dict_lines:
            dict_lines_str = "\n".join(dict_lines)
        else:
            return ""

        return dict_lines_str

    # 构造项目表（角色表、术语表）
    def _build_project_table_prompt(
        source_text_dict: dict,
        rows: list[dict],
        key_field: str,
        translation_field: str = "",
        meta_fields: tuple[str, ...] = (),
    ) -> str:
        """
        构建 Sakura 用的紧凑项目表片段，保持和原有术语表一致的纯行格式。
        示例:
        Alice->爱丽丝 #女性 主角
        Academy->学院 #组织 学校
        """
        lines = []
        fields_to_keep = (key_field, translation_field, *meta_fields) if translation_field else (key_field, *meta_fields)
        matched_rows = PromptBuilder._match_project_table_rows(
            rows,
            source_text_dict,
            key_field,
            fields_to_keep,
        )

        for row in matched_rows:
            meta_values = [
                row.get(field_name, "")
                for field_name in meta_fields
                if row.get(field_name, "")
            ]
            meta_suffix = f" #{' '.join(meta_values)}" if meta_values else ""

            if translation_field:
                translation_value = str(row.get(translation_field, "") or "").strip()
                key_value = str(row.get(key_field, "") or "").strip()
                lines.append(f"{key_value}->{translation_value}{meta_suffix}")
            else:
                key_value = str(row.get(key_field, "") or "").strip()
                lines.append(f"{key_value}{meta_suffix}")

        if not lines:
            return ""

        return "\n".join(lines)

    # 生成项目角色表 - Sakura
    def build_project_characters_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilderSakura._build_project_table_prompt(
            source_text_dict,
            getattr(config, "project_characters_data", []),
            "source",
            "recommended_translation",
            ("gender", "note"),
        )

    # 生成项目术语表 - Sakura
    def build_project_terms_prompt(config: TaskConfig, source_text_dict: dict) -> str:
        return PromptBuilderSakura._build_project_table_prompt(
            source_text_dict,
            getattr(config, "project_terms_data", []),
            "source",
            "recommended_translation",
            ("category_path", "note"),
        )

    # 构建原文（Sakura 用）：多行按换行拆成「序号+行」平铺，便于本地模型处理。
    def build_source_text_sakura(config: TaskConfig, source_text_dict: dict) -> str:
        """构建原文（Sakura 用）：多行按换行拆成「序号+行」平铺，便于本地模型处理。

        构建后示例（source_text_dict 含单行与多行时）:
        ---
        1.单行内容
        2.1.多行块第一行
        2.2.多行块第二行
        3.下一块单行
        ---
        """
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            if "\n" not in line:
                numbered_lines.append(f"{index + 1}.{line}")
            else:
                lines = line.split("\n")
                for sub_index, sub_line in enumerate(lines):
                    sub_line = sub_line[:-1] if re.match(r'.*[^ ] $', sub_line) else sub_line
                    numbered_lines.append(f"{index + 1}.{sub_index + 1}.{sub_line}")
        return "\n".join(numbered_lines)

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

        # 项目角色表
        project_characters = PromptBuilderSakura.build_project_characters_prompt(config, source_text_dict)
        if project_characters != "":
            extra_log.append(project_characters)

        # 项目术语表
        project_terms = PromptBuilderSakura.build_project_terms_prompt(config, source_text_dict)
        if project_terms != "":
            extra_log.append(project_terms)


        # 构建待翻译文本（序号+行平铺格式，便于本地模型处理换行）
        source_text = PromptBuilderSakura.build_source_text_sakura(config, source_text_dict)

        # 构建主要提示词
        context_blocks = []
        if glossary != "":
            context_blocks.append(glossary)
        if project_characters != "":
            context_blocks.append(project_characters)
        if project_terms != "":
            context_blocks.append(project_terms)

        context_text = "\n".join(context_blocks)

        if not context_text:
            user_prompt = "将下面的日文文本翻译成中文：\n" + source_text
        else:
            user_prompt = (
                "根据以下术语表（可以为空）：\n" + context_text
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
