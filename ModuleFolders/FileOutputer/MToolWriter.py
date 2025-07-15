import json
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class MToolWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        output_dict = {}
        for item in cache_file.items:
            # 如果这个本已经翻译了，存放对应的文件中
            if item.translation_status == TranslationStatus.TRANSLATED or item.translation_status == TranslationStatus.POLISHED:
                output_dict[item.source_text] = item.final_text
            # 如果这个文本没有翻译或者正在翻译
            # elif item.translation_status == TranslationStatus.UNTRANSLATED:
            #     output_dict[item.source_text] = item.translated_text
        json_content = json.dumps(output_dict, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")
        # 未保留未翻译输出

    @classmethod
    def get_project_type(self) -> str:
        return ProjectType.MTOOL
