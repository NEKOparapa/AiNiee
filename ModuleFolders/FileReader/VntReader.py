import json
import os

class VntReader():
    def __init__(self):
        pass

    def read_vnt_files(self, folder_path):
        json_data_list = [{"project_type": "Vnt"}]
        i = 1

        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        json_data = json.load(json_file)
                        for entry in json_data:
                            source_text = entry["message"]
                            storage_path = os.path.relpath(file_path, folder_path)
                            file_name = file

                            name = entry.get("name")
                            entry_data = {
                                "text_index": i,
                                "translation_status": 0,
                                "source_text": source_text,
                                "translated_text": source_text,
                                "model": "none",
                                "storage_path": storage_path,
                                "file_name": file_name,
                            }

                            if name:
                                # 直接拼接【人名】+文本
                                entry_data["source_text"] = VntReader.combine_srt(self,name, source_text)
                                entry_data["name"] = name
                            
                            json_data_list.append(entry_data)
                            i += 1

        return json_data_list

    def combine_srt(self, name, text):
        return f"【{name}】{text}"