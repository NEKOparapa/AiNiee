
import os
import openpyxl  #需安装库pip install openpyxl

class TPPReader():
    def __init__(self):
        pass


    #读取文件夹中树形结构的xlsx文件， 存到列表变量中
    def read_tpp_files(self,folder_path):
        # 缓存数据结构示例
        ex_cache_data = [
        {'project_type': 'T++'},
        {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！', 'translated_text': '无', 'storage_path': 'TrsData.xlsx', 'file_name': 'TrsData.xlsx', "row_index": 1},
        {'text_index': 2, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ', 'translated_text': '无', 'storage_path': 'TrsData.xlsx', 'file_name': 'TrsData.xlsx', "row_index": 2},
        {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ', 'translated_text': '无', 'storage_path': 'DEBUG Folder\\text.xlsx', 'file_name': 'text.xlsx', "row_index": 3},
        ]

        # 创建列表
        cache_list = []
        # 添加文件头
        cache_list.append({
            "project_type": "T++",
        })
        #文本索引初始值
        i = 1

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".xlsx"):
                    file_path = os.path.join(root, file) #构建文件路径

                    wb = openpyxl.load_workbook(file_path)
                    sheet = wb.active
                    for row in range(2, sheet.max_row + 1): # 从第二行开始读取，因为第一行是标识头，通常不用理会
                        cell_value1 = sheet.cell(row=row, column=1).value # 第N行第一列的值
                        cell_value2 = sheet.cell(row=row, column=2).value # 第N行第二列的值

                        source_text = cell_value1  # 获取原文
                        storage_path = os.path.relpath(file_path, folder_path) # 用文件的绝对路径和输入文件夹路径“相减”，获取相对的文件路径
                        file_name = file #获取文件名

                        #第1列的值不为空，和第2列的值为空，是未翻译内容
                        if cell_value1 and cell_value2 is  None:
                            
                            translated_text = "无"
                            cache_list.append({
                                "text_index": i,
                                "translation_status": 0,
                                "source_text": source_text,
                                "translated_text": translated_text,
                                "model": "none",
                                "storage_path": storage_path,
                                "file_name": file_name,
                                "row_index": row ,
                            })

                            i = i + 1 # 增加文本索引值

                        # 第1列的值不为空，和第2列的值不为空，是已经翻译内容
                        elif cell_value1 and cell_value2 :

                            translated_text = cell_value2
                            cache_list.append({
                                "text_index": i,
                                "translation_status": 1,
                                "source_text": source_text,
                                "translated_text": translated_text,
                                "storage_path": storage_path,
                                "model": "none",
                                "file_name": file_name,
                                "row_index": row ,
                            })

                            i = i + 1 # 增加文本索引值



        return cache_list