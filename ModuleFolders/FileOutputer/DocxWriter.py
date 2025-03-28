import os
import shutil
import zipfile

from bs4 import BeautifulSoup

class DocxWriter():
    def __init__(self):
        pass

    # 输出docx文件
    def output_docx_file(self,cache_data, output_path, input_path):

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

            # 创建文件夹路径及文件路径
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
                        'translated_text': item['translated_text']}
                text_dict[file_path].append(text)

            # 否则，创建一个新的列表
            else:
                text = {'translation_status': item['translation_status'],
                        'source_text': item['source_text'],
                        'translated_text': item['translated_text']}
                text_dict[file_path] = [text]


        # 创建输出文件夹
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # 将输入路径里面的所有docx文件复制到输出路径
        for dirpath, dirnames, filenames in os.walk(input_path):
            for filename in filenames:
                # 检查文件扩展名是否为.epub
                if filename.endswith('.docx'):
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



        # 遍历 path_dict，并将内容写入对应文件中
        for file_path, content_list in text_dict.items():

            # 构建解压文件夹路径
            parent_path = os.path.dirname(file_path)
            extract_path = os.path.join(parent_path, 'DocxCache')

            # 创建解压文件夹
            if not os.path.exists(extract_path):
                os.makedirs(extract_path)

            # 使用zipfile模块打开并解压docx文件
            with zipfile.ZipFile(file_path, 'r') as epub_file:
                # 提取所有文件
                epub_file.extractall(extract_path)

            # 构建存储文本的文件路径
            the_file_path = os.path.join(extract_path,'word', 'document.xml')

            # 打开对应xml文件
            with open(the_file_path, 'r', encoding='utf-8') as file:
                # 读取文件内容
                xml_soup = BeautifulSoup(file, 'xml')

            start_index = 0
            # 根据 w:t 标签找到原文
            paragraphs = xml_soup.findAll('w:t')
            for match in paragraphs:
                if match.string.strip():
                    # 在翻译结果中查找是否存在原文，存在则替换并右移开始下标
                    for content_index in range(start_index, len(content_list)):
                        if match.string == content_list[content_index]['source_text']:
                            match.string = content_list[content_index]['translated_text']
                            start_index = content_index + 1
                            break

            # 写入内容到xml文件
            with open(the_file_path, 'w', encoding='utf-8') as file:
                file.write(str(xml_soup))

            # 构建修改后的docx文件路径
            modified_epub_file = file_path.rsplit('.', 1)[0] + '_translated.docx'

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
