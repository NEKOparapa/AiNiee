import os
import copy
import json



from ModuleFolders.FileOutputer.MToolWriter import MToolWriter
from ModuleFolders.FileOutputer.ParatranzWriter import ParatranzWriter
from ModuleFolders.FileOutputer.TPPWriter import TPPWriter
from ModuleFolders.FileOutputer.VntWriter import VntWriter
from ModuleFolders.FileOutputer.SrtWriter import SrtWriter
from ModuleFolders.FileOutputer.VttWriter import VttWriter
from ModuleFolders.FileOutputer.LrcWriter import LrcWriter
from ModuleFolders.FileOutputer.TxtWriter import TxtWriter
from ModuleFolders.FileOutputer.EpubWriter import EpubWriter
from ModuleFolders.FileOutputer.DocxWriter import DocxWriter
from ModuleFolders.FileOutputer.MdWriter import MdWriter
from ModuleFolders.FileOutputer.RenpyWriter import RenpyWriter




# 文件输出器
class FileOutputer():

    def __init__(self):
        pass


    # 输出缓存文件
    def output_cache_file(self,cache_data,output_path):
        # 复制缓存数据到新变量
        try:
            modified_cache_data = copy.deepcopy(cache_data)
        except:
            print("[INFO]: 无法正常进行深层复制,改为浅复制")
            modified_cache_data = cache_data.copy()

        # 修改新变量的元素中的'translation_status'
        for item in modified_cache_data:
            if 'translation_status' in item and item['translation_status'] == 2:
                item['translation_status'] = 0

        # 输出为JSON文件
        with open(os.path.join(output_path, "AinieeCacheData.json"), "w", encoding="utf-8") as f:
            json.dump(modified_cache_data, f, ensure_ascii=False, indent=4)



    # 输出已经翻译文件
    def output_translated_content(self, cache_data, output_path, input_path) -> None:
        if cache_data[0]["project_type"] == "Mtool":
            MToolWriter.output_mtool_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Srt":
            SrtWriter.output_srt_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Vtt":
            VttWriter.output_vtt_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Lrc":
            LrcWriter.output_lrc_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Vnt":
            VntWriter.output_vnt_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Txt":
            TxtWriter.output_txt_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Md":
            MdWriter.output_md_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "Epub":
            EpubWriter.output_epub_file(self, cache_data, output_path, input_path)
        elif cache_data[0]["project_type"] == "Docx":
            DocxWriter.output_docx_file(self, cache_data, output_path, input_path)
        elif cache_data[0]["project_type"] == "Renpy":
            RenpyWriter.output_renpy_file(self, cache_data, output_path, input_path)
        elif cache_data[0]["project_type"] == "Paratranz":
            ParatranzWriter.output_paratranz_file(self, cache_data, output_path)
        elif cache_data[0]["project_type"] == "T++":
            TPPWriter.output_tpp_file(self, cache_data, output_path)