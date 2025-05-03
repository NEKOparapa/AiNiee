import json
from pathlib import Path

import rich

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class TransReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.TRANS

    @property
    def support_file(self):
        return "trans"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
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

                # --- 新增检查 ---
                if not isinstance(text_pair, (list, tuple)):
                    rich.print(
                        f"[[red]WARNING[/]] 在文件 '{file_path}' 的类别 '{file_category}' 索引 {idx} 处发现非列表/元组项：{text_pair}，已跳过。")
                    continue  # 跳过这个无效项

                if len(text_pair) == 0:
                    rich.print(
                        f"[[red]WARNING[/]] 在文件 '{file_path}' 的类别 '{file_category}' 索引 {idx} 处发现空项：{text_pair}，已跳过。")
                    continue  # 跳过这个空项
                # --- 检查结束 ---

                # 安全获取原文内容
                source_text = text_pair[0]

                # 获取译文内容，并且防止列表越界，有些trans文件没有译文位置
                if len(text_pair) >= 2:
                    translated_text = text_pair[1]
                else:
                    translated_text = ""

                # 检查翻译状态，过滤已翻译内容
                if translated_text:
                    translation_status = CacheItem.STATUS.TRANSLATED
                else:
                    translation_status = CacheItem.STATUS.UNTRANSLATED

                # 确定该特定条目的标签
                tags = None
                if idx < len(tags_list):
                    tags = tags_list[idx]  # 可能为 null 或类似 "red" 的字符串

                # 确定该特定条目的人名
                parameters = None
                rowInfoText = None
                if idx < len(parameters_list):
                    parameters = parameters_list[idx]
                    if parameters and len(parameters) > 0 and isinstance(parameters[0], dict):  # 有些人名信息并没有以字典存储
                        rowInfoText = parameters[0].get("rowInfoText", "")  # 可能为 具体人名 或类似 "\\v[263]" 的字符串

                extra = {
                    "tags": tags,
                    "file_category": file_category,
                    "data_index": idx,
                }
                item = CacheItem(
                    source_text=source_text,
                    translated_text=translated_text,
                    translation_status=translation_status,
                    extra=extra
                )
                if rowInfoText:
                    item.source_text = self.combine_srt(rowInfoText, source_text)
                    item.set_extra("name", rowInfoText)
                items.append(item)
        return CacheFile(items=items)

    def combine_srt(self, name, text):
        return f"[{name}]{text}"
