import os
import re
import shutil
import zipfile


import ebooklib #需要安装库pip install ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup #需要安装库pip install beautifulsoup4


class EpubReader():
    def __init__(self):
        pass


    # 读取文件夹中树形结构Epub文件
    def read_epub_files (self,folder_path):

        # 创建缓存数据，并生成文件头信息
        json_data_list = []
        json_data_list.append({
            "project_type": "Epub",
        })

        #文本索引初始值
        i = 1

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 判断文件是否为 epub 文件
                if file.endswith(".epub"):

                    file_path = os.path.join(root, file)  # 构建文件路径

                    # 构建解压文件夹路径
                    parent_path = os.path.dirname(file_path)
                    extract_path = os.path.join(parent_path, 'EpubCache')

                    # 创建暂存文件夹
                    if not os.path.exists(extract_path):
                        os.makedirs(extract_path)

                    # 解压EPUB文件到暂存文件夹中
                    with zipfile.ZipFile(file_path, 'r') as epub_file:
                        # 提取所有文件
                        epub_file.extractall(extract_path)

                    # 加载EPUB文件
                    book = epub.read_epub(file_path)

                    # 获取文件路径和文件名
                    storage_path = os.path.relpath(file_path, folder_path)
                    book_name = file

                    # 遍历书籍中的所有内容
                    for item in book.get_items():
                        # 检查是否是文本内容
                        if item.get_type() == ebooklib.ITEM_DOCUMENT:


                            # 获取文件的唯一ID及文件名
                            item_id = item.get_id()
                            file_name = os.path.basename(item.get_name())

                            # 遍历文件夹中的所有文件,找到该文件，因为上面给的相对路径与epub解压后路径是不准的
                            for root_extract, dirs_extract, files_extract in os.walk(extract_path):
                                for filename in files_extract:
                                    # 如果文件名匹配
                                    if filename == file_name:
                                        # 构建完整的文件路径
                                        the_file_path = os.path.join(root_extract, filename)

                            # 打开对应HTML文件
                            with open(the_file_path, 'r', encoding='utf-8') as file:
                                # 读取文件内容
                                html_content = file.read()


                            # 获取文本内容并解码（为什么不用这个而进行解压操作呢，因为这个会自动将成对标签改为自适应标签）
                            #html_content = item.get_content().decode('utf-8')

                            # 正则表达式匹配<p>标签及其内容，包括自闭和的<p/>标签，<h1>到<h7>、以及<li>标签，text标签
                            p_pattern = r'<p[^>/]*>(.*?)</p>|<p[^>/]*/>|<h[1-7][^>/]*>(.*?)</h[1-7]>|<h[1-7][^>/]*/>|<li[^>/]*>(.*?)</li>|<li[^>/]*/>|<textp[^>/]*>(.*?)</ptext>|<text[^>/]*/>'

                            # 使用findall函数找到所有匹配的内容
                            paragraphs = re.findall(p_pattern, html_content, re.DOTALL)

                            # 过滤和处理匹配结果
                            filtered_matches = []
                            for match in paragraphs:
                                # findall 返回的是元组，我们需要找到元组中非空的字符串
                                text = next((x for x in match if x), '')
                                if text.strip():
                                    filtered_matches.append(text)

                            # 遍历每个p标签，并提取文本内容
                            for p in filtered_matches:
                                # 保留原html内容文本，方便后面直接按原字符整体替换
                                html_text = p

                                # 借用库自带的函数来提取纯文本，以免中间还有子标签，影响翻译效果
                                p_html = "<p>"+ p + "</p>"
                                soup = BeautifulSoup(p_html, 'html.parser')
                                text_content = soup.get_text()

                                # 去除前面的空格
                                text_content = text_content.lstrip()
                                html_text = html_text.lstrip() 

                                # 检查一下是否提取到空文本内容
                                if not text_content.strip():
                                    continue

                                # 获取项目的唯一ID
                                item_id = item.get_id()

                                # 录入缓存
                                json_data_list.append({
                                    "text_index": i,
                                    "translation_status": 0,
                                    "source_text": text_content,
                                    "translated_text": text_content,
                                    "html":html_text,
                                    "model": "none",
                                    "item_id": item_id,
                                    "storage_path": storage_path,
                                    "file_name": book_name,
                                })                                    
                                # 增加文本索引值
                                i = i + 1

                    # 删除文件夹
                    shutil.rmtree(extract_path)

        return json_data_list

