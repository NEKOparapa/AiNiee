import re
from types import SimpleNamespace

from ModuleFolders.Base.Base import Base
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder

class PromptBuilderSakura(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderSakura, "sakura_system_zh", None) == None:
            with open("./Resource/Prompt/Sakura/sakura_system_zh.txt", "r", encoding = "utf-8") as reader:
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
        # 将输入字典中的所有值合并为一个字符串，方便正则全局匹配
        full_text = "\n".join(input_dict.values())

        # 筛选并处理匹配的条目
        result = []
        seen_keys = set() # 用于去重 (匹配到的实际原文, 译文)

        for v in config.prompt_dictionary_data:
            src = v.get("src", "")
            if not src:
                continue

            try:
                # 编译正则表达式，忽略大小写以保持与原逻辑一致的宽松匹配
                pattern = re.compile(src, re.IGNORECASE)

                # 查找所有匹配项 (set去重，处理同一词在文中多次出现的情况)
                found_texts = set(m.group() for m in pattern.finditer(full_text))

                # 如果正则匹配到了内容 (例如正则 (A|B) 匹配到了 A 和 B，这里会循环两次)
                for match_text in found_texts:
                    if not match_text: continue

                    # 使用 (实际匹配文本, 译文) 作为唯一键进行去重
                    key = (match_text, v.get("dst"))
                    if key not in seen_keys:
                        # 复制元数据，并将 src 替换为实际匹配到的原文文本
                        new_entry = v.copy()
                        new_entry["src"] = match_text
                        result.append(new_entry)
                        seen_keys.add(key)

            except re.error:
                # 如果正则编译失败（非合法正则），回退到普通字符串包含判断
                if src.lower() in full_text.lower():
                    key = (src, v.get("dst"))
                    if key not in seen_keys:
                        result.append(v)
                        seen_keys.add(key)

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

        # 构建待翻译文本（序号+行平铺格式，便于本地模型处理换行）
        source_text = PromptBuilderSakura.build_source_text_sakura(config, source_text_dict)

        # 构建主要提示词
        if glossary == "":
            user_prompt = "将下面的日文文本翻译成中文：\n" + source_text
        else:
            user_prompt = (
                "根据以下术语表（可以为空）：\n" + glossary
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