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
    TIMESTAMP_LYRIC_PATTERN = re.compile(r'(\[([0-9:.]+)])(.*)')

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        content = file_path.read_text(encoding=pre_read_metadata.encoding)

        # 切行
        lyrics = content.splitlines()
        items = []
        subtitle_title = ''
        for line in lyrics:

            # 使用正则表达式匹配标题标签行
            title_match = self.TITLE_PATTERN.search(line)

            # 返回匹配到的标题全部内容
            if title_match and not subtitle_title:
                subtitle_title = title_match.group(1)

            # 使用正则表达式匹配时间戳和歌词内容
            match = self.TIMESTAMP_LYRIC_PATTERN.match(line)
            if match:
                timestamp = match.group(2)
                source_text = match.group(3).strip()
                if source_text == "":
                    continue
                item_extra = {"subtitle_time": timestamp}
                items.append(CacheItem(source_text=source_text, extra=item_extra))
        file_extra = {"subtitle_title": subtitle_title}
        return CacheFile(items=items, extra=file_extra)
