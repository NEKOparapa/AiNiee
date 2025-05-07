from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class SrtReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.SRT

    @property
    def support_file(self):
        return "srt"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        # 读取文件内容并去除 BOM，即.lstrip("\ufeff")
        lines = [line.strip().lstrip("\ufeff") for line in file_path.read_text(encoding=pre_read_metadata.encoding).splitlines()]

        current_block = None
        items = []
        for line in lines:

            # 新字幕块开始
            if current_block is None:
                if line.isdigit():
                    current_block = {
                        "number": line,
                        "time": None,
                        "text": []
                    }
                continue

            # 处理时间轴
            if current_block["time"] is None:
                if "-->" in line:
                    current_block["time"] = line
                else:
                    # 时间轴格式错误，丢弃当前块
                    current_block = None
                continue

            # 处理文本内容
            if not line:
                # 遇到空行，保存当前块
                items.append(self._block_to_item(current_block))
                current_block = None
            else:
                current_block["text"].append(line)

        # 处理文件末尾未以空行结束的情况
        if current_block is not None:
            items.append(self._block_to_item(current_block))
        return CacheFile(items=items)

    def _block_to_item(self, block):
        source_text = "\n".join(block["text"])
        extra = {"subtitle_number": block["number"], "subtitle_time": block["time"]}
        item = CacheItem(source_text=source_text, extra=extra)
        return item
