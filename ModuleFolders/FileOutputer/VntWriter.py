import json
from pathlib import Path

# 假定这些导入相对于项目结构是正确的
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class VntWriter(BaseTranslatedWriter):
    """输出Vnt格式文件的写入器。
       输出文件格式示例
        [
            {
                "names": ["玲","女人"], # 可能包含 'names' 列表
                "message": "「……」"
            },
            {
                "name": "玲", # 或者可能包含 'name' 字符串
                "message": "「……おはよう」"
            },
            { # 或者两者都没有
                "message": "　心の内では、ムシャクシャした気持ちは未だに鎮まっていなかった。"
            }
        ]
    """
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None
    ):
        output_list = []
        # 转换中间字典的格式为最终输出格式
        for item in items:
            # 一次性获取翻译后的文本
            translated_text_full = item.get_translated_text()
            text = None # 初始化text字典

            # --- 首先检查 'names' ---
            original_names = getattr(item, "names", None)
            # 确保它是一个非空列表
            if isinstance(original_names, list) and original_names:
                # 处理 'names' 字段
                updated_names, remaining_message = self.extract_multiple_names_from_text(
                    original_names, translated_text_full
                )
                text = {"names": original_names, "message": remaining_message}

            # --- 如果 'names' 未被处理，则检查 'name' ---
            elif text is None and getattr(item, "name", None):
                 # 处理 'name' 字段（使用原始逻辑）
                original_name = item.name
                # 处理前确保 name 不为空
                if original_name:
                    updated_name, remaining_message = self.extract_strings(
                        original_name, translated_text_full
                    )
                    text = {"name": original_name, "message": remaining_message}
                else: # 处理 'name' 属性存在但为空的情况
                     text = {"message": translated_text_full}

            # --- 后备处理：没有 'name' 或 'names' ---
            # 如果 text 仍然是 None，表示既没有找到 'names' 也没有找到 'name' 或它们未被成功处理
            if text is None:
                text = {"message": translated_text_full}

            output_list.append(text)

        # --- 写入文件 ---
        json_content = json.dumps(output_list, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")


    def extract_multiple_names_from_text(self, original_names: list[str], dialogue: str) -> tuple[list[str], str]:
        """
        从对话字符串的开头提取多个方括号括起来的名称，
        基于 original_names 列表中的名称数量。

        Args:
            original_names: 原始名称列表（用于确定数量）。
            dialogue: 翻译后的文本，可能以方括号括起来的名称开头。

        Returns:
            一个元组，包含：
            - list[str]: 提取出的名称列表（如果提取失败则为原始名称列表）。
            - str: 提取名称后剩余的对话文本。
        """
        num_names_to_extract = len(original_names) # 需要提取的名称数量
        extracted_names = []
        current_pos = 0
        last_bracket_end = 0

        for i in range(num_names_to_extract):
            # 查找下一个潜在名称块的开始位置 '['，跳过前导空格
            start_bracket_pos = -1
            temp_pos = current_pos
            while temp_pos < len(dialogue):
                if dialogue[temp_pos] == '[':
                    start_bracket_pos = temp_pos
                    break
                elif not dialogue[temp_pos].isspace():
                    # 在找到 '[' 之前遇到了非空白字符，此模式的提取失败
                    return original_names, dialogue # 回退到原始值
                temp_pos += 1

            if start_bracket_pos == -1:
                 # 未找到足够的起始方括号 '['
                return original_names, dialogue # 回退到原始值

            # 查找对应的结束方括号 ']'
            end_bracket_pos = dialogue.find("]", start_bracket_pos + 1)
            if end_bracket_pos == -1:
                # 未找到结束方括号 ']'
                return original_names, dialogue # 回退到原始值

            # 提取名称内容
            name_content = dialogue[start_bracket_pos + 1 : end_bracket_pos]
            extracted_names.append(name_content)

            # 更新下一次搜索的位置
            current_pos = end_bracket_pos + 1
            last_bracket_end = current_pos # 记录最后一个方括号结束的位置

        # 提取完所有名称后，剩余的对话从最后一个方括号之后开始
        remaining_dialogue = dialogue[last_bracket_end:].lstrip()

        # 检查是否成功提取了预期数量的名称
        if len(extracted_names) == num_names_to_extract:
            return extracted_names, remaining_dialogue
        else:
            # 如果出现问题则回退（应该在前面被捕获，但作为安全措施）
            return original_names, dialogue


    # 处理 'name' 字段的情况
    def extract_strings(self, name, dialogue):
        """
        根据原始名称中的方括号数量，从对话文本中提取单个名称部分，
        遵循原始实现逻辑。
        """
        if dialogue.startswith("["):
            # 计算原始名称中 ']' 的数量
            count_in_name = name.count("]")
            required_closing_brackets = count_in_name + 1  # 需要找到这么多个 ']'
            current_pos = 0
            found_brackets = 0
            end_pos = -1

            # 查找第 (count_in_name + 1) 个 ']' 的位置
            while found_brackets < required_closing_brackets:
                next_pos = dialogue.find("]", current_pos)
                if next_pos == -1:  # 未找到足够的 ']'
                    break
                found_brackets += 1
                end_pos = next_pos
                current_pos = next_pos + 1 # 在此 ']' 之后继续搜索

            # 如果找到了足够数量的 ']'，则分割字符串
            if found_brackets == required_closing_brackets:
                # 内容从第一个 '[' 到第 N 个 ']'
                extracted_name = dialogue[1:end_pos]
                remaining_dialogue = dialogue[end_pos + 1:].lstrip()
                return (extracted_name, remaining_dialogue)

        # 回退：如果条件不满足，返回原始名称和完整对话
        return name, dialogue

    @classmethod
    def get_project_type(self):
        return "Vnt"