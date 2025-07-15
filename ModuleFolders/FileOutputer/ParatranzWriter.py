import json
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class ParatranzWriter(BaseTranslatedWriter):
    """
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

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        output_list = []
        for item in cache_file.items:

            line = {
                "key": item.get_extra("key", ""),  # 假设每个 item 都有 key 字段
                "original": item.source_text,
                "translation": item.final_text or "",
                "context": item.get_extra("context", "")  # 如果你有 context 字段，也包括它
            }
            # 根据翻译状态，选择存储到已翻译或未翻译的列表
            if item.translation_status == TranslationStatus.TRANSLATED or item.translation_status == TranslationStatus.POLISHED:
                output_list.append(line)
        json_content = json.dumps(output_list, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")
        # 未保留未翻译输出

    @classmethod
    def get_project_type(self):
        return ProjectType.PARATRANZ
