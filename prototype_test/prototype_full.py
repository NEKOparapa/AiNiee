"""
AiNiee Word翻译改进 - 完整原型（含回写）

功能：
1. 段落级/单元格级提取 ✅
2. 格式标记转换（文本 → 标记符号）
3. 模拟翻译（添加标记）
4. 格式恢复（标记符号 → XML格式）
5. 回写到原文档
"""

import zipfile
import re
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString
from typing import List, Dict, Tuple
import json
import copy

class FormatMarker:
    """格式标记工具"""
    
    @staticmethod
    def add_markers(text: str, formats: List[Dict]) -> str:
        """
        在文本中添加格式标记
        例: "EC50" + format@76-78:subscript -> "EC_{50}"
        """
        if not formats:
            return text
        
        # 按位置倒序排序，从后往前插入，避免位置偏移
        sorted_formats = sorted(formats, key=lambda f: f['start'], reverse=True)
        
        result = text
        for fmt in sorted_formats:
            start = fmt['start']
            end = fmt['end']
            fmt_type = fmt['type']
            
            # 提取格式化的文本
            formatted_text = text[start:end]
            
            # 添加标记
            if fmt_type == 'subscript':
                marker = f"_{{{formatted_text}}}"
            elif fmt_type == 'superscript':
                marker = f"^{{{formatted_text}}}"
            elif fmt_type == 'italic':
                marker = f"*{{{formatted_text}}}*"
            else:
                marker = formatted_text
            
            # 替换
            result = result[:start] + marker + result[end:]
        
        return result
    
    @staticmethod
    def parse_markers(text: str) -> Tuple[str, List[Dict]]:
        """
        从翻译后的文本中解析格式标记
        例: "EC_{50}" -> "EC50" + format@2-4:subscript
        """
        formats = []
        clean_text = text
        
        # 正则匹配格式标记
        patterns = [
            (r'_\{([^}]+)\}', 'subscript'),
            (r'\^\{([^}]+)\}', 'superscript'),
            (r'\*\{([^}]+)\}\*', 'italic'),
        ]
        
        offset = 0
        for pattern, fmt_type in patterns:
            for match in re.finditer(pattern, text):
                content = match.group(1)
                marker_start = match.start() - offset
                marker_end = marker_start + len(content)
                
                formats.append({
                    'start': marker_start,
                    'end': marker_end,
                    'type': fmt_type,
                    'text': content
                })
                
                # 更新偏移量
                marker_length = len(match.group(0))
                offset += marker_length - len(content)
        
        # 移除标记符号
        for pattern, _ in patterns:
            clean_text = re.sub(pattern, r'\1', clean_text)
        
        # 按位置排序
        formats.sort(key=lambda f: f['start'])
        
        return clean_text, formats

class TranslationUnit:
    """翻译单元"""
    def __init__(self, source_text: str, unit_type: str, location: str, 
                 xml_element: Tag = None, formats: List[Dict] = None):
        self.source_text = source_text
        self.unit_type = unit_type
        self.location = location
        self.xml_element = xml_element  # 保存原始XML元素引用
        self.formats = formats or []
        self.marked_text = ""  # 带标记的文本
        self.translated_text = ""  # 翻译后的文本（带标记）
        self.final_text = ""  # 最终文本（去掉标记）
        self.final_formats = []  # 最终格式列表

