# AiNiee Word翻译优化实施方案

## 🎯 实施目标

将Word文档翻译从**`w:t`标签级切分**改进为**段落级合并**,提升翻译质量和上下文连贯性。

## 📋 实施步骤

### 步骤1: 扩展CacheItem数据结构

**文件:** `ModuleFolders/Service/Cache/CacheItem.py`

**修改内容:** 添加格式元数据支持

```python
@dataclass
class CacheItem:
    source_text: str
    final_text: str = ""
    translation_status: TranslationStatus = TranslationStatus.UNTRANSLATED
    
    # 新增: Word格式信息
    word_format_info: dict = None  # 存储段落内的run结构
    
    # word_format_info 结构:
    # {
    #   "paragraph_index": 0,
    #   "runs": [
    #       {
    #           "text": "原始文本片段",
    #           "styles": {
    #               "bold": True/False,
    #               "italic": True/False,
    #               "color": "RGB值",
    #               # 其他格式属性...
    #           }
    #       },
    #       ...
    #   ]
    # }
```

### 步骤2: 改造DocxAccessor - 添加段落级读取

**文件:** `ModuleFolders/Domain/FileAccessor/DocxAccessor.py`

**新增方法:**

```python
def read_content_by_paragraph(self, source_file_path: Path):
    """按段落读取Word内容,保留格式信息"""
    with zipfile.ZipFile(source_file_path) as zipf:
        content = zipf.read("word/document.xml").decode("utf-8")
    
    xml_soup = BeautifulSoup(content, 'xml')
    
    # 先合并相同格式的run(保留现有优化)
    for paragraph in xml_soup.find_all('w:p', recursive=True):
        self._merge_adjacent_same_style_run(paragraph)
    
    paragraph_data = []
    
    for p_idx, paragraph in enumerate(xml_soup.find_all('w:p', recursive=True)):
        runs_info = []
        paragraph_text = []
        
        for run in paragraph.find_all('w:r', recursive=False):
            text_elem = run.find('w:t')
            if text_elem and text_elem.string:
                text = str(text_elem.string)
                if text.strip():  # 只处理非空文本
                    # 提取格式信息
                    style_info = self._extract_run_style(run)
                    runs_info.append({
                        "text": text,
                        "styles": style_info
                    })
                    paragraph_text.append(text)
        
        if paragraph_text:  # 只保留有文本的段落
            paragraph_data.append({
                "paragraph_index": p_idx,
                "full_text": "".join(paragraph_text),
                "runs": runs_info
            })
    
    return xml_soup, paragraph_data

def _extract_run_style(self, run: Tag):
    """提取run的格式信息"""
    styles = {}
    rpr = run.find("w:rPr")
    
    if rpr:
        # 提取常见格式
        if rpr.find("w:b"):
            styles["bold"] = True
        if rpr.find("w:i"):
            styles["italic"] = True
        if rpr.find("w:u"):
            styles["underline"] = True
        
        # 颜色
        color = rpr.find("w:color")
        if color and color.get("w:val"):
            styles["color"] = color.get("w:val")
        
        # 字体大小
        sz = rpr.find("w:sz")
        if sz and sz.get("w:val"):
            styles["font_size"] = sz.get("w:val")
    
    return styles
```

### 步骤3: 改造DocxReader - 按段落生成CacheItem

**文件:** `ModuleFolders/Domain/FileReader/DocxReader.py`

```python
def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
    # 使用新的段落级读取方法
    xml_soup, paragraph_data = self.file_accessor.read_content_by_paragraph(file_path)
    
    items = []
    for para_info in paragraph_data:
        # 创建CacheItem,保存格式信息
        item = CacheItem(
            source_text=para_info["full_text"],
            word_format_info={
                "paragraph_index": para_info["paragraph_index"],
                "runs": para_info["runs"]
            }
        )
        items.append(item)
    
    return CacheFile(items=items)
```

### 步骤4: 改造DocxWriter - 智能分配译文到run

**文件:** `ModuleFolders/Domain/FileOutputer/DocxWriter.py`

