import re
from itertools import groupby
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileAccessor.EpubAccessor import EpubAccessor
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class EpubWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)
        self.file_accessor = EpubAccessor()

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file,
            source_file_path, self._rebuild_bilingual_tag
        )

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file,
            source_file_path, self._rebuild_translated_tag
        )

    def _write_translation_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        source_file_path: Path, translate_html_tag: Callable[[str, str], str]
    ):
        content = self.file_accessor.read_content(source_file_path)

        # groupby需要key有序，item_id本身有序，不需要重排
        translated_item_dict = {
            k: list(v)
            for k, v in groupby(cache_file.items, key=lambda x: x.require_extra("item_id"))
        }
        translation_content = {}
        for item_id, item_filename, html_content in content:
            if item_id not in translated_item_dict:
                translation_content[item_filename] = html_content
                continue
            
            # 创建一个副本进行操作，避免在迭代中修改
            modified_html_content = html_content
            for item in translated_item_dict[item_id]:
                if item.translation_status == TranslationStatus.TRANSLATED:
                    original_html = item.require_extra("original_html")
                    translated_text = item.final_text
                    new_html = translate_html_tag(original_html, translated_text)
                    # 在副本上执行替换
                    modified_html_content = modified_html_content.replace(original_html, new_html, 1)
            translation_content[item_filename] = modified_html_content
        self.file_accessor.write_content(
            translation_content, translation_file_path, source_file_path
        )


    # 构建译文版本标签
    def _rebuild_translated_tag(self, original_html, translated_text):

        soup = BeautifulSoup(original_html, 'html.parser')
        original_tag = soup.find()
        if not original_tag:
            return translated_text

        original_text = original_tag.get_text()
        processed_translated = self._copy_leading_spaces(original_text, translated_text)

        new_tag = soup.new_tag(original_tag.name)
        new_tag.attrs = original_tag.attrs.copy()

        if original_tag.is_empty_element:
            return str(new_tag)

        new_tag.string = processed_translated
        return str(new_tag)


    # 构建双语版本标签
    def _rebuild_bilingual_tag(self, original_html, translated_text):
        # 样式配置常量
        ORIGINAL_STYLE = {
            'opacity': '0.8',
            'color': '#888',
            'font-size': '0.85em',
            'font-style': 'italic',
            'margin-top': '0.2em',  # 增加一点上边距，视觉上分隔两行
        }

        soup = BeautifulSoup(original_html, 'html.parser')
        original_tag = soup.find()

        # 如果原始HTML中没有标签（纯文本），则使用div进行包裹作为回退方案
        if not original_tag:
            original_text_content = soup.get_text()
            processed_trans = self._copy_leading_spaces(original_text_content, translated_text)
            style_str = '; '.join([f"{k}:{v}" for k, v in ORIGINAL_STYLE.items()])
            
            # 返回两个并列的div标签
            return f'<div>{processed_trans}</div>\n  <div style="{style_str}">{original_html}</div>'

        # 复制前导空格
        original_text = original_tag.get_text()
        processed_trans = self._copy_leading_spaces(original_text, translated_text)

        # 创建译文标签
        # 使用原始标签名和属性
        trans_tag = soup.new_tag(original_tag.name, attrs=original_tag.attrs.copy())
        trans_tag.string = processed_trans

        # 修改原文标签 
        # 在解析出的原始标签上直接修改
        # 移除id以避免HTML文档中id重复
        original_tag.attrs.pop('id', None)
        
        # 合并样式
        existing_style = original_tag.get('style', '')
        # 确保现有样式末尾有分号（如果存在）
        if existing_style and not existing_style.strip().endswith(';'):
            existing_style += '; '
        
        new_style = '; '.join([f"{k}:{v}" for k, v in ORIGINAL_STYLE.items()])
        original_tag['style'] = existing_style + new_style
        
        # 组合并返回两个标签的字符串形式
        return str(trans_tag) + "\n  " +  str(original_tag)

    # 复制前导空格
    def _copy_leading_spaces(self, source_text, target_text):
        """复制源文本的前导空格到目标文本"""
        # 修改正则以同时匹配半角空格和全角空格（\u3000）
        leading_spaces = re.match(r'^[ \u3000]+', source_text)
        leading_spaces = leading_spaces.group(0) if leading_spaces else ''
        return leading_spaces + target_text.lstrip()

    @classmethod
    def get_project_type(self):
        return ProjectType.EPUB
