import json
import os


class VntWriter():
    def __init__(self):
        pass

    # 输出vnt文件
    def output_vnt_file(self,cache_data, output_path):

        # 输出文件格式示例
        ex_output =  [
            {
                "name": "玲",
                "message": "「……おはよう」"
            },
            {
                "message": "　心の内では、ムシャクシャした気持ちは未だに鎮まっていなかった。"
            }
            ]

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
            if file_path in path_dict:
                if'name' in item:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text'],
                            'name': item['name']}

                else:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text']}

                path_dict[file_path].append(text)

            # 否则，创建一个新的列表
            else:
                if'name' in item:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text'],
                            'name': item['name']}

                else:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text']}

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

            #存储未翻译的文本
            output_file2 = []

            # 转换中间字典的格式为最终输出格式
            for content in content_list:
                # 如果这个本已经翻译了，存放对应的文件中
                if'name' in content:

                    # 提取原来人名与文本
                    name =  content['name']
                    translated_text = content['translated_text']
                    
                    # 分割人名与文本
                    name,translated_text = VntWriter.extract_strings(self, name, translated_text)

                    # 构建字段
                    text = {'name': name,
                            'message': translated_text}
                else:
                    text = {'message': content['translated_text']}

                output_file.append(text)

                # 如果这个文本没有翻译或者正在翻译
                if content['translation_status'] == 0 or content['translation_status'] == 2:
                    if'name' in content:

                        # 提取原来人名与文本
                        name =  content['name']
                        translated_text = content['translated_text']
                        
                        # 分割人名与文本
                        name,translated_text = VntWriter.extract_strings(self, name, translated_text)

                        # 构建字段
                        text = {'name': name,
                                'message': translated_text}
                    else:
                        text = {'message': content['translated_text']}

                    output_file2.append(text)


            # 输出已经翻译的文件
            with open(file_path_translated, 'w', encoding='utf-8') as file:
                json.dump(output_file, file, ensure_ascii=False, indent=4)

            # 输出未翻译的内容
            if output_file2:
                with open(file_path_untranslated, 'w', encoding='utf-8') as file:
                    json.dump(output_file2, file, ensure_ascii=False, indent=4)


    # 辅助函数，提取人名与文本
    def extract_strings(self, name,dialogue):
        parts = dialogue.partition("「")  # 使用 partition 分割字符串，保留分隔符

        if parts[1]:  # parts[1] 是分隔符，如果存在，则说明找到了 "「"
            extracted_name = parts[0].strip()  # 分隔符前的部分为人名
            extracted_text = (parts[1] + parts[2]).strip()  # 分隔符 + 分隔符后的部分为对话文本

            if extracted_text.startswith("「（"):
                extracted_text = extracted_text[1:] # 从索引 1 开始切片，移除第一个字符 "「"

        else:
            extracted_name = name  # 没有 "「"，使用默认人名
            extracted_text = dialogue.strip()  # 整个对话文本作为内容

        return extracted_name, extracted_text
        