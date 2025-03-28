import os

class SrtReader:
    def __init__(self):
        pass

    def read_srt_files(self, folder_path):
        json_data_list = [{"project_type": "Srt"}]
        text_index = 1  # 全局文本索引

        for root, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".srt"):
                    continue

                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = [line.rstrip("\n").lstrip("\ufeff") for line in f]

                current_block = None
                storage_path = os.path.relpath(file_path, folder_path)

                for line in lines:
                    line = line.strip()

                    # 新字幕块开始
                    if current_block is None:
                        if line.isdigit():
                            current_block = {
                                "number": line,
                                "time": None,
                                "text": []
                            }
                        continue

                    # 处理时间轴
                    if current_block["time"] is None:
                        if "-->" in line:
                            current_block["time"] = line
                        else:
                            # 时间轴格式错误，丢弃当前块
                            current_block = None
                        continue

                    # 处理文本内容
                    if not line:
                        # 遇到空行，保存当前块
                        json_data_list.append({
                            "text_index": text_index,
                            "translation_status": 0,
                            "source_text": "\n".join(current_block["text"]),
                            "translated_text": "\n".join(current_block["text"]),
                            "model": "none",
                            "subtitle_number": current_block["number"],
                            "subtitle_time": current_block["time"],
                            "storage_path": storage_path,
                            "file_name": file,
                        })
                        text_index += 1
                        current_block = None
                    else:
                        current_block["text"].append(line)

                # 处理文件末尾未以空行结束的情况
                if current_block is not None:
                    json_data_list.append({
                        "text_index": text_index,
                        "translation_status": 0,
                        "source_text": "\n".join(current_block["text"]),
                        "translated_text": "\n".join(current_block["text"]),
                        "model": "none",
                        "subtitle_number": current_block["number"],
                        "subtitle_time": current_block["time"],
                        "storage_path": storage_path,
                        "file_name": file,
                    })
                    text_index += 1

        return json_data_list