import json
from pathlib import Path
import re

import rich

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class TransReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.TRANS

    @property
    def support_file(self):
        return "trans"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:

        # 以json格式读取工程文件
        trans_content = json.loads(file_path.read_text(encoding="utf-8"))

        # 获取具体文本路径
        files_data = trans_content["project"]["files"]
        items = []
        
        # 遍历每个文件类别（例如："data/Actors.json"）
        for file_category, category_data in files_data.items():

            data_list = category_data.get("data", [])
            tags_list = category_data.get("tags", [])  # 如果缺失，默认为空列表
            context_list = category_data.get("context", [])  # 如果缺失，默认为空列表
            parameters_list = category_data.get("parameters", [])  # 如果缺失，默认为空列表

            # 遍历每对文本 [原文，翻译]
            for idx, text_pair in enumerate(data_list):

                # 类型检查
                if not isinstance(text_pair, (list, tuple)):
                    rich.print(
                        f"[[red]WARNING[/]] 在文件 '{file_path}' 的类别 '{file_category}' 索引 {idx} 处发现非列表/元组项：{text_pair}，已跳过。")
                    continue  # 跳过这个无效项

                if len(text_pair) == 0:
                    rich.print(
                        f"[[red]WARNING[/]] 在文件 '{file_path}' 的类别 '{file_category}' 索引 {idx} 处发现空项：{text_pair}，已跳过。")
                    continue  # 跳过这个空项

                # 初始翻译状态
                translation_status = TranslationStatus.UNTRANSLATED



                # 检查翻译状态，过滤已翻译内容
                translated_text = ""
                if len(text_pair) >= 2: # 获取译文内容，并且防止列表越界，有些trans文件没有译文位置
                    translated_text = text_pair[1]

                    if translated_text:
                        translation_status = TranslationStatus.TRANSLATED


                # 获取原文内容
                source_text = text_pair[0]

                # 获取该原文的对应标签
                tags = None
                if idx < len(tags_list):
                    tags = tags_list[idx]  # 可能为 null 或类似 "red" 的列表

                # 获取文本的地址来源
                contexts = None
                if idx < len(context_list):
                    contexts = context_list[idx]  # 可能为null或者是列表

                # 获取该原文的对应人名
                parameters = None
                rowInfoText = None
                if idx < len(parameters_list):
                    parameters = parameters_list[idx]
                    if parameters and len(parameters) > 0 and isinstance(parameters[0], dict):  # 有些人名信息并没有以字典存储
                        rowInfoText = parameters[0].get("rowInfoText", "")  # 可能为 具体人名 或类似 "\\v[263]" 的字符串

                # 过滤不需要翻译的文本，放在这里进行处理是因为contexts太大了，后面解决性能消耗后，转移到其他地方
                if isinstance(source_text, str) and self.filter_trans_text( source_text, tags, contexts) :
                    translation_status = TranslationStatus.EXCLUDED  # 改变为不需要翻译

                    # 添加处理过的标签注释
                    if tags is None:
                        tags = ["indigo"]
                    else:
                        tags.append("indigo")

                # 额外属性
                extra = {
                    "tags": tags,
                    "file_category": file_category,
                    "data_index": idx,
                }
                # 基本属性
                item = CacheItem(
                    source_text=source_text,
                    translated_text=translated_text,
                    translation_status=translation_status,
                    extra=extra
                )

                # 如果有人名，则对原文本进行二次处理
                if rowInfoText:
                    item.source_text = self.combine_srt(rowInfoText, source_text)
                    item.set_extra("name", rowInfoText)

                # 添加进缓存条目
                items.append(item)

        return CacheFile(items=items)

    # 人名信息添加
    def combine_srt(self, name, text):
        return f"[{name}]{text}"


    # 特殊文本过滤器-trans项目
    def filter_trans_text(self, source_text: str, tags, contexts):

        # 保留绿色安全标签
        if tags and ("green" in tags):
            return False

        # 保留常见插件文本
        if self.isTagText(source_text):
            return False


        # 过滤全部蓝色标签
        if tags and ("blue" in tags):
            return True

        # 过滤特定文本以外的红色标签
        if tags and ("red" in tags):
            # 如果是插件文本，而非命令文本
            if self.check_list_conditions(contexts=contexts, middle_list = ["StringLiteral"]) :
                # 如果检查出纯日志文本
                if self.check_english_letters_after_tags(source_text):
                    pass
    
                else:
                    return True
            else:
                return True

        # 过滤全部note文本
        if self.check_list_conditions(contexts=contexts, end_str="note"):
            # 如果检查出纯日志文本
            if self.check_english_letters_after_tags(source_text):
                pass
            else:
                return True

        # 过滤Animations文件
        if self.check_list_conditions(contexts=contexts, start_str="Animations") :
            return True

        # 过滤MapInfos文件
        if self.check_list_conditions(contexts=contexts, start_str="MapInfos") :
            return True
        
        # 过滤Tilesets文件
        if self.check_list_conditions(contexts=contexts, start_str="Tilesets") :
            return True

        # 过滤CommonEvents 调用事件名
        if self.check_list_conditions(contexts=contexts, start_str="CommonEvents", end_str="name") :
            return True

        # 过滤Troops 调用事件名
        if self.check_list_conditions(contexts=contexts, start_str="Troops", end_str="name") :
            return True

        # 过滤Actors的profile字段
        if self.check_list_conditions(contexts=contexts, start_str="Actors", end_str="profile") :
            return True

        # 过滤所有事件名
        if self.check_list_conditions(contexts=contexts, end_str="name", middle_list = ["events"]) :
            return True

        # 过滤图片调用代码
        if source_text.strip().startswith("<PLM"):
            return True

        return False

    # 识别出部分战斗日志文本
    def check_english_letters_after_tags(self,text: str) -> bool:
        r"""
        提取文本中所有RPG Maker代码标签后，检查剩余文本是否还有英文字母。

        RPG Maker 代码标签格式: \ + 任意字母 + [ + 任意内容 + ]
        例如: \C[27], \N[HeroName], \V[10=5]
        """
        # 1. 定义代码标签的正则表达式
        tag_pattern = r"\\([a-zA-Z]+)\[.*?\]" 

        # 2. 移除所有匹配到的代码标签
        text_without_tags = re.sub(tag_pattern, "", text)
        text_cleaned = re.sub(r'\s+', '', text_without_tags)  # 移除所有空白字符
        # 比如文本为\C[7]\I[2456]，提取完标签文本后为空
        if not text_cleaned:
            return False

        # 3. 检查剩余文本中是否包含任何英文字母,比如b_0001或者单个字母，但会误伤3p这样的文本
        if re.search(r"[a-zA-Z]", text_cleaned):
            return False
        else:
            return True

    # 识别插件文本
    def isTagText(self, text: str):
        # 检查是否信息提示插件
        if text.startswith("<infowindow") and text.endswith(">"):
            return True
        # 检查是否是地图名字显示插件
        if text.startswith("<namePop:") and text.endswith(">"):
            return True
        return False
    
    # 检查字段路径内容
    def check_list_conditions(self, contexts: list[str],start_str: str = None,end_str: str = None,middle_list: list[str] = None) -> bool:

        # 检查空列表
        if not contexts:
            return False

        # 1. 检查 str_a (开头字符串)
        if start_str is not None:
            # 检查 list_a 中的每个元素
            for item_in_a in contexts:
                if not item_in_a.startswith(start_str):
                    return False  

        # 2. 检查 str_b (结尾字符串)
        if end_str is not None:
            for item_in_a in contexts:
                if not item_in_a.endswith(end_str):
                    return False

        # 3. 检查 list_b (包含所有子字符串)
        if middle_list is not None and middle_list: 
            for item_in_a in contexts:
                # 对于 list_a 中的每一个元素，检查它是否包含 list_b 中的所有子字符串
                for sub_item_in_b in middle_list:
                    if sub_item_in_b not in item_in_a:
                        return False # item_in_a 没有包含 list_b 中的某个元素

        # 如果所有检查都通过了
        return True