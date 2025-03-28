import os


class LrcWriter():
    def __init__(self):
        pass

    # 输出lrc文件
    def output_lrc_file(self,cache_data, output_path):

        # 输出文件格式示例
        ex_output ="""
        [ti:1.したっぱ童貞構成員へハニートラップ【手コキ】 (Transcribed on 15-May-2023 19-10-13)]
        [00:00.00]お疲れ様です大長 ただいま機会いたしました
        [00:06.78]法案特殊情報部隊一番対処得フィルレイやセルドツナイカーです 今回例の犯罪組織への潜入が成功しましたのでご報告させていただきます
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
                if 'subtitle_title' in item:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text'],
                            "subtitle_time": item['subtitle_time'],
                            'subtitle_title': item['subtitle_title']}
                else:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text'],
                            "subtitle_time": item['subtitle_time']}
                text_dict[file_path].append(text)

            # 否则，创建一个新的列表
            else:
                if 'subtitle_title' in item:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text'],
                            "subtitle_time": item['subtitle_time'],
                            'subtitle_title': item['subtitle_title']}
                else:
                    text = {'translation_status': item['translation_status'],
                            'source_text': item['source_text'],
                            'translated_text': item['translated_text'],
                            "subtitle_time": item['subtitle_time']}
                text_dict[file_path] = [text]

        # 遍历 path_dict，并将内容写入文件
        for file_path, content_list in text_dict.items():

            # 提取文件路径的文件夹路径和文件名
            folder_path, old_filename = os.path.split(file_path)


            # 创建已翻译文本的新文件路径
            if old_filename.endswith(".lrc"):
                file_name_translated = old_filename.replace(".lrc", "") + "_translated.lrc"
            else:
                file_name_translated = old_filename + "_translated.lrc"
            file_path_translated = os.path.join(folder_path, file_name_translated)


            # 存储已经翻译的文本
            output_file = ""
            # 转换中间字典的格式为最终输出格式
            for content in content_list:
                # 获取字幕时间轴
                subtitle_time = content['subtitle_time']
                # 获取字幕文本内容
                subtitle_text = content['translated_text']

                if 'subtitle_title' in content:
                    subtitle_title = content['subtitle_title']
                    output_file += f'[{subtitle_title}]\n[{subtitle_time}]{subtitle_text}\n'
                else:
                    output_file += f'[{subtitle_time}]{subtitle_text}\n'



            # 输出已经翻译的文件
            with open(file_path_translated, 'w', encoding='utf-8') as file:
                file.write(output_file)

