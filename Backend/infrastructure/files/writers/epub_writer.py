import re
import logging
from html import escape
from itertools import groupby
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup

from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_item import TranslationStatus
from Backend.domain.models.cache_project import ProjectType
from Backend.infrastructure.files.accessors.epub_accessor import EpubAccessor
from Backend.domain.text.epub_markup import (
    protect_fragment, restore_fragment_text, validate_tokens,
)
from Backend.infrastructure.files.writers.base_writer import (
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

    @staticmethod
    def _is_same_primary_language(code_a: str, code_b: str) -> bool:
        """比较 BCP 47 语言代码的主语言子标签是否一致（ja 匹配 ja-JP/ja_JP）。

        参考 RFC 4647 basic filtering: https://www.rfc-editor.org/rfc/rfc4647#section-3.3.1
        """
        if not code_a or not code_b:
            return False
        primary_a = re.split(r"[-_]", code_a.strip(), maxsplit=1)[0].lower()
        primary_b = re.split(r"[-_]", code_b.strip(), maxsplit=1)[0].lower()
        return primary_a == primary_b

    def _write_translation_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        source_file_path: Path, translate_html_tag: Callable[[str, str, dict | None], str]
    ):
        content, opf_info = self.file_accessor.read_content(source_file_path)
        lang_config = self.output_config.language_config
        source_lang_code = lang_config.source_lang_code
        target_lang_code = lang_config.target_lang_code

        translated_item_dict = {
            k: list(v)
            for k, v in groupby(cache_file.items, key=lambda x: x.require_extra("item_id"))
        }
        translation_content = {}
        skipped_legacy = 0
        skipped_invalid = 0
        for item_id, item_filename, html_content in content:
            if item_id not in translated_item_dict:
                translation_content[item_filename] = html_content
                continue
            
            modified_html_content = html_content
            for item in translated_item_dict[item_id]:
                if item.translation_status == TranslationStatus.TRANSLATED or item.translation_status == TranslationStatus.POLISHED:
                    original_html = item.require_extra("original_html")
                    translated_text = item.final_text
                    placeholders = item.extra.get("epub_placeholders")
                    if placeholders is None and protect_fragment(original_html)[1]:
                        # 旧缓存没有注号位置，保留原段落，不能猜测译文中的插入位置。
                        skipped_legacy += 1
                        continue
                    if placeholders is not None and not validate_tokens(
                        "".join(placeholders), translated_text
                    ):
                        skipped_invalid += 1
                        continue
                    new_html = translate_html_tag(original_html, translated_text, placeholders)
                    modified_html_content = modified_html_content.replace(original_html, new_html, 1)

            if target_lang_code and item_filename.endswith(('.xhtml', '.html', '.htm')):
                modified_html_content = self._replace_html_lang_tags(
                    modified_html_content, source_lang_code, target_lang_code
                )

            translation_content[item_filename] = modified_html_content

        if skipped_legacy:
            logging.getLogger(__name__).warning(
                "EPUB：%d 个含链接或锚点的旧缓存段落缺少位置标记，已保留原文。"
                "请重新读取原书并翻译这些段落后导出。", skipped_legacy
            )
        if skipped_invalid:
            logging.getLogger(__name__).warning(
                "EPUB：%d 个段落的结构标记缺失、重复或顺序错误，已保留原文，"
                "请重新翻译这些段落。", skipped_invalid
            )

        # 替换 OPF 文件中的 <dc:language> 元数据
        if target_lang_code and opf_info:
            opf_filename, opf_content = opf_info
            translation_content[opf_filename] = self._replace_opf_language(
                opf_content, source_lang_code, target_lang_code
            )

        self.file_accessor.write_content(
            translation_content, translation_file_path, source_file_path
        )

    @staticmethod
    def _translated_inner_html(original_html, translated_text, placeholders):
        """只恢复缓存中的可信标签；模型返回的普通文字始终转义。"""
        if placeholders is None:
            if protect_fragment(original_html)[1]:
                return None
            return escape(translated_text, quote=False)
        try:
            return restore_fragment_text(translated_text, placeholders)
        except ValueError:
            return None

    # 译文版本
    def _rebuild_translated_tag(self, original_html, translated_text, placeholders=None):
        soup = BeautifulSoup(original_html, 'html.parser')
        original_tag = soup.find()
        if not original_tag:
            return escape(translated_text, quote=False)

        original_text = original_tag.get_text()
        processed_translated = self._copy_leading_spaces(original_text, translated_text)
        inner_html = self._translated_inner_html(original_html, processed_translated, placeholders)
        if inner_html is None:
            return original_html

        new_tag = soup.new_tag(original_tag.name)
        new_tag.attrs = original_tag.attrs.copy()

        if original_tag.is_empty_element:
            return str(new_tag)

        new_tag.extend(list(BeautifulSoup(inner_html, 'html.parser').contents))
        return str(new_tag)

    # 双语版本
    def _rebuild_bilingual_tag(self, original_html, translated_text, placeholders=None):
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
            
            trans_div = f'<div>{escape(processed_trans, quote=False)}</div>'
            orig_div = f'<div style="{style_str}">{original_html}</div>'

            if self.output_config.bilingual_order == BilingualOrder.SOURCE_FIRST:
                return f"{orig_div}\n  {trans_div}"
            else:  # 默认为译文在前
                return f"{trans_div}\n  {orig_div}"

        # 复制前导空格
        original_text = original_tag.get_text()
        processed_trans = self._copy_leading_spaces(original_text, translated_text)
        inner_html = self._translated_inner_html(original_html, processed_trans, placeholders)
        if inner_html is None:
            return original_html

        # 1. 创建全新的译文标签
        trans_tag = soup.new_tag(original_tag.name, attrs=original_tag.attrs.copy())
        trans_tag.extend(list(BeautifulSoup(inner_html, 'html.parser').contents))

        # 2. 创建一个全新的、带样式的原文标签，而不是在原始标签上就地修改。
        #    这是为了避免 BeautifulSoup 的副作用导致原始标签内容丢失。
        styled_attrs = original_tag.attrs.copy()
        styled_attrs.pop('id', None) # 移除id以避免冲突
        styled_attrs.pop('xml:id', None)
        if original_tag.name == 'a':
            styled_attrs.pop('name', None)

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

        # 链接统一指向译文的原始锚点；原文副本不能再持有相同的 id/name。
        for child in orig_styled_tag.find_all(True):
            child.attrs.pop('id', None)
            child.attrs.pop('xml:id', None)
            if child.name == 'a':
                child.attrs.pop('name', None)
        
        # 4. 组合并返回两个新创建标签的字符串形式
        trans_html = str(trans_tag)
        orig_html_styled = str(orig_styled_tag)
        
        if self.output_config.bilingual_order == BilingualOrder.SOURCE_FIRST:
            return f"{orig_html_styled}\n  {trans_html}"
        else:  # 默认为译文在前
            return f"{trans_html}\n  {orig_html_styled}"


    def _replace_html_lang_tags(
        self, xhtml_content: str, source_lang_code: str | None, target_lang_code: str
    ) -> str:
        """替换 <html> 根元素上与源语言一致的 lang / xml:lang 属性为目标语言代码；
        源语言未知（auto）时直接替换。正文内局部 lang 标记不处理。"""
        def replace_lang_attr(match):
            current_code = match.group(2)
            if source_lang_code and not self._is_same_primary_language(current_code, source_lang_code):
                return match.group(0)
            return f'{match.group(1)}"{target_lang_code}"'

        def replace_in_html_tag(match):
            html_tag = match.group(0)
            html_tag = re.sub(r'(xml:lang\s*=\s*)["\']([^"\']*)["\']', replace_lang_attr, html_tag)
            html_tag = re.sub(r'(?<!xml:)(lang\s*=\s*)["\']([^"\']*)["\']', replace_lang_attr, html_tag)
            return html_tag
        return re.sub(r'<html\b[^>]*>', replace_in_html_tag, xhtml_content, count=1)

    def _replace_opf_language(
        self, opf_content: str, source_lang_code: str | None, target_lang_code: str
    ) -> str:
        """替换 OPF 中与源语言一致的 <dc:language> 为目标语言代码，其余语言声明保留；
        源语言未知（auto）时只替换第一个（EPUB 约定第一个为主语言）。"""
        replaced = False

        def replace_language_element(match):
            nonlocal replaced
            current_code = match.group(2).strip()
            if source_lang_code:
                if not self._is_same_primary_language(current_code, source_lang_code):
                    return match.group(0)
            elif replaced:
                return match.group(0)
            replaced = True
            return f"{match.group(1)}{target_lang_code}{match.group(3)}"

        return re.sub(
            r'(<dc:language[^>]*>)([^<]*)(</dc:language>)',
            replace_language_element,
            opf_content,
        )

    def _copy_leading_spaces(self, source_text, target_text):
        leading_spaces = re.match(r'^[ \u3000]+', source_text)
        leading_spaces = leading_spaces.group(0) if leading_spaces else ''
        return leading_spaces + target_text.lstrip()

    @classmethod
    def get_project_type(self):
        return ProjectType.EPUB
