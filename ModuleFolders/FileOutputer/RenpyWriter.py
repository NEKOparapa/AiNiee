import os
import shutil


class RenpyWriter():
    def __init__(self):
        pass

    def output_renpy_file(self, data, output_path, input_path):
        """写入翻译后的rpy文件"""
        # 先复制整个目录结构
        if os.path.exists(output_path):
            shutil.rmtree(output_path)
        shutil.copytree(input_path, output_path)

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

                old_line = lines[line_num]
                new_trans = item["translated_text"]

                # 保留原格式生成新行
                parts = old_line.split('"', 2)
                if len(parts) >= 3:
                    new_line = f'{parts[0]}"{new_trans}"{parts[2]}'
                    lines[line_num] = new_line

            # 写回文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
