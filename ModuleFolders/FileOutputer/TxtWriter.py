import json
import os


class TxtWriter():
    def __init__(self):
        pass

    # 输出txt文件
    def output_txt_file(self,cache_data, output_path):

        # 输出文件格式示例
        ex_output ="""
        　测试1
        　今ではダンジョンは、人々の営みの一部としてそれなりに定着していた。

        ***

        「正気なの？」
        测试2
        """

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
                        "sentence_indent": item['sentence_indent'],
                        'line_break': item['line_break']}
                text_dict[file_path].append(text)

            # 否则，创建一个新的列表
            else:
                text = {'translation_status': item['translation_status'],
                        'source_text': item['source_text'],
                        'translated_text': item['translated_text'],
                        "sentence_indent": item['sentence_indent'],
                        'line_break': item['line_break']}
                text_dict[file_path] = [text]

        # 遍历 path_dict，并将内容写入文件
        for file_path, content_list in text_dict.items():

            # 提取文件路径的文件夹路径和文件名
            folder_path, old_filename = os.path.split(file_path)


            # 创建已翻译文本的新文件路径
            if old_filename.endswith(".txt"):
                file_name_translated = old_filename.replace(".txt", "") + "_translated.txt"
            else:
                file_name_translated = old_filename + "_translated.txt"
            file_path_translated = os.path.join(folder_path, file_name_translated)


            # 存储已经翻译的文本
            output_file = ""

            # 转换中间字典的格式为最终输出格式
            for content in content_list:
                # 获取记录的句首空格数
                expected_indent_count = content['sentence_indent']
                # 获取句尾换行符数
                line_break_count = content['line_break']

                # 删除句首的所有空格
                translated_text = content['translated_text'].lstrip()

                # 根据记录的空格数在句首补充空格
                sentence_indent = "　" * expected_indent_count

                line_break = "\n" * (line_break_count + 1)

                output_file += f'{sentence_indent}{translated_text}{line_break}'

            # 输出已经翻译的文件
            with open(file_path_translated, 'w', encoding='utf-8') as file:
                file.write(output_file)
