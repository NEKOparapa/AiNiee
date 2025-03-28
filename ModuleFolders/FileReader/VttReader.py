import os
import re

class VttReader:
    def __init__(self):
        self.timecode_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})"
        )

    def read_vtt_files(self, folder_path):
        json_data_list = [{"project_type": "Vtt"}]
        text_index = 1
        
        self.timecode_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})"
        )

        for root, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".vtt"):
                    continue

                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                header, body = VttReader._split_header_body(self,content)
                blocks = VttReader._parse_blocks(self,body)

                for block in blocks:
                    entry = VttReader._parse_block(self,block, text_index, file_path, folder_path, header)
                    if entry:
                        json_data_list.append(entry)
                        text_index += 1

        return json_data_list

    def _split_header_body(self, content):
        parts = content.split('\n\n', 1)
        return parts[0], parts[1] if len(parts) > 1 else ''

    def _parse_blocks(self, body):
        return [b.strip() for b in re.split(r'\n{2,}', body) if b.strip()]

    def _parse_block(self, block, text_index, file_path, base_path, header):

        self.timecode_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})"
        )

        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            return None

        # 解析时间轴
        time_match = self.timecode_pattern.search(lines[0])
        if not time_match:
            return None

        full_timecode = lines[0]
        text_lines = []
        current_line = 1

        # 处理可能的序号
        if lines[0].isdigit() and len(lines) > 1:
            if self.timecode_pattern.search(lines[1]):
                full_timecode = lines[1]
                current_line += 1

        # 收集文本内容
        while current_line < len(lines):
            line = lines[current_line]
            if self.timecode_pattern.search(line):  # 防止异常时间轴
                break
            text_lines.append(line)
            current_line += 1

        source_text = '\n'.join(text_lines).strip()
        if not source_text:
            return None

        return {
            "text_index": text_index,
            "translation_status": 0,
            "source_text": source_text,
            "translated_text": source_text,
            "model": "none",
            "subtitle_time": full_timecode,
            "top_text": header,
            "storage_path": os.path.relpath(file_path, base_path),
            "file_name": os.path.basename(file_path),
        }