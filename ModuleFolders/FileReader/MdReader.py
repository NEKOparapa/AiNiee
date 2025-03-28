import os

class MdReader:
    def __init__(self):
        pass

    def read_md_files(self, folder_path):
        """读取指定文件夹下的Markdown文件并结构化存储"""
        json_data_list = [{"project_type": "Md"}]
        text_index = 1

        for root, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".md"):
                    continue

                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                storage_path = os.path.relpath(file_path, folder_path)
                lines = content.split('\n')

                for j, line in enumerate(lines):
                    if not line.strip():
                        continue

                    # 计算缩进和后续空行
                    leading_spaces = len(line) - len(line.lstrip())
                    consecutive_empty = MdReader._count_consecutive_empty(self,lines, j)
                    
                    json_data_list.append({
                        "text_index": text_index,
                        "translation_status": 0,
                        "source_text": line,
                        "translated_text": line,
                        "model": "none",
                        "sentence_indent": leading_spaces,
                        "line_break": min(consecutive_empty, 2),
                        "original_line": line,
                        "storage_path": storage_path,
                        "file_name": os.path.basename(file),
                    })
                    text_index += 1

        return json_data_list

    def _count_consecutive_empty(self, lines, current_index):
        """统计当前行后续连续空行数"""
        count = 0
        next_index = current_index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            count += 1
            next_index += 1
        return count
