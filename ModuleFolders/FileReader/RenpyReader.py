import re
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class RenpyReader(BaseSourceReader):
    """读取rpy文件并提取翻译条目，兼容两种格式"""
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Renpy"

    @property
    def support_file(self):
        return "rpy"

    NEW_FORMAT_PARTTERN = re.compile(r'#\s*([a-zA-Z]+(?: [a-zA-Z]+)?)\s*"(.*?)"')
    CODE_LINE_TAG_PATTERN = re.compile(r'([a-zA-Z]+(?: [a-zA-Z]+)?)\s*"(.*?)"')

    def read_source_file(self, file_path: Path, cache_project: CacheProject) -> list[CacheItem]:
        lines = file_path.read_text(encoding="utf-8").splitlines()

        entries = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("old"):
                source = self._extract_quoted(stripped)
                translated = None
                new_line_num = None
                format_type = "old_new"  # 标记格式类型

                # 查找后续的new行
                for j in range(i + 1, len(lines)):
                    j_stripped = lines[j].strip()
                    if j_stripped.startswith("new"):
                        translated = self._extract_quoted(j_stripped)
                        new_line_num = j
                        break

                if translated is not None:
                    entries.append({
                        "source": source,
                        "translated": translated,
                        "new_line_num": new_line_num,
                        "format_type": format_type  # 记录格式类型
                    })
                    i = j  # 跳过已处理的new行

            elif stripped.startswith("#"):
                new_format_match = re.match(self.NEW_FORMAT_PARTTERN, stripped)
                if new_format_match:
                    tag = new_format_match.group(1)
                    source = new_format_match.group(2)
                    code_line_num = i + 1
                    if code_line_num < len(lines):
                        code_line = lines[code_line_num].strip()
                        code_line_tag_match = re.match(self.CODE_LINE_TAG_PATTERN, code_line)
                        if code_line_tag_match and code_line_tag_match.group(1) == tag:
                            format_type = "comment_tag"  # 标记格式类型
                            entries.append({
                                "source": source,
                                "translated": source,  # 初始译文与原文相同
                                "new_line_num": code_line_num,  # 指向代码行
                                "format_type": format_type,  # 记录格式类型
                                "tag": tag  # 记录tag
                            })
                            i = code_line_num  # 跳过已处理的代码行
            i += 1
        items = []
        # 格式化为统一数据结构
        for entry in entries:
            item = text_to_cache_item(entry["source"], entry["translated"])
            item.new_line_num = entry["new_line_num"]
            item.format_type = entry["format_type"]
            if 'tag' in entry:
                item.tag = entry["tag"]  # 可选地保留tag
            items.append(item)
        return items

    def _extract_quoted(self, line):
        """从形如 old "text" 的行中提取引号内容"""
        try:
            return line.split('"', 2)[1]
        except IndexError:
            return ""
