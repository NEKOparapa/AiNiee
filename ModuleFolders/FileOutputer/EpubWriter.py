import os
import re
import shutil
import zipfile
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

class EpubWriter():
    def __init__(self):
        pass

    def output_epub_file(self, cache_data, output_path, input_path):
        text_dict = {}

        # 分类处理缓存数据
        for item in cache_data:
            if 'storage_path' not in item:
                continue

            storage_path = item['storage_path']
            file_name = item['file_name']
            file_path = f'{output_path}/{storage_path}'

            if file_name != storage_path:
                folder_path = os.path.dirname(file_path)
                os.makedirs(folder_path, exist_ok=True)

            text = {
                'translation_status': item['translation_status'],
                'source_text': item['source_text'],
                'translated_text': item['translated_text'],
                'original_html': item['original_html'],
                "tag_type": item['tag_type'],
                "item_id": item['item_id'],
            }
            text_dict.setdefault(file_path, []).append(text)

        # 创建输出目录并复制原始文件
        os.makedirs(output_path, exist_ok=True)
        EpubWriter._copy_epub_files(self,input_path, output_path)

        # 处理每个EPUB文件
        for file_path, content_list in text_dict.items():
            book = epub.read_epub(file_path)
            parent_path = os.path.dirname(file_path)
            
            # 创建两个解压目录
            extract_paths = {
                'translated': os.path.join(parent_path, 'EpubCacheTranslated'),
                'bilingual': os.path.join(parent_path, 'EpubCacheBilingual')
            }
            
            # 解压到两个目录
            with zipfile.ZipFile(file_path, 'r') as epub_file:
                epub_file.extractall(extract_paths['translated'])
            shutil.copytree(extract_paths['translated'], extract_paths['bilingual'])

            # 处理两个版本
            EpubWriter._process_version(self,book, extract_paths['translated'], 'translated', content_list)
            EpubWriter._process_version(self,book, extract_paths['bilingual'], 'bilingual', content_list)

            # 打包生成两个版本并获取路径
            translated_path = EpubWriter._package_version(self, file_path, extract_paths['translated'], '_translated')
            bilingual_path = EpubWriter._package_version(self, file_path, extract_paths['bilingual'], '_bilingual')

            # 移动双语版本到 bilingual 子目录
            bilingual_output_dir = os.path.join(output_path, 'bilingual_epub')
            relative_path = os.path.relpath(bilingual_path, output_path)
            target_path = os.path.join(bilingual_output_dir, relative_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.move(bilingual_path, target_path)

            # 清理临时文件
            os.remove(file_path)
            shutil.rmtree(extract_paths['translated'])
            shutil.rmtree(extract_paths['bilingual'])

    # 对epub文件进行译文写入
    def _process_version(self, book, extract_path, version, content_list):
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                item_id = item.get_id()
                file_name = os.path.basename(item.get_name())
                the_file_path = EpubWriter._find_file_path(self,extract_path, file_name)
                
                if not the_file_path:
                    continue

                with open(the_file_path, 'r+', encoding='utf-8') as file:
                    content_html = file.read()
                    file.seek(0)
                    
                    for content in content_list:
                        if content['translation_status'] == 1 and content['item_id'] == item_id:
                            original_html = content['original_html']
                            translated_text = content['translated_text']
                            source_text = content['source_text']
                            
                            if version == 'translated':
                                new_html = EpubWriter._rebuild_translated_tag(self,original_html, translated_text)
                            else:
                                new_html = EpubWriter._rebuild_bilingual_tag(self,original_html, translated_text)
                            
                            content_html = content_html.replace(original_html, new_html, 1)
                    
                    file.write(content_html)
                    file.truncate()

    # 处理特定标签结构
    def _handle_specific_tag_structure(self, original_html, translated_text, version):
        """
        处理特定HTML标签结构，返回处理后的HTML或None（未匹配时）
        """
        soup = BeautifulSoup(original_html, 'html.parser')
        li_tag = soup.find('li')
        if li_tag and len(li_tag.contents) == 1 and li_tag.a and len(li_tag.a.contents) == 1:
            a_tag = li_tag.a
            a_tag.string = translated_text
            return str(soup)
        return None

    # 构建译文版本标签
    def _rebuild_translated_tag(self, original_html, translated_text):
        # 优先处理特定标签结构
        handled_html = EpubWriter._handle_specific_tag_structure(self, original_html, translated_text, 'translated')
        if handled_html:
            return handled_html
        
        # 默认BeautifulSoup处理逻辑
        try:
            soup = BeautifulSoup(original_html, 'html.parser')
            original_tag = soup.find()
            if not original_tag:
                return translated_text

            original_text = original_tag.get_text()
            processed_translated = EpubWriter._copy_leading_spaces(self, original_text, translated_text)

            new_tag = soup.new_tag(original_tag.name)
            new_tag.attrs = original_tag.attrs.copy()
            
            if original_tag.is_empty_element:
                return str(new_tag)
                
            new_tag.string = processed_translated
            return str(new_tag)
        except Exception as e:
            print(f"Error rebuilding translated tag: {e}")
            return translated_text

    # 构建双语版本标签
    def _rebuild_bilingual_tag(self, original_html, translated_text):
        # 样式配置常量
        ORIGINAL_STYLE = {
            'opacity': '0.8',
            'color': '#888',
            'font-size': '0.85em',
            'font-style': 'italic',
            'margin-top': '0.5em'
        }
        
        try:
            soup = BeautifulSoup(original_html, 'html.parser')
            original_tag = soup.find()

            # 处理无原生标签的兜底逻辑
            if not original_tag:
                original_text = soup.get_text()
                processed_trans = EpubWriter._copy_leading_spaces(self,original_text, translated_text)
                style_str = '; '.join([f"{k}:{v}" for k,v in ORIGINAL_STYLE.items()])
                return f'''<div class="bilingual-container">
                            <div class="translated-text">{processed_trans}</div>
                            <div class="original-text" style="{style_str}">{original_html}</div>
                        </div>'''

            # 处理有效标签
            original_text = original_tag.get_text()
            processed_trans = EpubWriter._copy_leading_spaces(self,original_text, translated_text)

            # 构建容器标签（保留原始标签类型）
            container_tag = soup.new_tag(original_tag.name)
            container_tag.attrs = {k:v for k,v in original_tag.attrs.items() if k != 'id'}
            container_tag['class'] = container_tag.get('class', []) + ['bilingual-container']

            # 译文部分（主内容）
            trans_tag = soup.new_tag('div', **{'class': 'translated-text'})
            trans_tag.string = processed_trans

            # 原文部分（样式增强）
            original_tag['class'] = original_tag.get('class', []) + ['original-text']
            existing_style = original_tag.get('style', '').rstrip(';')
            new_style = '; '.join([f"{k}:{v}!important" for k,v in ORIGINAL_STYLE.items()])
            original_tag['style'] = f"{existing_style}; {new_style}".strip('; ')
            original_tag.attrs.pop('id', None)

            # 组合结构
            container_tag.append(trans_tag)
            container_tag.append(original_tag)

            return str(container_tag)
        except Exception as e:
            print(f"Bilingual generation error: {e}")
            # 异常情况保持双语结构
            style_str = '; '.join([f"{k}:{v}" for k,v in ORIGINAL_STYLE.items()])
            return f'''<div class="bilingual-container">
                        <div class="translated-text">{translated_text}</div>
                        <div class="original-text" style="{style_str}">{original_html}</div>
                    </div>'''
        

    # 构建文件路径
    def _find_file_path(self, extract_path, target_file):
        for root, _, files in os.walk(extract_path):
            for file in files:
                if file == target_file:
                    return os.path.join(root, file)
        return None

    # 打包epub文件
    def _package_version(self, orig_path, extract_path, suffix):
        new_path = orig_path.rsplit('.', 1)[0] + f'{suffix}.epub'
        with zipfile.ZipFile(new_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(extract_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, extract_path)
                    zipf.write(full_path, rel_path)
        return new_path  # 返回生成的文件路径
    
    # 复制epub文件
    def _copy_epub_files(self, input_path, output_path):
        for dirpath, _, filenames in os.walk(input_path):
            for filename in filenames:
                if filename.endswith('.epub'):
                    src = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(src, input_path)
                    dst = os.path.join(output_path, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

    # 复制前导空格
    def _copy_leading_spaces(self, source_text, target_text):
        """复制源文本的前导空格到目标文本"""
        # 修改正则以同时匹配半角空格和全角空格（\u3000）
        leading_spaces = re.match(r'^[ \u3000]+', source_text)
        leading_spaces = leading_spaces.group(0) if leading_spaces else ''
        return leading_spaces + target_text.lstrip()