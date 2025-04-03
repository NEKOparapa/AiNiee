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
                file_category = item.get("file_category","")
                data_index = item.get("data_index","")
                new_translation = item.get("translated_text","")
                name = item.get("name","")

                # 导航并更新，带有检查
                category_data = trans_content["project"]["files"][file_category]
                data_list = category_data["data"]
                parameters_list = category_data["parameters"]

                # 如果有人名信息
                if name:
                    # 分割人名与文本
                    name,new_translation = TransWriter.extract_strings(self, name, new_translation)
                    # 更新人名翻译
                    parameters_list[data_index][0]["translation"] = name

                # 仅当翻译实际改变时才写入，译文文本在第二个元素
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


    def extract_strings(self, name, dialogue):
        if dialogue.startswith("["):
            # 计算原name中的"]"数量
            count_in_name = name.count("]")
            required_closing_brackets = count_in_name + 1  # 需要匹配的"]"总数
            current_pos = 0
            found_brackets = 0
            end_pos = -1

            # 查找第 (count_in_name + 1) 个"]"
            while found_brackets < required_closing_brackets:
                next_pos = dialogue.find("]", current_pos)
                if next_pos == -1:  # 没有足够的"]"，直接返回原值
                    break
                found_brackets += 1
                end_pos = next_pos  # 更新最后一个"]"的位置
                current_pos = next_pos + 1  # 继续往后搜索

            # 如果找到足够数量的"]"，则分割字符串
            if found_brackets == required_closing_brackets:
                extracted_name = dialogue[1:end_pos]
                remaining_dialogue = dialogue[end_pos+1:].lstrip()
                return (extracted_name, remaining_dialogue)
        
        # 其他情况直接返回原值
        return name, dialogue