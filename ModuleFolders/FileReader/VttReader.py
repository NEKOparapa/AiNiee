import re
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
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

    TIME_CODE_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})")

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        content = file_path.read_text(encoding=pre_read_metadata.encoding).strip()

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

        # 解析时间轴
        time_match = self.TIME_CODE_PATTERN.search(lines[0])
        if not time_match:
            return None

        full_timecode = lines[0]
        text_lines = []
        current_line = 1

        # 处理可能的序号
        if lines[0].isdigit() and len(lines) > 1:
            if self.TIME_CODE_PATTERN.search(lines[1]):
                full_timecode = lines[1]
                current_line += 1

        # 收集文本内容
        while current_line < len(lines):
            line = lines[current_line]
            if self.TIME_CODE_PATTERN.search(line):  # 防止异常时间轴
                break
            text_lines.append(line)
            current_line += 1

        source_text = '\n'.join(text_lines).strip()
        if not source_text:
            return None

        return CacheItem(
            source_text=source_text,
            extra={"subtitle_time": full_timecode},
        )
