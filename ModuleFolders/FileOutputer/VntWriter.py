import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class VntWriter(BaseTranslatedWriter):
    """输出文件格式示例
        [
            {
                "name": "玲",
                "message": "「……おはよう」"
            },
            {
                "message": "　心の内では、ムシャクシャした気持ちは未だに鎮まっていなかった。"
            }
        }
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
            # 如果这个本已经翻译了，存放对应的文件中
            if getattr(item, "name", None):

                # 分割人名与文本
                name, translated_text = self.extract_strings(item.name, item.get_translated_text())

                # 构建字段
                text = {"name": name, "message": translated_text}
            else:
                text = {"message": item.get_translated_text()}
            output_list.append(text)
        json_content = json.dumps(output_list, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")
        # 未保留未翻译输出

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
        return "Vnt"
