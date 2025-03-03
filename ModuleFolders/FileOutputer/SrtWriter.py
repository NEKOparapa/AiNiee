import os

class SrtWriter:
    def __init__(self):
        pass

    def output_srt_file(self, cache_data, output_path):
        translated_dict = {}  # 存储译文版本内容 {文件路径: 条目列表}
        bilingual_dict = {}   # 存储双语版本内容 {文件路径: 条目列表}

        for item in cache_data:
            if "storage_path" not in item:
                continue

            file_path = os.path.join(output_path, item["storage_path"])
            folder_path = os.path.dirname(file_path)
            os.makedirs(folder_path, exist_ok=True)

            # 构建翻译版和双语版的文件路径
            base, ext = os.path.splitext(file_path)
            translated_path = f"{base}.translated{ext}"
            bilingual_path = f"{base}.bilingual{ext}"

            # 处理译文版本
            translated_entry = {
                "number": item["subtitle_number"],
                "time": item["subtitle_time"],
                "text": item.get("translated_text", "").strip()
            }
            if translated_path not in translated_dict:
                translated_dict[translated_path] = []
            translated_dict[translated_path].append(translated_entry)

            # 处理双语版本（需要原文和译文）
            original_text = item.get("source_text", "").strip()
            translated_text = item.get("translated_text", "").strip()
            if original_text or translated_text:
                bilingual_entry = {
                    "time": item["subtitle_time"],
                    "original": original_text,
                    "translated": translated_text
                }
                if bilingual_path not in bilingual_dict:
                    bilingual_dict[bilingual_path] = []
                bilingual_dict[bilingual_path].append(bilingual_entry)

        # 写入译文版本文件
        for file_path, contents in translated_dict.items():
            output = []
            for content in contents:
                # 跳过空文本（可选）
                if not content["text"]:
                    continue
                block = [
                    str(content["number"]),
                    content["time"],
                    content["text"],
                    ""
                ]
                output.append("\n".join(block).strip())
            if output:  # 确保有内容才写入
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(output))

        # 写入双语版本文件
        for file_path, contents in bilingual_dict.items():
            output = []
            entry_number = 1  # 条目编号从1开始递增
            for entry in contents:
                # 添加原文条目（如果有内容）
                if entry["original"]:
                    original_block = [
                        str(entry_number),
                        entry["time"],
                        entry["original"],
                        ""
                    ]
                    output.append("\n".join(original_block).strip())
                    entry_number += 1
                # 添加译文条目（如果有内容）
                if entry["translated"]:
                    translated_block = [
                        str(entry_number),
                        entry["time"],
                        entry["translated"],
                        ""
                    ]
                    output.append("\n".join(translated_block).strip())
                    entry_number += 1
            if output:  # 确保有内容才写入
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(output))