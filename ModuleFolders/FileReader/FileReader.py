           
import datetime
import json
import os
import random


from ModuleFolders.FileReader.MToolReader import MToolReader
from ModuleFolders.FileReader.ParatranzReader import ParatranzReader
from ModuleFolders.FileReader.TPPReader import TPPReader
from ModuleFolders.FileReader.VntReader import VntReader
from ModuleFolders.FileReader.SrtReader import SrtReader
from ModuleFolders.FileReader.VttReader import VttReader
from ModuleFolders.FileReader.LrcReader import LrcReader
from ModuleFolders.FileReader.TxtReader import TxtReader
from ModuleFolders.FileReader.EpubReader import EpubReader
from ModuleFolders.FileReader.DocxReader import DocxReader
from ModuleFolders.FileReader.MdReader import MdReader
from ModuleFolders.FileReader.RenpyReader import RenpyReader

# 文件读取器
class FileReader():
    def __init__(self):
        pass
    
    # 根据文件类型读取文件
    def read_files (self,translation_project,label_input_path):

        if translation_project == "Mtool":
            cache_list = MToolReader.read_mtool_files(self,folder_path = label_input_path)
        elif translation_project == "Tpp":
            cache_list = TPPReader.read_tpp_files (self,folder_path = label_input_path)
        elif translation_project == "Vnt":
            cache_list = VntReader.read_vnt_files(self,folder_path = label_input_path)
        elif translation_project == "Srt":
            cache_list = SrtReader.read_srt_files(self,folder_path = label_input_path)
        elif translation_project == "Vtt":
            cache_list = VttReader.read_vtt_files(self,folder_path = label_input_path)
        elif translation_project == "Lrc":
            cache_list = LrcReader.read_lrc_files(self,folder_path = label_input_path)
        elif translation_project == "Txt":
            cache_list = TxtReader.read_txt_files(self,folder_path = label_input_path)
        elif translation_project == "Epub":
            cache_list = EpubReader.read_epub_files(self,folder_path = label_input_path)
        elif translation_project == "Docx":
            cache_list = DocxReader.read_docx_files(self,folder_path = label_input_path)
        elif translation_project == "Md":
            cache_list = MdReader.read_md_files(self,folder_path = label_input_path)
        elif translation_project == "Renpy":
            cache_list = RenpyReader.read_renpy_files(self,folder_path = label_input_path)
        elif translation_project == "Paratranz":
            cache_list = ParatranzReader.read_paratranz_files(self,folder_path = label_input_path)
        elif translation_project == "Ainiee_cache":
            cache_list = FileReader.read_cache_files(self,folder_path = label_input_path)
        return cache_list


    # 生成项目ID
    def generate_project_id(self,prefix):
        # 获取当前时间，并将其格式化为数字字符串
        current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # 生成5位随机数
        random_number = random.randint(10000, 99999)

        # 组合生成项目ID
        project_id = f"{current_time}{prefix}{random_number}"
        
        return project_id


    #读取缓存文件
    def read_cache_files(self,folder_path):
        # 获取文件夹中的所有文件
        files = os.listdir(folder_path)

        # 查找以 "CacheData" 开头且以 ".json" 结尾的文件
        json_files = [file for file in files if file.startswith("AinieeCacheData") and file.endswith(".json")]

        if not json_files:
            print(f"Error: No 'CacheData' JSON files found in folder '{folder_path}'.")
            return None

        # 选择第一个符合条件的 JSON 文件
        json_file_path = os.path.join(folder_path, json_files[0])

        # 读取 JSON 文件内容
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            return data
