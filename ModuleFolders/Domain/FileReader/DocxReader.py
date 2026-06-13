from pathlib import Path
from bs4 import Tag

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileAccessor.DocxAccessor import DocxAccessor
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class DocxReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.file_accessor = DocxAccessor()

    @classmethod
    def get_project_type(cls):
        return ProjectType.DOCX

    @property
    def support_file(self):
        return 'docx'

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        xml_soup = self.file_accessor.read_content(file_path)
        
        # 1. 深度优先遍历所有元素，提取普通段落与表格单元格
        def traverse_elements(element, units):
            is_p = element.name == 'p' or element.name == 'w:p'
            is_tc = element.name == 'tc' or element.name == 'w:tc'
            if is_p:
                parent_tc = element.find_parent(lambda tag: tag and tag.name in ('tc', 'w:tc'))
                if not parent_tc:
                    units.append(('paragraph', element))
                    return
            elif is_tc:
                units.append(('table_cell', element))
                return
            for child in element.children:
                if isinstance(child, Tag):
                    traverse_elements(child, units)

        body = xml_soup.find(lambda tag: tag and tag.name in ('body', 'w:body'))
        units = []
        if body:
            traverse_elements(body, units)
            
        # 2. 对每个非空翻译单元构造标签包裹文本
        items = []
        valid_unit_index = 0
        for utype, elem in units:
            w_ts = elem.find_all(lambda tag: tag and tag.name in ('t', 'w:t'))
            valid_ts = [t for t in w_ts if t.string and t.string.strip()]
            if not valid_ts:
                continue
                
            # 使用 <t id="x"> 标签包裹 runs 的文本内容
            src_parts = []
            for t_idx, t in enumerate(valid_ts):
                src_parts.append(f'<t id="{t_idx}">{t.string}</t>')
            src_text = "".join(src_parts)
            
            item = CacheItem(source_text=src_text)
            item.extra['docx_unit_type'] = utype
            item.extra['docx_unit_index'] = valid_unit_index
            items.append(item)
            valid_unit_index += 1
            
        return CacheFile(items=items)
