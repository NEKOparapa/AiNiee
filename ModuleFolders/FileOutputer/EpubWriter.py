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
    PreWriteMetadata,
    BilingualOrder,
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

        translated_item_dict = {
            k: list(v)
            for k, v in groupby(cache_file.items, key=lambda x: x.require_extra("item_id"))
        }
        translation_content = {}
        for item_id, item_filename, html_content in content:
            if item_id not in translated_item_dict:
                translation_content[item_filename] = html_content
                continue
            
            modified_html_content = html_content
            for item in translated_item_dict[item_id]:
                if item.translation_status == TranslationStatus.TRANSLATED or item.translation_status == TranslationStatus.POLISHED:
                    original_html = item.require_extra("original_html")
                    translated_text = item.final_text
                    new_html = translate_html_tag(original_html, translated_text)
                    modified_html_content = modified_html_content.replace(original_html, new_html, 1)
            translation_content[item_filename] = modified_html_content
        self.file_accessor.write_content(
            translation_content, translation_file_path, source_file_path
        )

    # 译文版本
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

    # 双语版本
    def _rebuild_bilingual_tag(self, original_html, translated_text):
        ORIGINAL_STYLE = {
            'opacity': '0.8',
            'color': '#888',
            'font-size': '0.85em',
            'font-style': 'italic',
            'margin-top': '0.2em',
        }

        soup = BeautifulSoup(original_html, 'html.parser')
        original_tag = soup.find()

        # 如果原始HTML中没有标签（纯文本），则使用div进行包裹作为回退方案
        if not original_tag:
            original_text_content = soup.get_text()
            processed_trans = self._copy_leading_spaces(original_text_content, translated_text)
            style_str = '; '.join([f"{k}:{v}" for k, v in ORIGINAL_STYLE.items()])
            
            trans_div = f'<div>{processed_trans}</div>'
            orig_div = f'<div style="{style_str}">{original_html}</div>'

            if self.output_config.bilingual_order == BilingualOrder.SOURCE_FIRSTT:
                return f"{orig_div}\n  {trans_div}"
            else:  # 默认为译文在前
                return f"{trans_div}\n  {orig_div}"

        # 复制前导空格
        original_text = original_tag.get_text()
        processed_trans = self._copy_leading_spaces(original_text, translated_text)

        # 1. 创建全新的译文标签
        trans_tag = soup.new_tag(original_tag.name, attrs=original_tag.attrs.copy())
        trans_tag.string = processed_trans

        # 2. 创建一个全新的、带样式的原文标签，而不是在原始标签上就地修改。
        #    这是为了避免 BeautifulSoup 的副作用导致原始标签内容丢失。
        styled_attrs = original_tag.attrs.copy()
        styled_attrs.pop('id', None) # 移除id以避免冲突

        # 合并样式
        existing_style = styled_attrs.get('style', '')
        if existing_style and not existing_style.strip().endswith(';'):
            existing_style += '; '
        new_style = '; '.join([f"{k}:{v}" for k, v in ORIGINAL_STYLE.items()])
        styled_attrs['style'] = existing_style + new_style
        
        orig_styled_tag = soup.new_tag(original_tag.name, attrs=styled_attrs)
        
        # 3. 将原始标签的完整内容（包括文本和所有子标签）复制到新的带样式标签中。
        if original_tag.contents:
            orig_styled_tag.extend(list(original_tag.contents))
        
        # 4. 组合并返回两个新创建标签的字符串形式
        trans_html = str(trans_tag)
        orig_html_styled = str(orig_styled_tag)
        
        if self.output_config.bilingual_order == BilingualOrder.SOURCE_FIRST:
            return f"{orig_html_styled}\n  {trans_html}"
        else:  # 默认为译文在前
            return f"{trans_html}\n  {orig_html_styled}"


    def _copy_leading_spaces(self, source_text, target_text):
        leading_spaces = re.match(r'^[ \u3000]+', source_text)
        leading_spaces = leading_spaces.group(0) if leading_spaces else ''
        return leading_spaces + target_text.lstrip()

    @classmethod
    def get_project_type(self):
        return ProjectType.EPUB