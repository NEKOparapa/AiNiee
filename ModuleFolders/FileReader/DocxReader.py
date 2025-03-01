
import os
import shutil
import zipfile

from bs4 import BeautifulSoup #需要安装库pip install beautifulsoup4


class DocxReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构Docx文件
    def read_docx_files (self,folder_path):

        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Docx",
        })

        #文本索引初始值
        i = 1

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 docx 文件
                if file.endswith(".docx"):

                    # 构建文件的路径
                    file_path = os.path.join(root, file)  

                    # 构建解压文件夹路径
                    parent_path = os.path.dirname(file_path)
                    extract_path = os.path.join(parent_path, 'DocxCache')

                    # 创建暂存文件夹
                    if not os.path.exists(extract_path):
                        os.makedirs(extract_path)

                    # 解压docx文件到暂存文件夹中
                    with zipfile.ZipFile(file_path, 'r') as docx_file:
                        # 提取所有文件
                        docx_file.extractall(extract_path)

                    # 获取文件路径和文件名
                    storage_path = os.path.relpath(file_path, folder_path)
                    file_name = file

                    # 构建存储主要文本的文件路径
                    the_file_path = os.path.join(extract_path,'word', 'document.xml')


                    # 打开对应xml文件
                    with open(the_file_path, 'r', encoding='utf-8') as file:
                        # 读取文件内容
                        xml_soup = BeautifulSoup(file, 'xml')

                    # 使用BeautifulSoup解析，找到所有 w:t 标签
                    paragraphs = xml_soup.findAll('w:t')

                    # 过滤掉空的内容
                    filtered_matches = [match.string for match in paragraphs if match.string .strip()]

                    # 遍历每个标签，并提取文本内容
                    for text in filtered_matches:

                        # 检查一下是否提取到空文本内容和其他特殊内容
                        if text == "" or text == "\n" or text == " "or text == '\xa0':
                            continue

                        # 录入缓存
                        json_data_list.append({
                            "text_index": i,
                            "translation_status": 0,
                            "source_text": text,
                            "translated_text": text,
                            "model": "none",
                            "storage_path": storage_path,
                            "file_name": file_name,
                        })                                    
                        # 增加文本索引值
                        i = i + 1

            # 删除暂存文件夹
            shutil.rmtree(extract_path)

        return json_data_list
