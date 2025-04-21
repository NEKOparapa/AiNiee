import json
from pathlib import Path
from typing import Any, Dict, List

# 假定这些导入相对于项目结构是正确的
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
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
        return "I18next" # 与 Reader 保持一致

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

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None # source_file_path 在此实现中未使用
    ):
        """
        将 CacheItem 列表写入 i18next JSON 文件。
        """
        output_data = {} # 用于构建最终 JSON 结构的字典

        for item in items:
            path: List[str] = item.i18next_path

            # 获取翻译后的文本
            translated_text = item.get_translated_text() # 假设这个方法返回最终要写入的字符串

            # 使用辅助函数将翻译文本按路径设置到 output_data 中
            self._set_value_by_path(output_data, path, translated_text)


        json_content = json.dumps(output_data, ensure_ascii=False, indent=4)

        # 确保目录存在
        translation_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 以 UTF-8 编码写入文件
        translation_file_path.write_text(json_content, encoding="utf-8")
