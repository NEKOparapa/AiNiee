from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileReader.BaseReader import (
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
                if "-->" in line:
                    # 部分SRT没有cue序号行，时间轴行直接开始一个块
                    # （与VTT同类bug：序号非纯数字或缺失时，旧逻辑把整个文件丢弃）
                    current_block = {
                        "number": None,
                        "time": line,
                        "text": []
                    }
                elif line:
                    # cue标识行不一定是纯数字（如"cue-1"）；若下一行不是时间轴则整块按原逻辑丢弃
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
        # 与VttReader一致：仅在存在cue标识时保存subtitle_number，writer据此决定是否还原
        extra = {"subtitle_time": block["time"]}
        if block["number"] is not None:
            extra["subtitle_number"] = block["number"]
        item = CacheItem(source_text=source_text, extra=extra)
        return item
