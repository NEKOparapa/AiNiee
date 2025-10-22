### AssReader.py

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

class AssReader(BaseSourceReader):
    """
    ASS (Advanced SubStation Alpha) 字幕文件读取器。
    能够解析 [Events] 部分，并智能分离行首的样式标签和待翻译的文本。
    行首的样式标签 (如 {\an8\fs20}) 会被移除并暂存，
    而文本内部的格式标签 (如用于变色的 {\c&...&}) 会被保留。
    """
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.ASS

    @property
    def support_file(self):
        return "ass"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        lines = [line.lstrip("\ufeff") for line in file_path.read_text(encoding=pre_read_metadata.encoding).splitlines()]

        items = []
        header_lines = []
        in_events_section = False
        
        num_dialogue_fields = 10
        
        dialogue_pattern = re.compile(r"^\s*Dialogue:", re.IGNORECASE)
        format_pattern = re.compile(r"^\s*Format:", re.IGNORECASE)
        
        # 修改点 1: 定义一个只匹配行首 ASS 标签的正则表达式
        # ^      - 匹配字符串的开始
        # (\{.*?\})+ - 匹配一个或多个连续的 {...} 块
        leading_ass_tags_pattern = re.compile(r'^(\{.*?\})+')

        for line in lines:
            stripped_line = line.strip()

            if stripped_line.lower() == '[events]':
                in_events_section = True
                header_lines.append(line)
                continue

            if in_events_section:
                if format_pattern.match(stripped_line):
                    try:
                        fields_str = stripped_line.split(':', 1)[1]
                        fields = [field.strip() for field in fields_str.split(',')]
                        num_dialogue_fields = len(fields)
                    except IndexError:
                        pass
                    header_lines.append(line)
                    continue
                
                if dialogue_pattern.match(line):
                    try:
                        parts = line.split(',', num_dialogue_fields - 1)
                        
                        if len(parts) == num_dialogue_fields:
                            prefix = ",".join(parts[:-1])
                            raw_text_with_tags = parts[-1]
                            
                            # --- 修改点 2: 智能分离行首标签和文本 ---
                            leading_tags = ""
                            text_for_translation = raw_text_with_tags
                            
                            match = leading_ass_tags_pattern.match(raw_text_with_tags)
                            if match:
                                # 如果匹配成功，提取行首标签
                                leading_tags = match.group(0)
                                # 剩余部分作为待翻译文本
                                text_for_translation = raw_text_with_tags[len(leading_tags):]

                            item = CacheItem(
                                source_text=text_for_translation,
                                extra={
                                    "dialogue_prefix": prefix,
                                    "leading_tags": leading_tags  # 存储行首标签
                                }
                            )
                            items.append(item)
                        else:
                            header_lines.append(line)
                    except (ValueError, IndexError):
                        header_lines.append(line)
                else:
                    header_lines.append(line)
            else:
                header_lines.append(line)
        
        cache_file = CacheFile(items=items)
        cache_file.extra['ass_header_footer'] = header_lines
        
        return cache_file