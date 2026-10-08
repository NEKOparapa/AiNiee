import re
from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class VttReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.VTT

    @property
    def support_file(self):
        return "vtt"

    # 支持可选小时位(1-2位)、MM:SS.mmm形式、逗号/点号毫秒分隔
    TIME_CODE_PATTERN = re.compile(
        r"(?:(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3}) --> (?:(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3})"
    )

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        content = file_path.read_text(encoding=pre_read_metadata.encoding)
        # 去除UTF-8 BOM，避免影响首行 WEBVTT 头与首个cue的解析
        content = content.lstrip('\ufeff').strip()

        header, body = self._split_header_body(content)
        blocks = self._split_blocks(body)

        items = []
        for block in blocks:
            item = self._parse_block(block)
            if item is not None:
                items.append(item)
        return CacheFile(items=items, extra={"top_text": header})

    def _split_header_body(self, content):
        parts = content.split('\n\n', 1)
        return parts[0], parts[1] if len(parts) > 1 else ''

    def _split_blocks(self, body):
        return [b.strip() for b in re.split(r'\n{2,}', body) if b.strip()]

    def _parse_block(self, block):

        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            return None

        # 定位时间轴行（前面可能存在cue序号/标识行，如ffmpeg输出的 "1"）
        time_idx = -1
        for idx, line in enumerate(lines[:2]):  # 标识行最多一行，检查前两行即可
            if self.TIME_CODE_PATTERN.search(line):
                time_idx = idx
                break
        if time_idx == -1:
            return None

        full_timecode = lines[time_idx]

        # 收集文本内容
        text_lines = []
        for line in lines[time_idx + 1:]:
            if self.TIME_CODE_PATTERN.search(line):  # 防止异常时间轴
                break
            text_lines.append(line)

        source_text = '\n'.join(text_lines).strip()
        if not source_text:
            return None

        return CacheItem(
            source_text=source_text,
            extra={"subtitle_time": full_timecode},
        )
