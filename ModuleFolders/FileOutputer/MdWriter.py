import os


class MdWriter:
    def __init__(self):
        pass

    def output_md_file(self, cache_data, output_path):
        """根据缓存数据输出翻译后的Markdown文件"""
        from collections import defaultdict
        file_dict = defaultdict(list)

        # 组织文件内容
        for item in cache_data:
            if 'storage_path' not in item:
                continue

            file_path = os.path.join(output_path, item['storage_path'])
            MdWriter._ensure_dir_exists(self,file_path)
            
            file_dict[file_path].append({
                'translated': item['translated_text'].lstrip(),
                'indent': '　' * item['sentence_indent'],
                'line_break': '\n' * (item['line_break'] + 1)
            })

        # 写入文件
        for orig_path, contents in file_dict.items():
            translated_path = MdWriter._get_translated_path(self,orig_path)
            with open(translated_path, 'w', encoding='utf-8') as f:
                f.write(''.join(
                    f"{content['indent']}{content['translated']}{content['line_break']}"
                    for content in contents
                ))

    def _ensure_dir_exists(self, file_path):
        """确保文件目录存在"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    def _get_translated_path(self, original_path):
        """生成翻译文件路径"""
        directory, filename = os.path.split(original_path)
        name, ext = os.path.splitext(filename)
        return os.path.join(directory, f"{name}_translated{ext}")