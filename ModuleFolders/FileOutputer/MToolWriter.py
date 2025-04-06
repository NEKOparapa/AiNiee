import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class MToolWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        output_dict = {}
        for item in items:
            # 如果这个本已经翻译了，存放对应的文件中
            if item.get_translation_status() == CacheItem.STATUS.TRANSLATED:
                output_dict[item.get_source_text()] = item.get_translated_text()
            # 如果这个文本没有翻译或者正在翻译
            # elif any(item.get_translation_status() == status for status in self.NOT_TRANSLATED_STATUS):
            #     output_dict[item.get_source_text()] = item.get_source_text()
        json_content = json.dumps(output_dict, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")
        # 未保留未翻译输出

    @classmethod
    def get_project_type(self) -> str:
        return "Mtool"
