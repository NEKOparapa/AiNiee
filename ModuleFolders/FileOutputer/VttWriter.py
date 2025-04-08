from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class VttWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None
    ):
        # 头信息
        header = f"{items[0].top_text}\n\n"
        output_lines = []
        for item in items:
            block = []
            if getattr(item, "subtitle_number", None):
                block.append(str(item.subtitle_number))
            block.append(item.subtitle_time)
            block.append(item.get_translated_text())
            output_lines.append("\n".join(block))
        translation_file_path.write_text(header + "\n\n\n".join(output_lines), encoding=self.translated_encoding)

    @classmethod
    def get_project_type(self):
        return "Vtt"
