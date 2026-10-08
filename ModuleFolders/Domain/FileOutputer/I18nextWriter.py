import json
from pathlib import Path
from typing import Any, Dict, List

# 假定这些导入相对于项目结构是正确的
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class I18nextWriter(BaseTranslatedWriter):
    """
    将包含翻译信息的 CacheItem 列表写回 i18next 格式的 JSON 文件。
    利用 CacheItem 中的 'i18next_path' 属性来重建原始的嵌套结构。
    """
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.I18NEXT  # 与 Reader 保持一致

    def _set_value_by_path(self, data_dict: Dict, path: List[str], value: Any):
        """
        根据路径列表在嵌套字典中设置值。如果路径不存在，则创建它。
        """
        current_level = data_dict
        # 遍历到倒数第二个键
        for i, key in enumerate(path[:-1]):
            if key not in current_level:
                current_level[key] = {} # 创建新字典层级
            elif not isinstance(current_level[key], dict):
                 # 路径冲突：期望是字典，但遇到其他类型
                 # 可以选择：覆盖、报错、或跳过
                 current_level[key] = {} # 强制覆盖为字典以继续
            current_level = current_level[key]

        # 设置最后一个键的值
        last_key = path[-1]
        current_level[last_key] = value

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        """
        将 CacheItem 列表写入 i18next JSON 文件。

        以源文件为模板：只把已翻译条目写回原路径，保留源JSON中的
        数字/布尔/null/数组/空对象等非字符串叶子（旧实现从零重建，会全部删掉）。
        源文件缺失时回退为从缓存重建（untranslated键用final_text=原文补齐，避免丢键）。
        """
        output_data = {}
        template_loaded = False
        if source_file_path and Path(source_file_path).exists():
            try:
                output_data = json.loads(Path(source_file_path).read_text(encoding="utf-8-sig"))
                template_loaded = isinstance(output_data, dict)
            except Exception as e:
                print(f"Error reading source i18next file {source_file_path}: {e}")
                template_loaded = False

        if not template_loaded:
            # 回退：用全部条目重建（含untranslated的原文），避免输出丢键
            for item in cache_file.items:
                path: List[str] = item.require_extra("i18next_path")
                self._set_value_by_path(output_data, path, item.final_text)
        else:
            for item in cache_file.items:
                path = item.require_extra("i18next_path")
                # 只写回已翻译条目；untranslated键保持模板原值
                if item.translation_status not in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED):
                    continue
                translated_text = item.final_text
                if not translated_text:
                    continue
                self._set_value_by_path(output_data, path, translated_text)

        json_content = json.dumps(output_data, ensure_ascii=False, indent=4)

        # 确保目录存在
        translation_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 以 UTF-8 编码写入文件
        translation_file_path.write_text(json_content, encoding="utf-8")
