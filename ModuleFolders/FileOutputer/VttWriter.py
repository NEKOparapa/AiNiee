import os


class VttWriter:
    def __init__(self):
        pass

    def output_vtt_file(self, cache_data, output_path):
        from collections import defaultdict
        file_dict = defaultdict(list)

        # 收集数据
        for item in cache_data:
            if 'storage_path' not in item:
                continue
            
            path = os.path.join(output_path, item['storage_path'])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # 构建完整块结构
            block = []
            if item.get('subtitle_number'):
                block.append(str(item['subtitle_number']))
            block.append(item['subtitle_time'])
            block.append(item['translated_text'])
            
            file_dict[path].append('\n'.join(block))

        # 写入文件
        for path, blocks in file_dict.items():
            translated_path = path.replace('.vtt', '_translated.vtt')
            
            with open(translated_path, 'w', encoding='utf-8') as f:
                # 写入头信息
                f.write(cache_data[1]['top_text'] + '\n\n')
                
                # 写入字幕块
                f.write('\n\n\n'.join(blocks))