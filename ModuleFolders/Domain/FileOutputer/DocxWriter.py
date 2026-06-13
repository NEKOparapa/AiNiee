from pathlib import Path
from bs4 import Tag

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileAccessor.DocxAccessor import DocxAccessor
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class DocxWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)
        self.file_accessor = DocxAccessor()

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        import re
        content = self.file_accessor.read_content(source_file_path)
        
        # 1. 采用与 Reader 相同的提取算法，保证索引完全对齐
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

        body = content.find(lambda tag: tag and tag.name in ('body', 'w:body'))
        units = []
        if body:
            traverse_elements(body, units)
            
        # 2. 筛选出非空有效单元
        valid_xml_units = []
        for utype, elem in units:
            w_ts = elem.find_all(lambda tag: tag and tag.name in ('t', 'w:t'))
            valid_ts = [t for t in w_ts if t.string and t.string.strip()]
            if valid_ts:
                valid_xml_units.append((utype, valid_ts))
                
        # 3. 遍历缓存项，精准替换文本
        for item in cache_file.items:
            unit_idx = item.extra.get('docx_unit_index')
            if unit_idx is None or unit_idx >= len(valid_xml_units):
                continue
                
            _, valid_ts = valid_xml_units[unit_idx]
            translated_text = item.final_text
            
            # 使用正则解析标签
            matches = re.findall(r'<t id="(\d+)">([\s\S]*?)</t>', translated_text)
            translated_map = {int(tid): text for tid, text in matches}
            
            # 4. 稳健性兜底：若大模型破坏了标签（匹配率低于50%）
            if len(translated_map) < len(valid_ts) * 0.5:
                # 去除所有标签，把纯译文写入第一个 run，其他 run 清空
                clean_text = re.sub(r'<t id="\d+">|</t>', '', translated_text)
                if valid_ts:
                    valid_ts[0].string = clean_text
                    if clean_text.startswith(' ') or clean_text.endswith(' '):
                        valid_ts[0]['xml:space'] = 'preserve'
                    for t in valid_ts[1:]:
                        t.string = ""
            else:
                # 正常回写每个标签内容
                for t_idx, t in enumerate(valid_ts):
                    if t_idx in translated_map:
                        t.string = translated_map[t_idx]
                        if t.string.startswith(' ') or t.string.endswith(' '):
                            t['xml:space'] = 'preserve'
                            
        self.file_accessor.write_content(
            content, translation_file_path, source_file_path
        )

    @classmethod
    def get_project_type(self):
        return ProjectType.DOCX
