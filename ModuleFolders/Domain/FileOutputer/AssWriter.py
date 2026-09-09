### AssWriter.py

from itertools import count
from pathlib import Path
from typing import Callable, Iterator

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
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

        # Dialogue行必须写在[Events]节的Format:行之后：reader把[Events]后的Format:行、
        # Comment:行和解析失败的Dialogue行都存进了header_footer，旧实现一遇到[events]就
        # 插入全部Dialogue，导致Format:行跑到所有Dialogue之后（严格解析器会按默认字段顺序误读）
        pre_events = []
        post_events_header = []
        in_events = False
        for line in header_footer:
            if line.strip().lower() == '[events]':
                in_events = True
                pre_events.append(line)
                continue
            (post_events_header if in_events else pre_events).append(line)

        output_lines = []
        output_lines.extend(pre_events)

        # 找到Format:行的位置，Dialogue插在其后；没有Format:行时紧跟[Events]
        insert_at = 0
        for idx, line in enumerate(post_events_header):
            if line.strip().lower().startswith('format:'):
                insert_at = idx + 1
                break

        output_lines.extend(post_events_header[:insert_at])
        for item in cache_file.items:
            for dialogue_line in line_generator(item):
                output_lines.append(dialogue_line)
        output_lines.extend(post_events_header[insert_at:])

        translation_file_path.write_text("\n".join(output_lines), encoding=pre_write_metadata.encoding)

    def _yield_translated_line(self, item: CacheItem) -> Iterator[str]:
        """生成单句翻译的Dialogue行"""
        if item.final_text:
            prefix = item.require_extra("dialogue_prefix")
            # 修改点 3: 从 extra 中获取行首标签，并与翻译文本组合
            leading_tags = item.extra.get("leading_tags", "")
            # 真实换行会截断Dialogue行，ASS的行内换行必须用 \N
            text = item.final_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\N")
            yield f"{prefix},{leading_tags}{text}"

    def _yield_bilingual_lines(self, item: CacheItem) -> Iterator[str]:
        """生成原文和译文两条Dialogue行"""
        prefix = item.require_extra("dialogue_prefix")
        # 修改点 4: 同样，在写回原文和译文时，都加上行首标签
        leading_tags = item.extra.get("leading_tags", "")

        if self._strip_text(item.source_text):
            # 组合行首标签和原文，以恢复原始行
            yield f"{prefix},{leading_tags}{item.source_text}"
        if self._strip_text(item.final_text):
            # 组合行首标签和译文（换行转\N，同上）
            text = item.final_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\N")
            yield f"{prefix},{leading_tags}{text}"

    def _strip_text(self, text: str):
        return (text or "").strip()

    @classmethod
    def get_project_type(cls):
        return ProjectType.ASS