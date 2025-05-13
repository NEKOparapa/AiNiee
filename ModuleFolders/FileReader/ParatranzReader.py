import json
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class ParatranzReader(BaseSourceReader):
    """读取文件夹中树形结构Paratranz json 文件
        待处理的json接口例
        [
            {
                "key": "Activate",
                "original": "カードをプレイ",
                "translation": "出牌",
                "context": null,
                "stage": 1
            }
        ]
        缓存数据结构示例
        [
            {'project_type': 'Paratranz'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！',
                'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json', 'key': 'txtKey',
                'context': ''},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ',
                'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json', 'key': 'txtKey',
                'context': ''},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ',
                'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json',
                'file_name': 'Replace the original text.json', 'key': 'txtKey', 'context': ''},
        ]
    """
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.PARATRANZ

    @property
    def support_file(self):
        return "json"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:

        json_list = json.loads(file_path.read_text(encoding=pre_read_metadata.encoding))

        items = []
        # 提取键值对
        for json_item in json_list:
            # 根据 JSON 文件内容的数据结构，获取相应字段值
            stage = json_item.get('stage', 0)
            if stage == 0:  # stage 0为未翻译，详见https://paratranz.cn/docs
                translation_status = TranslationStatus.UNTRANSLATED
            else:
                translation_status = TranslationStatus.TRANSLATED
            source_text = json_item.get('original', '')  # 获取原文，如果没有则默认为空字符串
            translated_text = json_item.get('translation', '')  # 获取翻译，如果没有则默认为空字符串
            extra = {
                "key": json_item.get('key', ''),  # 获取键值，如果没有则默认为空字符串
                "context": json_item.get('context', ''),  # 获取上下文信息，如果没有则默认为空字符串
            }
            item = CacheItem(
                source_text=source_text, translated_text=translated_text,
                translation_status=translation_status,  # 更新翻译状态
                extra=extra
            )
            items.append(item)
        return CacheFile(items=items)

    def can_read_by_content(self, file_path: Path) -> bool:
        # 即使不是对应编码也不影响英文的key
        content = json.loads(file_path.read_text(encoding='utf-8', errors='ignore'))
        if not isinstance(content, list):
            return False
        return all(isinstance(line, dict) and "original" in line for line in content)
