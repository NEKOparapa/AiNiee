import os
import re


class LrcReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构Lrc音声文件
    def read_lrc_files (self,folder_path):
        # 缓存数据结构示例
        ex_cache_data = [
        {'project_type': 'Mtool'},
        {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！', 'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json'},
        {'text_index': 2, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ', 'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json'},
        {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ', 'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json', 'file_name': 'Replace the original text.json'},
        ]


        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Lrc",
        })

        #文本索引初始值
        i = 1
        subtitle_title = ""

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 JSON 文件
                if file.endswith(".lrc"):
                    file_path = os.path.join(root, file) # 构建文件路径
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 切行
                    lyrics = content.split('\n')
                    for line in lyrics:

                        # 使用正则表达式匹配标题标签行
                        title_pattern = re.compile(r'\[ti:(.*?)\]')
                        match = title_pattern.search(line)
                        if match:
                            subtitle_title =  match.group(1)  # 返回匹配到的标题全部内容


                        # 使用正则表达式匹配时间戳和歌词内容
                        pattern = re.compile(r'(\[([0-9:.]+)\])(.*)')
                        match = pattern.match(line)
                        if match:
                            timestamp = match.group(2)
                            source_text = match.group(3).strip()
                            if source_text == "":
                                continue
                            storage_path = os.path.relpath(file_path, folder_path)
                            file_name = file

                            if subtitle_title:                             
                                # 将数据存储在字典中
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": source_text,
                                    "translated_text": source_text,
                                    "model": "none",
                                    "subtitle_time": timestamp,
                                    "subtitle_title":subtitle_title,
                                    "storage_path": storage_path,
                                    "file_name": file_name,
                                })
                                subtitle_title = ""

                            else:
                                # 将数据存储在字典中
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": source_text,
                                    "translated_text": source_text,
                                    "model": "none",
                                    "subtitle_time": timestamp,
                                    "storage_path": storage_path,
                                    "file_name": file_name,
                                })

                            # 增加文本索引值
                            i += 1

        return json_data_list