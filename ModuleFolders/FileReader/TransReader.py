import os
import json


class TransReader:
    def __init__(self):
        pass

    def read_trans_files(self, folder_path):
        cache_data = [{"project_type": "Trans"}] # 与示例类似的结构
        text_index = 1 # 每对文本的唯一索引


        for root, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".trans"):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)

                with open(file_path, "r", encoding="utf-8") as f:
                    trans_content = json.load(f)

                files_data = trans_content["project"]["files"]

                # 遍历每个文件类别（例如："data/Actors.json"）
                for file_category, category_data in files_data.items():

                    data_list = category_data.get("data", [])
                    tags_list = category_data.get("tags", []) # 如果缺失，默认为空列表

                    # 遍历每对文本 [原文，翻译]
                    for idx, text_pair in enumerate(data_list):

                        source_text = text_pair[0]
                        translated_text = text_pair[1]

                        # 确定该特定条目的标签
                        tags = None
                        if idx < len(tags_list):
                            tags = tags_list[idx] # 可能为 null 或类似 "red" 的字符串

                        # 存储提取的信息
                        cache_data.append({
                            "text_index": text_index,
                            "translation_status": 0, 
                            "source_text": source_text,
                            "translated_text": translated_text,
                            "tags": tags, 
                            "model": "none", 
                            "storage_path": rel_path, # .trans 文件的相对路径
                            "file_name": file, # .trans 文件的名称
                            "file_category": file_category, # 例如："data/Actors.json"
                            "data_index": idx, # 类别 "data" 列表中的索引
                        })
                        text_index += 1
        return cache_data
