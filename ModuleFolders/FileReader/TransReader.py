import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class TransReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Trans"

    @property
    def support_file(self):
        return "trans"

    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        trans_content = json.loads(file_path.read_text(encoding="utf-8"))

        files_data = trans_content["project"]["files"]
        items = []
        # 遍历每个文件类别（例如："data/Actors.json"）
        for file_category, category_data in files_data.items():

            data_list = category_data.get("data", [])
            tags_list = category_data.get("tags", [])  # 如果缺失，默认为空列表
            parameters_list = category_data.get("parameters", [])  # 如果缺失，默认为空列表

            # 遍历每对文本 [原文，翻译]
            for idx, text_pair in enumerate(data_list):

                source_text = text_pair[0]
                translated_text = text_pair[1]

                # 确定该特定条目的标签
                tags = None
                if idx < len(tags_list):
                    tags = tags_list[idx]  # 可能为 null 或类似 "red" 的字符串

                # 确定该特定条目的人名
                parameters = None
                rowInfoText = None
                if idx < len(parameters_list):
                    parameters = parameters_list[idx]
                    if parameters and len(parameters) > 0 and isinstance(parameters[0], dict):
                        rowInfoText = parameters[0].get("rowInfoText", "")  # 可能为 具体人名 或类似 "\\v[263]" 的字符串

                item = text_to_cache_item(source_text, translated_text)
                item.tags = tags
                item.file_category = file_category
                item.data_index = idx
                if rowInfoText:
                    item.set_source_text(self.combine_srt(rowInfoText, source_text))
                    item.name = rowInfoText
                items.append(item)
        return items

    def combine_srt(self, name, text):
        return f"[{name}]{text}"
