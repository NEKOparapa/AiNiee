### AssWriter.py

from itertools import count
from pathlib import Path
from typing import Callable, Iterator

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)

class AssWriter(BaseBilingualWriter, BaseTranslatedWriter):
    """
    ASS (Advanced SubStation Alpha) 字幕文件写入器。
    能够恢复在读取时被分离的行首样式标签，以保留原始的样式和元数据。
    """
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_ass_file(translation_file_path, cache_file, pre_write_metadata, self._yield_translated_line)

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_ass_file(translation_file_path, cache_file, pre_write_metadata, self._yield_bilingual_lines)

    def _write_ass_file(
        self, 
        translation_file_path: Path, 
        cache_file: CacheFile, 
        pre_write_metadata: PreWriteMetadata,
        line_generator: Callable[[CacheItem], Iterator[str]]
    ):
        header_footer = cache_file.extra.get('ass_header_footer', [])
        
        output_lines = []
        events_written = False

        for line in header_footer:
            output_lines.append(line)
            if line.strip().lower() == '[events]':
                for item in cache_file.items:
                    for dialogue_line in line_generator(item):
                        output_lines.append(dialogue_line)
                events_written = True
        
        if not events_written:
             for item in cache_file.items:
                for dialogue_line in line_generator(item):
                    output_lines.append(dialogue_line)

        translation_file_path.write_text("\n".join(output_lines), encoding=pre_write_metadata.encoding)

    def _yield_translated_line(self, item: CacheItem) -> Iterator[str]:
        """生成单句翻译的Dialogue行"""
        if item.final_text:
            prefix = item.require_extra("dialogue_prefix")
            # 修改点 3: 从 extra 中获取行首标签，并与翻译文本组合
            leading_tags = item.extra.get("leading_tags", "")
            yield f"{prefix},{leading_tags}{item.final_text}"

    def _yield_bilingual_lines(self, item: CacheItem) -> Iterator[str]:
        """生成原文和译文两条Dialogue行"""
        prefix = item.require_extra("dialogue_prefix")
        # 修改点 4: 同样，在写回原文和译文时，都加上行首标签
        leading_tags = item.extra.get("leading_tags", "")
        
        if self._strip_text(item.source_text):
            # 组合行首标签和原文，以恢复原始行
            yield f"{prefix},{leading_tags}{item.source_text}"
        if self._strip_text(item.final_text):
            # 组合行首标签和译文
            yield f"{prefix},{leading_tags}{item.final_text}"

    def _strip_text(self, text: str):
        return (text or "").strip()

    @classmethod
    def get_project_type(cls):
        return ProjectType.ASS