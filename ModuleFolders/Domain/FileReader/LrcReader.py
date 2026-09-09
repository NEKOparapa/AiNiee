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


class LrcReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.LRC

    @property
    def support_file(self):
        return "lrc"

    TITLE_PATTERN = re.compile(r'\[ti:(.*?)]')
    # 单行可携带多个时间戳（合并歌词 [00:01.00][00:30.00]文本），全部捕获
    TIMESTAMP_PATTERN = re.compile(r'\[([0-9:.]+)]')
    # 非歌词元数据行（保留原样输出）
    METADATA_PATTERN = re.compile(r'^\[[a-z]+:.*]', re.IGNORECASE)

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        content = file_path.read_text(encoding=pre_read_metadata.encoding)
        # 去除UTF-8 BOM，避免首行 [ti:...] / 首句歌词解析失败
        content = content.lstrip('\ufeff')

        # 切行
        lyrics = content.splitlines()
        items = []
        other_lines = []  # 非歌词行（元数据等），按原顺序保留
        subtitle_title = ''
        for line in lyrics:

            # 使用正则表达式匹配标题标签行
            title_match = self.TITLE_PATTERN.search(line)

            # 返回匹配到的标题全部内容
            if title_match and not subtitle_title:
                subtitle_title = title_match.group(1)
                continue

            # 非歌词元数据行（如[ar:][al:][offset:]），原样保留
            if self.METADATA_PATTERN.match(line) and not self.TIMESTAMP_PATTERN.match(line):
                other_lines.append(('raw', line))
                continue

            # 匹配歌词时间戳（可能多个）
            timestamps = self.TIMESTAMP_PATTERN.findall(line)
            if not timestamps:
                continue

            text = self.TIMESTAMP_PATTERN.sub('', line, count=0).strip()
            if text == "":
                continue
            for timestamp in timestamps:
                item_extra = {"subtitle_time": timestamp}
                items.append(CacheItem(source_text=text, extra=item_extra))
        file_extra = {"subtitle_title": subtitle_title, "other_lines": other_lines}
        return CacheFile(items=items, extra=file_extra)
