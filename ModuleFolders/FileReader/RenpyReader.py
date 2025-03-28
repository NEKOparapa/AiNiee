import os
import re

class RenpyReader():
    def __init__(self):
        pass

    def read_renpy_files(self, folder_path):
        """读取rpy文件并提取翻译条目，兼容两种格式"""
        data = [{"project_type": "Renpy"}]
        text_index = 1

        for root, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".rpy"):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)

                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                entries = []
                i = 0
                while i < len(lines):
                    line = lines[i].rstrip("\n")
                    stripped = line.strip()

                    if stripped.startswith("old"):
                        source = RenpyReader._extract_quoted(self, stripped)
                        translated = None
                        new_line_num = None
                        format_type = "old_new" # 标记格式类型

                        # 查找后续的new行
                        for j in range(i + 1, len(lines)):
                            j_stripped = lines[j].strip()
                            if j_stripped.startswith("new"):
                                translated = RenpyReader._extract_quoted(self, j_stripped)
                                new_line_num = j
                                break

                        if translated is not None:
                            entries.append({
                                "source": source,
                                "translated": translated,
                                "new_line_num": new_line_num,
                                "file": file,
                                "rel_path": rel_path,
                                "format_type": format_type # 记录格式类型
                            })
                            i = j  # 跳过已处理的new行

                    elif stripped.startswith("#"):
                        new_format_match = re.match(r'#\s*([a-zA-Z]+(?: [a-zA-Z]+)?)\s*"(.*?)"', stripped)
                        if new_format_match:
                            tag = new_format_match.group(1)
                            source = new_format_match.group(2)
                            code_line_num = i + 1
                            if code_line_num < len(lines):
                                code_line = lines[code_line_num].strip()
                                code_line_tag_match = re.match(r'([a-zA-Z]+(?: [a-zA-Z]+)?)\s*"(.*?)"', code_line)
                                if code_line_tag_match and code_line_tag_match.group(1) == tag:
                                    format_type = "comment_tag" # 标记格式类型
                                    entries.append({
                                        "source": source,
                                        "translated": source, # 初始译文与原文相同
                                        "new_line_num": code_line_num, # 指向代码行
                                        "file": file,
                                        "rel_path": rel_path,
                                        "format_type": format_type, # 记录格式类型
                                        "tag": tag # 记录tag
                                    })
                                    i = code_line_num # 跳过已处理的代码行


                    i += 1

                # 格式化为统一数据结构
                for entry in entries:
                    data.append({
                        "text_index": text_index,
                        "translation_status": 0,
                        "source_text": entry["source"],
                        "translated_text": entry["translated"],
                        "model": "none",
                        "storage_path": entry["rel_path"],
                        "file_name": entry["file"],
                        "new_line_num": entry["new_line_num"],
                        "format_type": entry["format_type"], # 保留格式类型
                        **({"tag": entry["tag"]} if "tag" in entry else {}) # 可选地保留tag
                    })
                    text_index += 1

        return data

    def _extract_quoted(self, line):
        """从形如 old "text" 的行中提取引号内容"""
        try:
            return line.split('"', 2)[1]
        except IndexError:
            return ""