class DocxPrototypeTranslator:
    def __init__(self, docx_path: Path):
        self.docx_path = docx_path
        self.xml_soup = None
        self.units: List[TranslationUnit] = []
    
    def load(self):
        """加载DOCX文档"""
        with zipfile.ZipFile(self.docx_path, 'r') as zipf:
            content = zipf.read("word/document.xml").decode("utf-8")
        self.xml_soup = BeautifulSoup(content, 'xml')
        print(f"✅ 加载文档: {self.docx_path.name}")
    
    def extract_text_with_format(self, parent_element: Tag) -> Tuple[str, List[Dict]]:
        """从父元素中提取文本和格式信息"""
        full_text = ""
        formats = []
        
        runs = parent_element.find_all('w:r')
        
        for run in runs:
            text_elem = run.find('w:t')
            if not text_elem or not text_elem.string:
                continue
            
            text_content = text_elem.get_text()
            start_pos = len(full_text)
            full_text += text_content
            
            # 检查格式
            rpr = run.find('w:rPr')
            if rpr:
                # 上标/下标
                vert = rpr.find('w:vertAlign')
                if vert:
                    val = vert.get('w:val')
                    if val in ['subscript', 'superscript']:
                        formats.append({
                            'start': start_pos,
                            'end': start_pos + len(text_content),
                            'type': val,
                            'text': text_content
                        })
                
                # 斜体
                if rpr.find('w:i'):
                    formats.append({
                        'start': start_pos,
                        'end': start_pos + len(text_content),
                        'type': 'italic',
                        'text': text_content
                    })
        
        return full_text, formats
    
    def extract_all_units(self):
        """提取所有翻译单元"""
        print("\n📤 提取翻译单元...")
        
        # 提取段落
        for para_idx, para in enumerate(self.xml_soup.find_all('w:p')):
            if para.find_parent('w:tc'):
                continue
            
            text, formats = self.extract_text_with_format(para)
            if not text.strip():
                continue
            
            unit = TranslationUnit(
                source_text=text,
                unit_type='paragraph',
                location=f"para_{para_idx}",
                xml_element=para,
                formats=formats
            )
            self.units.append(unit)
        
        # 提取表格单元格
        for table_idx, table in enumerate(self.xml_soup.find_all('w:tbl')):
            for row_idx, row in enumerate(table.find_all('w:tr')):
                for cell_idx, cell in enumerate(row.find_all('w:tc')):
                    text, formats = self.extract_text_with_format(cell)
                    if not text.strip():
                        continue
                    
                    unit = TranslationUnit(
                        source_text=text,
                        unit_type='table_cell',
                        location=f"table_{table_idx}_row_{row_idx}_cell_{cell_idx}",
                        xml_element=cell,
                        formats=formats
                    )
                    self.units.append(unit)
        
        print(f"✅ 提取完成: {len(self.units)} 个翻译单元")
    
    def add_format_markers(self):
        """为所有单元添加格式标记"""
        print("\n🏷️  添加格式标记...")
        marked_count = 0
        
        for unit in self.units:
            unit.marked_text = FormatMarker.add_markers(unit.source_text, unit.formats)
            if unit.formats:
                marked_count += 1
        
        print(f"✅ 已为 {marked_count} 个单元添加格式标记")
    
    def simulate_translation(self):
        """模拟翻译（简单替换，保留格式标记）"""
        print("\n🔄 模拟翻译...")
        
        # 简单的中英词典
        trans_dict = {
            '临床研究方案': 'Clinical Study Protocol',
            '评价': 'Evaluation of',
            '片': 'Tablets',
            '在健康成人': 'in Healthy Adults',
            '安全性': 'Safety',
            '耐受性': 'Tolerability',
            '药代动力学': 'Pharmacokinetics',
            '药效学': 'Pharmacodynamics',
            '方案编号': 'Protocol Number',
            '版本号': 'Version',
            '版本日期': 'Version Date',
        }
        
        for unit in self.units:
            # 使用标记后的文本进行"翻译"
            translated = unit.marked_text
            
            # 简单替换
            for cn, en in trans_dict.items():
                translated = translated.replace(cn, en)
            
            unit.translated_text = translated
        
        print(f"✅ 翻译完成: {len(self.units)} 个单元")
    
    def parse_translation_markers(self):
        """解析翻译后的格式标记"""
        print("\n🔍 解析翻译后的格式标记...")
        
        for unit in self.units:
            unit.final_text, unit.final_formats = FormatMarker.parse_markers(unit.translated_text)
        
        print(f"✅ 解析完成")
    
    def write_back(self):
        """回写翻译结果到XML"""
        print("\n📥 回写翻译结果...")
        
        for unit in self.units:
            if not unit.xml_element:
                continue
            
            # 清空原有的所有 w:r 节点
            for run in unit.xml_element.find_all('w:r'):
                run.decompose()
            
            # 如果没有格式，创建一个简单的 run
            if not unit.final_formats:
                new_run = self.xml_soup.new_tag('w:r')
                new_text = self.xml_soup.new_tag('w:t')
                new_text.string = unit.final_text
                new_run.append(new_text)
                unit.xml_element.append(new_run)
                continue
            
            # 有格式的情况：需要切分成多个 run
            current_pos = 0
            sorted_formats = sorted(unit.final_formats, key=lambda f: f['start'])
            
            for fmt in sorted_formats:
                # 添加格式前的普通文本
                if fmt['start'] > current_pos:
                    plain_text = unit.final_text[current_pos:fmt['start']]
                    if plain_text:
                        plain_run = self.xml_soup.new_tag('w:r')
                        plain_t = self.xml_soup.new_tag('w:t')
                        plain_t.string = plain_text
                        plain_run.append(plain_t)
                        unit.xml_element.append(plain_run)
                
                # 添加格式化文本
                fmt_run = self.xml_soup.new_tag('w:r')
                rpr = self.xml_soup.new_tag('w:rPr')
                
                if fmt['type'] == 'subscript':
                    vert = self.xml_soup.new_tag('w:vertAlign')
                    vert['w:val'] = 'subscript'
                    rpr.append(vert)
                elif fmt['type'] == 'superscript':
                    vert = self.xml_soup.new_tag('w:vertAlign')
                    vert['w:val'] = 'superscript'
                    rpr.append(vert)
                elif fmt['type'] == 'italic':
                    italic = self.xml_soup.new_tag('w:i')
                    rpr.append(italic)
                
                fmt_run.append(rpr)
                fmt_t = self.xml_soup.new_tag('w:t')
                fmt_t.string = fmt['text']
                fmt_run.append(fmt_t)
                unit.xml_element.append(fmt_run)
                
                current_pos = fmt['end']
            
            # 添加最后的普通文本
            if current_pos < len(unit.final_text):
                trailing_text = unit.final_text[current_pos:]
                if trailing_text:
                    trailing_run = self.xml_soup.new_tag('w:r')
                    trailing_t = self.xml_soup.new_tag('w:t')
                    trailing_t.string = trailing_text
                    trailing_run.append(trailing_t)
                    unit.xml_element.append(trailing_run)
        
        print(f"✅ 回写完成: {len(self.units)} 个单元")
    
    def save(self, output_path: Path):
        """保存修改后的文档"""
        print(f"\n💾 保存文档到: {output_path}")
        
        # 准备新的document.xml内容
        new_xml_content = str(self.xml_soup)
        
        # 复制原始文档，替换document.xml
        with zipfile.ZipFile(self.docx_path, 'r') as zip_read:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_write:
                for item in zip_read.infolist():
                    if item.filename == 'word/document.xml':
                        zip_write.writestr(item, new_xml_content.encode('utf-8'))
                    else:
                        zip_write.writestr(item, zip_read.read(item.filename))
        
        print(f"✅ 保存完成")
    
    def export_comparison(self, output_path: Path):
        """导出对比结果"""
        samples = []
        for idx, unit in enumerate(self.units[:10]):
            samples.append({
                'id': idx,
                'type': unit.unit_type,
                'source': unit.source_text[:100],
                'marked': unit.marked_text[:100],
                'translated': unit.translated_text[:100],
                'final': unit.final_text[:100],
                'formats_in': len(unit.formats),
                'formats_out': len(unit.final_formats)
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 导出对比: {output_path}")

def main():
    print("=" * 80)
    print("AiNiee Word翻译改进 - 完整原型（含回写）")
    print("=" * 80)
    
    # 测试文档
    test_docx = Path(r"D:\项目\H011-GLP-1R\申报资料\中国\BD-IND\英文翻译初稿预处理文件\英文翻译初稿\测试\01_Source\H011-P101临床研究方案20260527去除敏感.docx")
    output_docx = Path("D:/AiNiee-Beta (1)/AiNiee-Beta/prototype_test/translated_output.docx")
    comparison_json = Path("D:/AiNiee-Beta (1)/AiNiee-Beta/prototype_test/comparison.json")
    
    # 创建翻译器
    translator = DocxPrototypeTranslator(test_docx)
    
    # 步骤1: 加载文档
    translator.load()
    
    # 步骤2: 提取翻译单元
    translator.extract_all_units()
    
    # 步骤3: 添加格式标记
    translator.add_format_markers()
    
    # 步骤4: 模拟翻译
    translator.simulate_translation()
    
    # 步骤5: 解析翻译后的格式标记
    translator.parse_translation_markers()
    
    # 步骤6: 回写到XML
    translator.write_back()
    
    # 步骤7: 保存文档
    translator.save(output_docx)
    
    # 步骤8: 导出对比
    translator.export_comparison(comparison_json)
    
    print("\n" + "=" * 80)
    print("✅ 完整流程验证成功！")
    print("=" * 80)
    print(f"\n请打开查看:")
    print(f"  1. 翻译后的文档: {output_docx}")
    print(f"  2. 对比数据: {comparison_json}")

if __name__ == "__main__":
    main()
