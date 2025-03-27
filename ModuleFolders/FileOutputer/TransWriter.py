import json
import os
import shutil


class TransWriter:
    def __init__(self):
        pass

    def output_trans_file(self, cache_data, output_path, input_path):
        # 创建输出目录并复制原始的.trans文件
        os.makedirs(output_path, exist_ok=True)
        TransWriter._copy_trans_files(self,input_path, output_path)

        # 按输出目录中的目标文件路径分组数据
        file_map = {}
        # 跳过第一个元素，项目类型标记
        for item in cache_data[1:]:

            # 构建在输出目录中的完整路径
            full_output_path = os.path.join(output_path, item["storage_path"])
            file_map.setdefault(full_output_path, []).append(item)

        # 处理每个需要修改的文件
        for file_path, items_to_update in file_map.items():
            # 读取目标文件内容
            with open(file_path, "r", encoding="utf-8") as f:
                trans_content = json.load(f)

            # 根据该文件的项更新翻译
            for item in items_to_update:
                file_category = item["file_category"]
                data_index = item["data_index"]
                new_translation = item["translated_text"]

                # 导航并更新，带有检查
                category_data = trans_content["project"]["files"][file_category]
                data_list = category_data["data"]

                # 仅当翻译实际改变时才写入
                if data_list[data_index][1] != new_translation:
                    data_list[data_index][1] = new_translation

            # 写回修改后的内容
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(trans_content, f, ensure_ascii=False, indent=4)

    # 复制trans文件
    def _copy_trans_files(self, input_path, output_path):
        for dirpath, _, filenames in os.walk(input_path):
            for filename in filenames:
                if filename.endswith('.trans'):
                    src = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(src, input_path)
                    dst = os.path.join(output_path, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
