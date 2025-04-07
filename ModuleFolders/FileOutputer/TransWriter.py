import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class TransWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None
    ):
        trans_content = json.loads(source_file_path.read_text(encoding="utf-8"))
        for item in items:
            file_category = getattr(item, "file_category", "")
            data_index = getattr(item, "data_index", "")
            new_translation = item.get_translated_text()
            name = getattr(item, "name", "")

            # 导航并更新，带有检查
            category_data = trans_content["project"]["files"][file_category]
            data_list = category_data["data"]
            parameters_list = category_data["parameters"]

            # 如果有人名信息
            if name:
                # 分割人名与文本
                name, new_translation = self.extract_strings(name, new_translation)
                # 更新人名翻译
                parameters_list[data_index][0]["translation"] = name

            # 仅当翻译实际改变时才写入，译文文本在第二个元素
            if len(data_list[data_index]) > 1:  # 检查长度是否至少为2,保证有译文位置
                if data_list[data_index][1] != new_translation:
                    data_list[data_index][1] = new_translation
            else:
                # 处理列表只有一个元素或没有元素的情况
                data_list[data_index].append(new_translation)

        # 写回修改后的内容
        json_content = json.dumps(trans_content, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")

    def extract_strings(self, name, dialogue):
        if dialogue.startswith("["):
            # 计算原name中的"]"数量
            count_in_name = name.count("]")
            required_closing_brackets = count_in_name + 1  # 需要匹配的"]"总数
            current_pos = 0
            found_brackets = 0
            end_pos = -1

            # 查找第 (count_in_name + 1) 个"]"
            while found_brackets < required_closing_brackets:
                next_pos = dialogue.find("]", current_pos)
                if next_pos == -1:  # 没有足够的"]"，直接返回原值
                    break
                found_brackets += 1
                end_pos = next_pos  # 更新最后一个"]"的位置
                current_pos = next_pos + 1  # 继续往后搜索

            # 如果找到足够数量的"]"，则分割字符串
            if found_brackets == required_closing_brackets:
                extracted_name = dialogue[1:end_pos]
                remaining_dialogue = dialogue[end_pos + 1:].lstrip()
                return (extracted_name, remaining_dialogue)

        # 其他情况直接返回原值
        return name, dialogue

    @classmethod
    def get_project_type(self):
        return "Trans"
