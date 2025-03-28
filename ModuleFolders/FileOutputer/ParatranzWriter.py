import json
import os


class ParatranzWriter():
    def __init__(self):
        pass


    # 输出paratranz文件
    def output_paratranz_file(self, cache_data, output_path):
        # 缓存数据结构示例
        ex_cache_data = [
            {'project_type': 'Mtool'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！',
             'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json',
             'key': 'txtKey', 'context': ''},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ',
             'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json',
             'key': 'txtKey', 'context': ''},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '111111111',
             'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json',
             'file_name': 'Replace the original text.json', 'key': 'txtKey', 'context': ''},
            {'text_index': 4, 'text_classification': 0, 'translation_status': 0, 'source_text': '222222222',
             'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json',
             'file_name': 'Replace the original text.json', 'key': 'txtKey', 'context': ''},
        ]

        # 中间存储字典格式示例
        ex_path_dict = {
            "D:\\DEBUG Folder\\Replace the original text.json": {'translation_status': 1, 'Source Text': 'しこトラ！',
                                                                 'Translated Text': 'しこトラ！'},
            "D:\\DEBUG Folder\\DEBUG Folder\\Replace the original text.json": {'translation_status': 0,
                                                                               'Source Text': 'しこトラ！',
                                                                               'Translated Text': 'しこトラ！'}
        }

        # 输出文件格式示例
        ex_output = [
        {
            "key": "Activate",
            "original": "カードをプレイ",
            "translation": "出牌",
            "context": ""
        }]

        # 创建中间存储字典，这个存储已经翻译的内容
        path_dict = {}

        # 遍历缓存数据
        for item in cache_data:
            # 忽略不包含 'storage_path' 的项
            if 'storage_path' not in item:
                continue

            # 获取相对文件路径
            storage_path = item['storage_path']
            # 获取文件名
            file_name = item['file_name']

            if file_name != storage_path:
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
            if file_path in path_dict:
                text = {'translation_status': item['translation_status'], 'source_text': item['source_text'],
                        'translated_text': item['translated_text'], 'context': item['context'], 'key': item['key']}
                path_dict[file_path].append(text)

            # 否则，创建一个新的列表
            else:
                text = {'translation_status': item['translation_status'], 'source_text': item['source_text'],
                        'translated_text': item['translated_text'], 'context': item['context'], 'key': item['key']}
                path_dict[file_path] = [text]

        # 遍历 path_dict，并将内容写入文件
        for file_path, content_list in path_dict.items():

            # 提取文件路径的文件夹路径和文件名
            folder_path, old_filename = os.path.split(file_path)

            # 创建已翻译文本的新文件路径
            if old_filename.endswith(".json"):
                file_name_translated = old_filename.replace(".json", "") + "_translated.json"
            else:
                file_name_translated = old_filename + "_translated.json"
            file_path_translated = os.path.join(folder_path, file_name_translated)

            # 创建未翻译文本的新文件路径
            if old_filename.endswith(".json"):
                file_name_untranslated = old_filename.replace(".json", "") + "_untranslated.json"
            else:
                file_name_untranslated = old_filename + "_untranslated.json"
            file_path_untranslated = os.path.join(folder_path, file_name_untranslated)

            # 存储已经翻译的文本
            output_file = []

            # 存储未翻译的文本
            output_file2 = []

            # 转换中间字典的格式为最终输出格式
            for content in content_list:
                item = {
                    "key": content.get("key", ""),  # 假设每个 content 字典都有 'key' 字段
                    "original": content['source_text'],
                    "translation": content.get('translated_text', ""),
                    "context": content.get('context', "")  # 如果你有 'context' 字段，也包括它
                }
                # 根据翻译状态，选择存储到已翻译或未翻译的列表
                if content['translation_status'] == 1:
                    output_file.append(item)
                elif content['translation_status'] == 0 or content['translation_status'] == 2:
                    output_file2.append(item)

            # 输出已经翻译的文件
            with open(file_path_translated, 'w', encoding='utf-8') as file:
                json.dump(output_file, file, ensure_ascii=False, indent=4)

            # 输出未翻译的内容
            if output_file2:
                with open(file_path_untranslated, 'w', encoding='utf-8') as file:
                    json.dump(output_file2, file, ensure_ascii=False, indent=4)
