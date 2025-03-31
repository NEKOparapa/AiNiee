import os
import shutil

# 改进点:现在还没能正确处理文本中含有双引号的问题
class RenpyWriter():
    def __init__(self):
        pass

    def output_renpy_file(self, data, output_path, input_path):
        """写入翻译后的rpy文件，兼容两种格式"""

        # 创建输出目录并复制原始文件
        os.makedirs(output_path, exist_ok=True)
        RenpyWriter._copy_renpy_files(self,input_path, output_path)

        # 按文件分组数据
        file_map = {}
        for item in data:
            if "new_line_num" not in item:
                continue

            full_path = os.path.join(output_path, item["storage_path"])
            file_map.setdefault(full_path, []).append(item)

        # 处理每个文件
        for file_path, items in file_map.items():
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 按行号降序排序避免修改影响
            sorted_items = sorted(items, key=lambda x: x["new_line_num"], reverse=True)

            for item in sorted_items:
                line_num = item["new_line_num"]
                if line_num >= len(lines):
                    continue

                new_trans = item["translated_text"]
                format_type = item["format_type"]

                if format_type == "old_new":
                    old_line = lines[line_num]
                    # 保留原格式生成新行
                    parts = old_line.split('"', 2)
                    if len(parts) >= 3:
                        new_line = f'{parts[0]}"{new_trans}"{parts[2]}'
                        lines[line_num] = new_line
                elif format_type == "comment_tag":
                    old_line = lines[line_num]
                    tag = item["tag"]
                    # 保留tag生成新行
                    parts = old_line.split('"', 1)
                    if len(parts) >= 2:
                        new_line = f'    {tag} "{new_trans}{parts[1][len(parts[1].split("\"",1)[0]):]}' # fix for tag with space
                        lines[line_num] = new_line


            # 写回文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)


    # 复制renpy文件
    def _copy_renpy_files(self, input_path, output_path):
        for dirpath, _, filenames in os.walk(input_path):
            for filename in filenames:
                if filename.endswith('.rpy'):
                    src = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(src, input_path)
                    dst = os.path.join(output_path, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)