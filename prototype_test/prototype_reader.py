"""
AiNiee Word翻译改进 - 原型验证脚本

功能：
1. 段落级/单元格级提取
2. 长文本切分（>1000 tokens）
3. 格式标记保留（上标/下标/斜体）
4. 模拟翻译和回写
"""

import zipfile
import re
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString
from typing import List, Dict, Tuple
import json

class TranslationUnit:
    """翻译单元"""
    def __init__(self, source_text: str, unit_type: str, location: str, formats: List[Dict] = None):
        self.source_text = source_text
        self.unit_type = unit_type  # 'paragraph', 'table_cell'
        self.location = location  # 用于回写定位
        self.formats = formats or []  # 格式信息：[{pos, length, type: 'sub'/'sup'/'i'}]
        self.translated_text = ""
    
    def __repr__(self):
        return f"<Unit type={self.unit_type} len={len(self.source_text)} formats={len(self.formats)}>"

class DocxPrototypeReader:
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
        """
        从父元素中提取文本和格式信息
        返回：(完整文本, 格式列表)
        """
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
                # 检查上标/下标
                vert = rpr.find('w:vertAlign')
                if vert:
                    val = vert.get('w:val')
                    if val == 'subscript':
                        formats.append({
                            'start': start_pos,
                            'end': start_pos + len(text_content),
                            'type': 'subscript',
                            'text': text_content
                        })
                    elif val == 'superscript':
                        formats.append({
                            'start': start_pos,
                            'end': start_pos + len(text_content),
                            'type': 'superscript',
                            'text': text_content
                        })
                
                # 检查斜体
                if rpr.find('w:i'):
                    formats.append({
                        'start': start_pos,
                        'end': start_pos + len(text_content),
                        'type': 'italic',
                        'text': text_content
                    })
        
        return full_text, formats
    
    def split_by_sentence(self, text: str, max_tokens: int = 1000) -> List[str]:
        """
        按句子边界切分长文本
        简化版：按标点符号切分，实际应该用 tiktoken 计算 token 数
        """
        # 简化：假设每个字符约等于1个token（实际需要用tiktoken）
        if len(text) <= max_tokens:
            return [text]
        
        # 按句子切分
        sentences = re.split(r'([。！？\.!?])', text)
        
        chunks = []
        current_chunk = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            delimiter = sentences[i+1] if i+1 < len(sentences) else ""
            full_sentence = sentence + delimiter
            
            if len(current_chunk) + len(full_sentence) > max_tokens and current_chunk:
                chunks.append(current_chunk)
                current_chunk = full_sentence
            else:
                current_chunk += full_sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def extract_paragraphs(self):
        """提取所有段落"""
        para_count = 0
        split_count = 0
        
        for para_idx, para in enumerate(self.xml_soup.find_all('w:p')):
            # 跳过表格内的段落（后面单独处理）
            if para.find_parent('w:tc'):
                continue
            
            text, formats = self.extract_text_with_format(para)
            
            if not text.strip():
                continue
            
            # 检查长度并切分
            chunks = self.split_by_sentence(text, max_tokens=1000)
            
            if len(chunks) > 1:
                split_count += 1
                print(f"  ⚠️ 段落 {para_idx} 太长({len(text)} chars)，切分为 {len(chunks)} 个单元")
            
            for chunk_idx, chunk in enumerate(chunks):
                location = f"para_{para_idx}_chunk_{chunk_idx}"
                
                # 调整格式位置（如果是切分后的chunk）
                # 简化：这里不处理格式在切分边界的情况
                chunk_formats = [f for f in formats if f['start'] < len(chunk)]
                
                unit = TranslationUnit(
                    source_text=chunk,
                    unit_type='paragraph',
                    location=location,
                    formats=chunk_formats
                )
                self.units.append(unit)
                para_count += 1
        
        print(f"✅ 提取段落: {para_count} 个翻译单元 (其中 {split_count} 个被切分)")
    
    def extract_table_cells(self):
        """提取所有表格单元格"""
        cell_count = 0
        
        for table_idx, table in enumerate(self.xml_soup.find_all('w:tbl')):
            for row_idx, row in enumerate(table.find_all('w:tr')):
                for cell_idx, cell in enumerate(row.find_all('w:tc')):
                    text, formats = self.extract_text_with_format(cell)
                    
                    if not text.strip():
                        continue
                    
                    location = f"table_{table_idx}_row_{row_idx}_cell_{cell_idx}"
                    
                    unit = TranslationUnit(
                        source_text=text,
                        unit_type='table_cell',
                        location=location,
                        formats=formats
                    )
                    self.units.append(unit)
                    cell_count += 1
        
        print(f"✅ 提取表格单元格: {cell_count} 个翻译单元")
    
    def export_units(self, output_path: Path):
        """导出翻译单元到JSON"""
        data = {
            'source_file': str(self.docx_path),
            'total_units': len(self.units),
            'units': [
                {
                    'id': idx,
                    'type': unit.unit_type,
                    'location': unit.location,
                    'source_text': unit.source_text[:100] + '...' if len(unit.source_text) > 100 else unit.source_text,
                    'text_length': len(unit.source_text),
                    'formats': unit.formats
                }
                for idx, unit in enumerate(self.units)
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 导出翻译单元到: {output_path}")

def main():
    print("=" * 80)
    print("AiNiee Word翻译改进 - 原型验证")
    print("=" * 80)
    
    # 测试文档路径
    test_docx = Path(r"D:\项目\H011-GLP-1R\申报资料\中国\BD-IND\英文翻译初稿预处理文件\英文翻译初稿\测试\01_Source\H011-P101临床研究方案20260527去除敏感.docx")
    
    if not test_docx.exists():
        print(f"❌ 测试文档不存在: {test_docx}")
        return
    
    # 创建读取器
    reader = DocxPrototypeReader(test_docx)
    reader.load()
    
    print("\n" + "=" * 80)
    print("步骤1: 提取段落")
    print("=" * 80)
    reader.extract_paragraphs()
    
    print("\n" + "=" * 80)
    print("步骤2: 提取表格单元格")
    print("=" * 80)
    reader.extract_table_cells()
    
    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)
    print(f"总翻译单元数: {len(reader.units)}")
    
    # 统计格式
    format_count = sum(len(unit.formats) for unit in reader.units)
    subscript_count = sum(1 for unit in reader.units for f in unit.formats if f['type'] == 'subscript')
    superscript_count = sum(1 for unit in reader.units for f in unit.formats if f['type'] == 'superscript')
    italic_count = sum(1 for unit in reader.units for f in unit.formats if f['type'] == 'italic')
    
    print(f"包含格式的单元数: {sum(1 for unit in reader.units if unit.formats)}")
    print(f"  - 下标: {subscript_count}")
    print(f"  - 上标: {superscript_count}")
    print(f"  - 斜体: {italic_count}")
    
    # 显示前5个单元示例
    print("\n" + "=" * 80)
    print("前5个翻译单元示例:")
    print("=" * 80)
    for idx, unit in enumerate(reader.units[:5]):
        print(f"\n单元 {idx}:")
        print(f"  类型: {unit.unit_type}")
        print(f"  位置: {unit.location}")
        print(f"  文本: {unit.source_text[:80]}...")
        if unit.formats:
            print(f"  格式: {unit.formats[:3]}")
    
    # 导出结果
    output_json = Path("D:/AiNiee-Beta (1)/AiNiee-Beta/prototype_test/extraction_result.json")
    reader.export_units(output_json)
    
    print("\n" + "=" * 80)
    print("✅ 原型验证完成！")
    print("=" * 80)
    print(f"\n对比:")
    print(f"  原始方法: ~11,854 个 w:t 节点")
    print(f"  现有合并: ~5,493 个单元")
    print(f"  新方法: {len(reader.units)} 个单元 ✅")
    print(f"  改进: {(1 - len(reader.units)/5493)*100:.1f}% 减少")

if __name__ == "__main__":
    main()
