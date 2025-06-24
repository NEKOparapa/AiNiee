import polib
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)

class PoReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)


    @classmethod
    def get_project_type(cls):
        return ProjectType.PO 

    @property
    def support_file(self):
        return "po"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        """
        读取并解析 .po 文件。
        """
        # polib 能够很好地处理编码，我们使用它来加载文件
        po_file = polib.pofile(str(file_path), encoding=pre_read_metadata.encoding)

        items = []
        for entry in po_file:
            # 跳过过时(obsolete)的条目和头部条目
            if entry.obsolete or not entry.msgid:
                continue

            # 将所有元数据存储在 extra 字典中，以便写回
            extra = {
                'msgctxt': entry.msgctxt,
                'msgid_plural': entry.msgid_plural,
                'comment': entry.comment,
                'tcomment': entry.tcomment,
                'occurrences': entry.occurrences,
                'flags': entry.flags,
                'previous_msgid': entry.previous_msgid,
                'previous_msgctxt': entry.previous_msgctxt,
                'linenum': entry.linenum
            }
            
            # source_text 就是 msgid
            # 对于复数形式，只翻译单数形式的 msgid。
            # 更复杂的复数处理需要修改 CacheItem 和翻译流程。
            item = CacheItem(source_text=entry.msgid, extra=extra)
            items.append(item)

        # 将文件级别的元数据（如文件头）保存在 CacheFile 的 extra 中
        file_extra = {
            'metadata': po_file.metadata,
            'header': po_file.header
        }
        
        return CacheFile(items=items, extra=file_extra)