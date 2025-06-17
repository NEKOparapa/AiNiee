from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class VttWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        # 头信息
        header = f"{cache_file.require_extra("top_text")}\n\n"
        output_lines = []
        for item in cache_file.items:
            block = []
            if "subtitle_number" in item.extra:
                block.append(str(item.require_extra("subtitle_number")))
            block.append(item.require_extra("subtitle_time"))
            block.append(item.final_text)
            output_lines.append("\n".join(block))
        translation_file_path.write_text(header + "\n\n\n".join(output_lines), encoding=pre_write_metadata.encoding)

    @classmethod
    def get_project_type(self):
        return ProjectType.VTT
