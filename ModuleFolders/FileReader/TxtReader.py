import os


class TxtReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构Txt小说文件
    def read_txt_files (self,folder_path):

        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Txt",
        })

        #文本索引初始值
        i = 1

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 JSON 文件
                if file.endswith(".txt"):
                    file_path = os.path.join(root, file) # 构建文件路径
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    storage_path = os.path.relpath(file_path, folder_path)
                    file_name = file

                    # 切行
                    lines = content.split('\n')


                    for j, line in enumerate(lines):
                        if line.strip() == '': # 跳过空行
                            continue
                        spaces = len(line) - len(line.lstrip()) # 获取行开头的空格数

                        if j < len(lines) - 1 and lines[j + 1].strip() == '': # 检查当前行是否是文本中的最后一行,并检测下一行是否为空行
                            if (j+1) < len(lines) - 1 and lines[j + 2].strip() == '': # 再检查下下行是否为空行，所以最多只会保留2行空行信息
                                # 将数据存储在字典中
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": line,
                                    "translated_text": line,
                                    "model": "none",
                                    "sentence_indent": spaces,
                                    "line_break":2,
                                    "storage_path": storage_path,
                                    "file_name": file_name,
                                })
                            else:
                                # 将数据存储在字典中
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": line,
                                    "translated_text": line,
                                    "model": "none",
                                    "sentence_indent": spaces,
                                    "line_break":1,
                                    "storage_path": storage_path,
                                    "file_name": file_name,
                                })

                        else:
                            # 将数据存储在字典中
                            json_data_list.append({
                                "text_index": i,
                                "translation_status": 0,
                                "source_text": line,
                                "translated_text": line,
                                "model": "none",
                                "sentence_indent": spaces,
                                "line_break":0,
                                "storage_path": storage_path,
                                "file_name": file_name,
                            })

                        i += 1


        return json_data_list
