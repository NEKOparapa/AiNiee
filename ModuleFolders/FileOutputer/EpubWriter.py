import os

import re
import shutil
import zipfile


import ebooklib # 需要安装库pip install ebooklib
from ebooklib import epub



class EpubWriter():
    def __init__(self):
        pass


    # 输出epub文件
    def output_epub_file(self,cache_data, output_path, input_path):

        # 创建中间存储文本
        text_dict = {}

        # 遍历缓存数据
        for item in cache_data:
            # 忽略不包含 'storage_path' 的项
            if 'storage_path' not in item:
                continue

            # 获取相对文件路径
            storage_path = item['storage_path']
            # 获取文件名
            file_name = item['file_name']

            if file_name != storage_path :
                # 构建文件输出路径
                file_path = f'{output_path}/{storage_path}'
                # 获取输出路径的上一级路径，使用os.path.dirname
                folder_path = os.path.dirname(file_path)
                # 如果路径不存在，则创建
                os.makedirs(folder_path, exist_ok=True)
            else:
                # 构建文件输出路径
                file_path = f'{output_path}/{storage_path}'


            # 如果文件路径已经在 path_dict 中，添加到对应的列表中
            if file_path in text_dict:
                text = {'translation_status': item['translation_status'],
                        'source_text': item['source_text'],
                        'translated_text': item['translated_text'],
                        'html': item['html'],
                        "item_id": item['item_id'],}
                text_dict[file_path].append(text)

            # 否则，创建一个新的列表
            else:
                text = {'translation_status': item['translation_status'],
                        'source_text': item['source_text'],
                        'translated_text': item['translated_text'],
                        'html': item['html'],
                        "item_id": item['item_id'],}
                text_dict[file_path] = [text]




        # 创建输出
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # 将输入路径里面的所有epub文件复制到输出路径
        for dirpath, dirnames, filenames in os.walk(input_path):
            for filename in filenames:
                # 检查文件扩展名是否为.epub
                if filename.endswith('.epub'):
                    # 构建源文件和目标文件的完整路径
                    src_file_path = os.path.join(dirpath, filename)
                    # 计算相对于输入路径的相对路径
                    relative_path = os.path.relpath(src_file_path, start=input_path)
                    # 构建目标文件的完整路径
                    dst_file_path = os.path.join(output_path, relative_path)

                    # 创建目标文件的目录（如果不存在）
                    os.makedirs(os.path.dirname(dst_file_path), exist_ok=True)
                    # 复制文件
                    shutil.copy2(src_file_path, dst_file_path)
                    #print(f'Copied: {src_file_path} -> {dst_file_path}')



        # 遍历 path_dict，并将内容写入对应文件中
        for file_path, content_list in text_dict.items():

            # 加载EPUB文件
            book = epub.read_epub(file_path)

            # 构建解压文件夹路径
            parent_path = os.path.dirname(file_path)
            extract_path = os.path.join(parent_path, 'EpubCache')

            # 创建解压文件夹
            if not os.path.exists(extract_path):
                os.makedirs(extract_path)

            # 使用zipfile模块打开并解压EPUB文件
            with zipfile.ZipFile(file_path, 'r') as epub_file:
                # 提取所有文件
                epub_file.extractall(extract_path)

            # 遍历书籍中的所有内容
            for item in book.get_items():
                # 检查是否是文本内容
                if item.get_type() == ebooklib.ITEM_DOCUMENT:

                    # 获取文件的唯一ID及文件名
                    item_id = item.get_id()
                    file_name = os.path.basename(item.get_name())

                    # 遍历文件夹中的所有文件,找到该文件，因为上面给的相对路径与epub解压后路径是不准的
                    for root, dirs, files in os.walk(extract_path):
                        for filename in files:
                            # 如果文件名匹配
                            if filename == file_name:
                                # 构建完整的文件路径
                                the_file_path = os.path.join(root, filename)

                    # 打开对应HTML文件
                    with open(the_file_path, 'r', encoding='utf-8') as file:
                        # 读取文件内容
                        content_html = file.read()

                    # 遍历缓存数据
                    for content in content_list:
                        # 如果找到匹配的文件id
                        if item_id == content['item_id']:
                            # 获取原文本
                            original = content['source_text']
                            # 获取翻译后的文本
                            replacement = content['translated_text']

                            # 获取html标签化的文本
                            html = content['html']
                            html = str(html)

                            # 删除 &#13;\n\t\t\t\t
                            html = html.replace("&#13;\n\t\t\t\t", "")

                            if"Others who have read our chapters and offered similar assistance have" in html:
                                print("ce")

                            # 有且只有一个a标签，则改变替换文本，以保留跳转功能
                            if (re.match( r'^(?:<a(?:\s[^>]*?)?>[^<]*?</a>)*$', html) is not None):
                                # 针对跳转标签的保留，使用正则表达式搜索<a>标签内的文本
                                a_tag_pattern = re.compile(r'<a[^>]*>(.*?)</a>')
                                matches = a_tag_pattern.findall(html)

                                if len(matches) == 1:
                                    html = matches[0]


                            # 如果原文与译文不为空，则替换原hrml文件中的文本
                            if (original and replacement):
                                # 替换第一个匹配项
                                content_html = content_html.replace(html, replacement, 1)
                                #content_html  = re.sub(original, replacement, content_html, count=1)


                    # 写入内容到HTML文件
                    with open(the_file_path, 'w', encoding='utf-8') as file:
                        file.write(content_html)

            # 构建修改后的EPUB文件路径
            modified_epub_file = file_path.rsplit('.', 1)[0] + '_translated.epub'

            # 创建ZipFile对象，准备写入压缩文件
            with zipfile.ZipFile(modified_epub_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 遍历文件夹中的所有文件和子文件夹
                for root, dirs, files in os.walk(extract_path):
                    for file in files:
                        # 获取文件的完整路径
                        full_file_path = os.path.join(root, file)
                        # 获取文件在压缩文件中的相对路径
                        relative_file_path = os.path.relpath(full_file_path, extract_path)
                        # 将文件添加到压缩文件中
                        zipf.write(full_file_path, relative_file_path)

            # 删除旧文件
            os.remove(file_path)
            # 删除文件夹
            shutil.rmtree(extract_path)


