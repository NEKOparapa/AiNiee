import json
import os


class ParatranzReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构Paratranz json 文件
    def read_paratranz_files(self, folder_path):
        # 待处理的json接口例
        # [
        #     {
        #         "key": "Activate",
        #         "original": "カードをプレイ",
        #         "translation": "出牌",
        #         "context": null
        #     }
        # ]
        # 缓存数据结构示例
        ex_cache_data = [
            {'project_type': 'Paratranz'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！',
             'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json', 'key': 'txtKey',
             'context': ''},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ',
             'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json', 'key': 'txtKey',
             'context': ''},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ',
             'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json',
             'file_name': 'Replace the original text.json', 'key': 'txtKey', 'context': ''},
        ]

        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Paratranz"
        })

        # 文本索引初始值
        i = 1

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 JSON 文件
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)  # 构建文件路径

                    # 读取 JSON 文件内容
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        json_data = json.load(json_file)

                        # 提取键值对
                        for item in json_data:
                            # 根据 JSON 文件内容的数据结构，获取相应字段值
                            source_text = item.get('original', '')  # 获取原文，如果没有则默认为空字符串
                            translated_text = item.get('translation', '')  # 获取翻译，如果没有则默认为空字符串
                            key = item.get('key', '')  # 获取键值，如果没有则默认为空字符串
                            context = item.get('context', '')  # 获取上下文信息，如果没有则默认为空字符串
                            storage_path = os.path.relpath(file_path, folder_path)
                            file_name = file
                            # 将数据存储在字典中
                            json_data_list.append({
                                "text_index": i,
                                "translation_status": 0,
                                "source_text": source_text,
                                "translated_text": translated_text,
                                "model": "none",
                                "storage_path": storage_path,
                                "file_name": file_name,
                                "key": key,
                                "context": context
                            })

                            # 增加文本索引值
                            i = i + 1

        return json_data_list