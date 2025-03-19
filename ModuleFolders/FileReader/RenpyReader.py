import os


class RenpyReader():
    def __init__(self):
        pass


    def read_renpy_files(self, folder_path):
        """读取rpy文件并提取翻译条目"""
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
                        source = RenpyReader._extract_quoted(self,stripped)
                        translated = None
                        new_line_num = None

                        # 查找后续的new行
                        for j in range(i+1, len(lines)):
                            j_stripped = lines[j].strip()
                            if j_stripped.startswith("new"):
                                translated = RenpyReader._extract_quoted(self,j_stripped)
                                new_line_num = j
                                break

                        if translated is not None:
                            entries.append({
                                "source": source,
                                "translated": translated,
                                "new_line_num": new_line_num,
                                "file": file,
                                "rel_path": rel_path
                            })
                            i = j  # 跳过已处理的new行
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
                        "new_line_num": entry["new_line_num"]
                    })
                    text_index += 1

        return data

    def _extract_quoted(self, line):
        """从形如 old "text" 的行中提取引号内容"""
        try:
            return line.split('"', 2)[1]
        except IndexError:
            return ""