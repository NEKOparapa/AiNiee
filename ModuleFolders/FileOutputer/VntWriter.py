import json
from pathlib import Path

# 假定这些导入相对于项目结构是正确的
from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
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

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        output_list = []
        # 转换中间字典的格式为最终输出格式
        for item in cache_file.items:
            # 一次性获取翻译后的文本
            translated_text_full = item.final_text
            text = None # 初始化text字典

            # --- 首先检查 'names' ---
            original_names = item.get_extra("names")
            # 确保它是一个非空列表
            if isinstance(original_names, list) and original_names:
                # 处理 'names' 字段
                updated_names, remaining_message = self.extract_multiple_names_from_text(
                    original_names, translated_text_full
                )
                text = {"names": updated_names, "message": remaining_message}

            # --- 如果 'names' 未被处理，则检查 'name' ---
            elif text is None and item.get_extra("name"):
                # 处理 'name' 字段（使用原始逻辑）
                original_name = item.require_extra("name")
                # 处理前确保 name 不为空
                if original_name:
                    updated_name, remaining_message = self.extract_strings(
                        original_name, translated_text_full
                    )
                    text = {"name": updated_name, "message": remaining_message}
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
        # 验证数据类型
        if not isinstance(dialogue, str) or not isinstance(name, str):
            return name, dialogue

        # 仅当对话以"["开头时才处理
        if not dialogue.startswith("["):
            return name, dialogue

        end_pos = -1  # 初始化结束位置为-1（表示未找到）

        # 优先策略：尝试匹配与原name嵌套层级一致的"]"
        # 这种策略可以正确处理 [[英雄]惊讶] 这样的情况
        count_in_name = name.count("]")
        required_closing_brackets = count_in_name + 1
        
        search_start_pos = 0
        temp_end_pos = -1
        found_brackets = 0
        for _ in range(required_closing_brackets):
            # 从上一个找到的位置之后开始搜索
            pos = dialogue.find("]", search_start_pos)
            if pos == -1:
                # 如果找不到足够数量的"]"，说明优先策略失败
                found_brackets = -1  # 标记为失败
                break
            temp_end_pos = pos
            found_brackets += 1
            search_start_pos = pos + 1
        
        # 如果优先策略成功，则使用其结果
        if found_brackets == required_closing_brackets:
            end_pos = temp_end_pos

        # 回退策略：如果优先策略失败 (end_pos 仍然是 -1)，则回退为查找第一个 "]"
        if end_pos == -1:
            end_pos = dialogue.find("]")

        # 如果最终找到了一个有效的结束位置（无论是通过优先策略还是回退策略）
        # end_pos > 0 确保了不是空名字，如 "[]text"
        if end_pos > 0:
            extracted_name = dialogue[1:end_pos]
            remaining_dialogue = dialogue[end_pos + 1:].lstrip()
            return extracted_name, remaining_dialogue

        # 如果两种策略都失败了（例如，对话是"["但没有"]"），则返回原值
        return name, dialogue

    @classmethod
    def get_project_type(self):
        return ProjectType.VNT