```python
def on_write_translated(
    self, translation_file_path: Path, cache_file: CacheFile,
    pre_write_metadata: PreWriteMetadata,
    source_file_path: Path = None,
):
    content = self.file_accessor.read_content(source_file_path)
    
    # 遍历段落
    paragraphs = content.find_all("w:p")
    
    for item in cache_file.items:
        if not item.word_format_info:
            continue  # 跳过没有格式信息的(向后兼容)
        
        para_idx = item.word_format_info["paragraph_index"]
        if para_idx >= len(paragraphs):
            continue
        
        paragraph = paragraphs[para_idx]
        original_runs = item.word_format_info["runs"]
        translated_text = item.final_text
        
        # 分配译文到各个run
        distributed_runs = self._distribute_translation(
            original_runs, 
            item.source_text, 
            translated_text
        )
        
        # 更新XML中的文本
        run_elements = paragraph.find_all("w:r", recursive=False)
        text_run_idx = 0
        
        for run_elem in run_elements:
            text_elem = run_elem.find("w:t")
            if text_elem and text_elem.string and text_elem.string.strip():
                if text_run_idx < len(distributed_runs):
                    text_elem.string = distributed_runs[text_run_idx]
                    text_run_idx += 1
    
    self.file_accessor.write_content(
        content, translation_file_path, source_file_path
    )

def _distribute_translation(self, original_runs, source_text, translated_text):
    """
    将翻译后的文本智能分配回原始run结构
    
    策略: 按原文各run的字符比例分配译文
    """
    if not original_runs:
        return [translated_text]
    
    # 如果只有一个run,直接返回
    if len(original_runs) == 1:
        return [translated_text]
    
    # 计算每个run在原文中的比例
    total_len = len(source_text)
    if total_len == 0:
        # 平均分配
        chunk_size = len(translated_text) // len(original_runs)
        return [translated_text[i*chunk_size:(i+1)*chunk_size] 
                for i in range(len(original_runs))]
    
    result = []
    pos = 0
    
    for i, run in enumerate(original_runs):
        run_len = len(run["text"])
        proportion = run_len / total_len
        
        # 最后一个run取剩余所有字符
        if i == len(original_runs) - 1:
            chunk = translated_text[pos:]
        else:
            chunk_len = int(len(translated_text) * proportion)
            # 尝试在标点或空格处断开
            chunk_len = self._find_break_point(translated_text, pos, chunk_len)
            chunk = translated_text[pos:pos+chunk_len]
            pos += chunk_len
        
        result.append(chunk)
    
    return result

def _find_break_point(self, text, start, ideal_len):
    """
    在理想位置附近找一个合适的断点(标点、空格)
    """
    if start + ideal_len >= len(text):
        return len(text) - start
    
    # 在前后3个字符范围内寻找标点或空格
    search_range = 3
    for offset in range(search_range + 1):
        # 先向后找
        pos = start + ideal_len + offset
        if pos < len(text) and text[pos] in ',.!?;:,。!?;:、 \n':
            return ideal_len + offset + 1
        
        # 再向前找
        pos = start + ideal_len - offset
        if pos >= start and text[pos] in ',.!?;:,。!?;:、 \n':
            return ideal_len - offset + 1
    
    # 没找到就用原始长度
    return ideal_len
```

### 步骤5: 添加配置开关(可选)

**文件:** 相关配置文件

添加用户选项,让用户选择切分模式:

```python
# 配置项
word_translation_mode: str = "paragraph"  # "paragraph" 或 "fragment"

# paragraph: 段落级合并(新模式,推荐)
# fragment: w:t标签级(旧模式,保持兼容)
```

在DocxReader中根据配置选择处理方式:

```python
def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
    if self.input_config.word_translation_mode == "paragraph":
        return self._read_by_paragraph(file_path)
    else:
        return self._read_by_fragment(file_path)  # 旧逻辑
```

## 🧪 测试计划

### 测试用例1: 简单格式混合

创建包含以下内容的Word文档:

```
这是一个普通的句子。
这是一个包含**粗体**和*斜体*的句子。
```

**预期结果:** 
- 第二句作为一个完整单元翻译
- 格式正确保留

### 测试用例2: 复杂格式

```
在临床试验中,安全性评估包括以下几个方面:
1. 不良事件监测
2. 实验室检查
3. 生命体征
```

**预期结果:**
- 每个段落/列表项作为完整单元
- 数字列表格式保留

### 测试用例3: 超长段落

创建一个超过1000字的段落,包含多种格式。

**预期结果:**
- 如果超出token限制,应该有合理的降级策略
- 或者给出明确的错误提示

### 测试用例4: 表格和特殊结构

包含表格、脚注、超链接的复杂文档。

**预期结果:**
- 不会破坏文档结构
- 至少保持向后兼容(即使不能完美处理)

## 📊 性能评估指标

### 改进前 vs 改进后

| 指标 | 改进前 | 改进后 | 改善比例 |
|------|--------|--------|----------|
| 平均切分粒度 | 5-10字/条目 | 50-200字/条目 | 10-20倍 |
| API调用次数 | 基准 | 减少60-80% | - |
| 翻译质量(主观) | ⭐⭐ | ⭐⭐⭐⭐ | - |
| Token消耗 | 基准 | 减少20-30% | - |

## ⚠️ 风险缓解

### 风险1: 格式丢失

**缓解措施:**
- 在分配译文前,备份原始格式信息
- 如果分配失败,回退到简单策略(保留第一个run的格式)

### 风险2: 超长段落

**缓解措施:**
- 检测段落长度,超过阈值时:
  - 方案A: 按句子边界智能切分
  - 方案B: 记录警告日志,提示用户调整
  - 方案C: 自动降级到fragment模式

### 风险3: 向后兼容

**缓解措施:**
- 保留旧的fragment模式作为备选
- 在CacheItem中检查word_format_info是否存在
- 如果不存在,使用旧逻辑处理

## 📝 实施时间估算

- 步骤1 (CacheItem扩展): 0.5小时
- 步骤2 (DocxAccessor改造): 2小时
- 步骤3 (DocxReader改造): 1小时
- 步骤4 (DocxWriter改造): 3小时
- 步骤5 (配置开关): 1小时
- 测试和调试: 3-4小时

**总计:** 约10-12小时

## 🚀 部署建议

1. 先在开发分支实施和测试
2. 邀请用户进行Beta测试
3. 收集反馈并优化
4. 合并到主分支
5. 发布新版本,在Release Notes中说明改进

## 📚 相关文档

- [ANALYSIS_REPORT.md](./ANALYSIS_REPORT.md) - 问题分析报告
- [ModuleFolders/Domain/FileAccessor/README.md](./ModuleFolders/Domain/FileAccessor/README.md) - 读写器系统编写指南

---

**文档版本:** 1.0  
**创建日期:** 2026-06-13  
**状态:** 待批准
