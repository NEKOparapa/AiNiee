import os
import re
import shutil
import zipfile

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


class EpubReader():
    def __init__(self):
        pass

    def read_epub_files(self, folder_path):
        json_data_list = []
        json_data_list.append({
            "project_type": "Epub",
        })
        # 文本索引初始值
        i = 1

        # 遍历文件夹及其子文件夹
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".epub"):  # 判断文件是否为 epub 文件
                    file_path = os.path.join(root, file) # 构建文件路径
                    parent_path = os.path.dirname(file_path)
                    extract_path = os.path.join(parent_path, 'EpubCache') # 构建解压文件夹路径

                    if not os.path.exists(extract_path): # 创建暂存文件夹
                        os.makedirs(extract_path)

                    with zipfile.ZipFile(file_path, 'r') as epub_file: # 解压EPUB文件到暂存文件夹中
                        epub_file.extractall(extract_path)

                    book = epub.read_epub(file_path)  # 加载EPUB文件
                    storage_path = os.path.relpath(file_path, folder_path) # 获取文件路径和文件名
                    book_name = file

                    # 遍历书籍中的所有内容
                    for item in book.get_items():
                        # 检查是否是文本内容
                        if item.get_type() == ebooklib.ITEM_DOCUMENT:
                            # 获取文件的唯一ID及文件名
                            item_id = item.get_id()
                            file_name = os.path.basename(item.get_name())

                            # 遍历文件夹中的所有文件,找到该文件 (上面给的相对路径与epub解压后路径是不准的)
                            for root_extract, dirs_extract, files_extract in os.walk(extract_path):
                                for filename in files_extract:
                                    if filename == file_name:
                                        the_file_path = os.path.join(root_extract, filename)

                            with open(the_file_path, 'r', encoding='utf-8') as file:
                                html_content = file.read()
                                # 获取文本内容并解码（为什么不用这个而进行解压操作呢，因为这个会自动将成对标签改为自适应标签）
                                # html_content = item.get_content().decode('utf-8')

                            # 正则字典，只包含成对标签，暂不考虑自闭合标签
                            tag_patterns_dict = {
                                "p": r"<p[^>]*>(.*?)</p>",
                                "heading": r"<h[1-7][^>]*>(.*?)</h[1-7]>",
                                "li": r"<li[^>]*>(.*?)</li>",
                                "text": r"<text[^>]*>(.*?)</text>",
                                "div": r"<div[^>]*>(.*?)</div>",  # div标签要放在最后面，这是提取不到前面任何文本内容再考虑的标签
                            }
                            
                            for tag_type, pattern in tag_patterns_dict.items():
                                # 使用 finditer 查找所有匹配项，可以迭代处理
                                for match in re.finditer(pattern, html_content, re.DOTALL):
                                    html_text = match.group(0) # 完整匹配到的HTML标签

                                    # 提取纯文本，并处理嵌套标签
                                    soup = BeautifulSoup(html_text, 'html.parser')
                                    text_content = soup.get_text(strip=True)

                                    if not text_content: # 检查一下是否提取到空文本内容
                                        continue

                                    # 对div标签进行额外检查
                                    if tag_type == "div":
                                        # 检查是否包含禁止的子标签
                                        forbidden_tags = soup.find(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'text'])
                                        if forbidden_tags is not None:
                                            continue  # 跳过包含禁止标签的div

                                    json_data_list.append({
                                        "text_index": i,
                                        "translation_status": 0,
                                        "source_text": text_content,
                                        "translated_text": text_content,
                                        "original_html": html_text,
                                        "tag_type": tag_type, # 直接使用循环的 tag_type
                                        "model": "none",
                                        "item_id": item_id,
                                        "storage_path": storage_path,
                                        "file_name": book_name,
                                    })
                                    i += 1

                    shutil.rmtree(extract_path)

        return json_data_list
    