import re
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class LrcReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Lrc"

    @property
    def support_file(self):
        return "lrc"

    TITLE_PATTERN = re.compile(r'\[ti:(.*?)]')
    TIMESTAMP_LYRIC_PATTERN = re.compile(r'(\[([0-9:.]+)])(.*)')

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        content = file_path.read_text(encoding=detected_encoding)

        # 切行
        lyrics = content.splitlines()
        items = []
        subtitle_title = ''
        for line in lyrics:

            # 使用正则表达式匹配标题标签行
            title_match = self.TITLE_PATTERN.search(line)

            # 返回匹配到的标题全部内容
            if title_match:
                subtitle_title = title_match.group(1)

            # 使用正则表达式匹配时间戳和歌词内容
            match = self.TIMESTAMP_LYRIC_PATTERN.match(line)
            if match:
                timestamp = match.group(2)
                source_text = match.group(3).strip()
                if source_text == "":
                    continue

                item = text_to_cache_item(source_text)
                item.subtitle_time = timestamp
                if subtitle_title:
                    item.subtitle_title = subtitle_title
                    subtitle_title = ''
                items.append(item)
        return items
