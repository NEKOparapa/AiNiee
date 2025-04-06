import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class ParatranzWriter(BaseTranslatedWriter):
    """缓存数据结构示例
        [
            {'project_type': 'Mtool'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！',
                'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json',
                'key': 'txtKey', 'context': ''},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 0, 'source_text': '室内カメラ',
                'translated_text': '无', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json',
                'key': 'txtKey', 'context': ''},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '111111111',
                'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json',
                'file_name': 'Replace the original text.json', 'key': 'txtKey', 'context': ''},
            {'text_index': 4, 'text_classification': 0, 'translation_status': 0, 'source_text': '222222222',
                'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json',
                'file_name': 'Replace the original text.json', 'key': 'txtKey', 'context': ''},
        ]
        中间存储字典格式示例
        ex_path_dict = {
            "D:\\DEBUG Folder\\Replace the original text.json": {'translation_status': 1, 'Source Text': 'しこトラ！',
                                                                    'Translated Text': 'しこトラ！'},
            "D:\\DEBUG Folder\\DEBUG Folder\\Replace the original text.json": {'translation_status': 0,
                                                                                'Source Text': 'しこトラ！',
                                                                                'Translated Text': 'しこトラ！'}
        }
    """
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        output_list = []
        for item in items:

            line = {
                "key": getattr(item, "key", ""),  # 假设每个 item 都有 key 字段
                "original": item.get_source_text(),
                "translation": item.get_translated_text() or "",
                "context": getattr(item, "context", "")  # 如果你有 context 字段，也包括它
            }
            # 根据翻译状态，选择存储到已翻译或未翻译的列表
            if item.get_translation_status() == CacheItem.STATUS.TRANSLATED:
                output_list.append(line)
        json_content = json.dumps(output_list, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")
        # 未保留未翻译输出

    @classmethod
    def get_project_type(self):
        return "Paratranz"
