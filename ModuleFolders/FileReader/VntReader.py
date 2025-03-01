import json
import os


class VntReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构VNText导出文件
    def read_vnt_files (self,folder_path):

        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Vnt",
        })

        #文本索引初始值
        i = 1

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 JSON 文件
                if file.endswith(".json"):
                    file_path = os.path.join(root, file) # 构建文件路径
                    
                    # 读取 JSON 文件内容
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        json_data = json.load(json_file)

                        # 提取键值对
                        for entry in json_data:
                            # 根据 JSON 文件内容的数据结构，获取相应字段值
                            source_text = entry["message"]
                            storage_path = os.path.relpath(file_path, folder_path) 
                            file_name = file

                            name = entry.get("name")
                            if name:

                                # 拼接人名和文本
                                source_text = VntReader.combine_srt(self,name,source_text)

                                # 将数据存储在字典中
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": source_text,
                                    "translated_text": source_text,
                                    "name": name,
                                    "model": "none",
                                    "storage_path": storage_path,
                                    "file_name": file_name,
                                })
                            else:
                                # 将数据存储在字典中
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": source_text,
                                    "translated_text": source_text,
                                    "model": "none",
                                    "storage_path": storage_path,
                                    "file_name": file_name,
                                })

                            # 增加文本索引值
                            i = i + 1

        return json_data_list

    # 辅助函数，拼接人名与文本
    def combine_srt(self,srt1, srt2):
        if srt2 and srt2[0] == '「':  # 检查 srt2 不为空 且 第一个字符是 '['
            return srt1 + srt2
        else:
            return srt1 + '「' + srt2
