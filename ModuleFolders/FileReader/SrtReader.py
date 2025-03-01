import json
import os


class SrtReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构Srt字幕文件
    def read_srt_files (self,folder_path):

        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Srt",
        })

        #文本索引初始值
        i = 1
        source_text = ''
        subtitle_number = ''
        subtitle_time = ''

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 srt 文件
                if file.endswith(".srt"):
                    file_path = os.path.join(root, file) # 构建文件路径
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 将内容按行分割,并除去换行
                    lines = content.split('\n')
                    # 计数变量
                    j = 1

                    # 遍历每一行
                    for line in lines:

                        # 去除行首的BOM（如果存在）
                        line = line.lstrip('\ufeff')

                        # 如果行是数字，代表新的字幕开始
                        if line.isdigit() and (line == str(j)):
                            subtitle_number = line

                        # 时间码行
                        elif ' --> ' in line:
                            subtitle_time = line

                        # 空行代表字幕文本的结束
                        elif line == '':
                            storage_path = os.path.relpath(file_path, folder_path) 
                            file_name = file
                            # 将数据存储在字典中
                            json_data_list.append({
                                "text_index": i,
                                "translation_status": 0,
                                "source_text": source_text,
                                "translated_text": source_text,
                                "model": "none",
                                "subtitle_number": subtitle_number,
                                "subtitle_time": subtitle_time,
                                "storage_path": storage_path,
                                "file_name": file_name,
                            })

                            # 增加文本索引值
                            i = i + 1
                            j = j + 1
                            # 清空变量
                            source_text = ''
                            subtitle_number = ''
                            subtitle_time = ''

                        # 其他行是字幕文本，需要添加到文本中
                        else:
                            if  source_text:
                                source_text += '\n' + line
                            else:
                                source_text = line

        return json_data_list

