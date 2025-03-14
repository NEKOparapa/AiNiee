import os
import re
import json

from openpyxl import Workbook
from openpyxl.utils.escape import escape

class TPPWriter():
    def __init__(self):
        pass

    # 输出表格文件
    def output_tpp_file(self, cache_data, output_path):
        # 缓存数据结构示例
        # ex_cache_data = [
        #     {"project_type": "T++"},
        #     {"text_index": 1,  "translation_status": 1, "source_text": "しこトラ！", "translated_text": "无", "storage_path": "TrsData.xlsx", "file_name": "TrsData.xlsx", "row_index": 2},
        #     {"text_index": 2, "translation_status": 0, "source_text": "室内カメラ", "translated_text": "无", "storage_path": "TrsData.xlsx", "file_name": "TrsData.xlsx", "row_index": 3},
        #     {"text_index": 3,  "translation_status": 0, "source_text": "草草草草", "translated_text": "11111", "storage_path": "DEBUG Folder\\text.xlsx", "file_name": "text.xlsx", "row_index": 3},
        #     {"text_index": 4,  "translation_status": 1, "source_text": "室内カメラ", "translated_text": "22222", "storage_path": "DEBUG Folder\\text.xlsx", "file_name": "text.xlsx", "row_index": 4},
        # ]

        # 创建一个字典，用于存储翻译数据
        translations_by_path = {}
        # 收集未翻译条目
        untranslated_entries = []

        # 遍历缓存数据
        for item in cache_data:
            if "storage_path" in item:
                path = item["storage_path"]

                # 如果路径不存在，创建文件夹
                folder_path = os.path.join(output_path, os.path.dirname(path))
                os.makedirs(folder_path, exist_ok=True)

                # 提取信息
                source_text = item.get("source_text", "")
                translated_text = item.get("translated_text", "")
                row_index = item.get("row_index", -1)
                translation_status = item.get("translation_status", -1)

                # 收集未翻译条目
                if translation_status == 0:
                    entry = {
                        "file_path": path,
                        "file_name": item.get("file_name", ""),
                        "row_number": row_index,
                        "source_text": source_text
                    }
                    untranslated_entries.append(entry)

                # 构造字典
                translation_dict = {
                    "translation_status": translation_status,
                    "source_text": source_text,
                    "translated_text": translated_text,
                    "row_index": row_index
                }

                # 将字典添加到对应路径的列表中
                if path in translations_by_path:
                    translations_by_path[path].append(translation_dict)
                else:
                    translations_by_path[path] = [translation_dict]

        # 遍历字典，将数据写入 Excel 文件
        for path, translations_list in translations_by_path.items():
            file_path = os.path.join(output_path, path)

            # 创建一个工作簿
            wb = Workbook()

            # 选择默认的活动工作表
            ws = wb.active

            # 添加表头
            ws.append(
                [
                    "Original Text",
                    "Initial",
                    "Machine translation",
                    "Better translation",
                    "Best translation",
                ]
            )

            # 将数据写入工作表
            for item in translations_list:
                source_text = item.get("source_text", "")
                translated_text = item.get("translated_text", "")
                row_index = item.get("row_index", -1)
                translation_status = item.get("translation_status", -1)

                # 根据翻译状态写入原文及译文
                # 如果文本是以 = 开始，则加一个空格
                # 因为 = 开头会被识别成 Excel 公式导致 T++ 导入时 卡住
                # 加入空格后，虽然还是不能直接导入 T++ ，但是可以手动复制粘贴
                if translation_status != 1:
                    ws.cell(row=row_index, column=1).value = re.sub(r"^=", " =", source_text)
                else:
                    ws.cell(row=row_index, column=1).value = re.sub(r"^=", " =", source_text)

                    # 防止含有特殊字符而不符合Excel公式时，导致的写入译文错误
                    try:
                        ws.cell(row=row_index, column=2).value = re.sub(r"^=", " =", translated_text)
                    except:
                        # 过滤非法控制字符并转义XML特殊字符
                        filtered_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', translated_text)
                        escaped_string = escape(filtered_text)
                        ws.cell(row=row_index, column=2).value = escaped_string

            # 保存工作簿
            wb.save(file_path)

        # 写入未翻译JSON文件
        if untranslated_entries:
            json_path = os.path.join(output_path, "未能成功翻译文本.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(untranslated_entries, f, ensure_ascii=False, indent=2)

