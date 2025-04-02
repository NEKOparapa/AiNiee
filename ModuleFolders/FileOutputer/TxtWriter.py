import os

class TxtWriter():
    def __init__(self):
        pass

    def output_txt_file(self, cache_data, output_path):
        text_dict = {}

        # 遍历缓存数据
        for item in cache_data:
            # 忽略不包含 'storage_path' 的项
            if 'storage_path' not in item:
                continue

            # 获取相对文件路径
            storage_path = item['storage_path']
            file_name = item['file_name']

            # 构建文件路径
            if file_name != storage_path:
                file_path = os.path.join(output_path, storage_path)
                folder_path = os.path.dirname(file_path)
                os.makedirs(folder_path, exist_ok=True)
            else:
                file_path = os.path.join(output_path, storage_path)

            # 构建存储结构
            text = {
                'translation_status': item['translation_status'],
                'source_text': item['source_text'],
                'translated_text': item['translated_text'],
                'sentence_indent': item['sentence_indent'],  # 修正键名
                'line_break': item['line_break']
            }
            text_dict.setdefault(file_path, []).append(text)

        # 遍历所有文件路径
        for file_path, content_list in text_dict.items():
            # ================= 生成译文版 =================
            # 构建译文版路径
            folder_path, old_filename = os.path.split(file_path)
            translated_filename = f"{os.path.splitext(old_filename)[0]}_translated.txt"
            translated_path = os.path.join(folder_path, translated_filename)

            # ================= 生成双语版 =================
            # 构建双语版路径
            bilingual_base = os.path.join(output_path, "bilingual_txt")
            relative_path = os.path.relpath(file_path, output_path)
            bilingual_fullpath = os.path.join(bilingual_base, relative_path)
            bilingual_folder, bilingual_filename = os.path.split(bilingual_fullpath)
            bilingual_filename = f"{os.path.splitext(bilingual_filename)[0]}_bilingual.txt"
            bilingual_path = os.path.join(bilingual_folder, bilingual_filename)
            os.makedirs(bilingual_folder, exist_ok=True)

            # 生成内容
            translated_content = []
            bilingual_content = []
            
            for content in content_list:
                indent = "　" * content['sentence_indent']
                line_break = "\n" * (content['line_break'] + 1)
                
                # 处理译文内容
                clean_translated = content['translated_text'].lstrip()
                translated_line = f"{indent}{clean_translated}"
                translated_content.append(f"{translated_line}{line_break}")
                
                # 处理双语内容
                clean_source = content['source_text'].lstrip()
                source_line = f"{indent}{clean_source}"
                translated_line = f"{indent}{clean_translated}"
                bilingual_block = f"{source_line}\n{translated_line}\n{line_break}"
                bilingual_content.append(bilingual_block)

            # 写入译文版
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write("".join(translated_content))
                
            # 写入双语版
            with open(bilingual_path, "w", encoding="utf-8") as f:
                f.write("".join(bilingual_content))