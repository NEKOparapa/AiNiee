# Word上标和下标问题分析

## 测试结果总结

### XML结构发现

上标和下标在Word XML中通过 `<w:vertAlign>` 标签标识:

```xml
<!-- 下标示例: EC50 -->
<w:p>
  <w:r>
    <w:t>EC</w:t>
  </w:r>
  <w:r>
    <w:rPr>
      <w:vertAlign w:val="subscript"/>
    </w:rPr>
    <w:t>50</w:t>
  </w:r>
  <w:r>
    <w:t> 值为 10 μM。</w:t>
  </w:r>
</w:p>

<!-- 上标示例: 参考文献[1,2] -->
<w:p>
  <w:r>
    <w:t>该研究表明药物有效</w:t>
  </w:r>
  <w:r>
    <w:rPr>
      <w:vertAlign w:val="superscript"/>
    </w:rPr>
    <w:t>[1,2]</w:t>
  </w:r>
  <w:r>
    <w:t>。</w:t>
  </w:r>
</w:p>
```

### 关键发现

1. **上标/下标也会导致文本切分**
   - `EC50` → 切成 2个片段: `EC` + `50`
   - `H2O` → 切成 2个片段: `H` + `2` + `O`
   - `参考文献[1,2]` → 切成 3个片段: `该研究表明药物有效` + `[1,2]` + `。`

2. **格式标识**
   - 下标: `<w:vertAlign w:val="subscript"/>`
   - 上标: `<w:vertAlign w:val="superscript"/>`
   - 位于 `<w:rPr>` (run properties) 中

3. **当前AiNiee的处理**
   ```python
   paragraphs = xml_soup.find_all('w:t')
   ```
   会将上标/下标的文本作为独立条目切分!

## 问题严重性

### 问题1: 科学术语被破坏

**示例:**
- `EC50` → 翻译成独立的 `EC` 和 `50`
  - 可能译为: "EC" + "50" 而不是保持 "EC₅₀"
  
- `H2O` → 翻译成 `H` + `2` + `O`
  - 可能译为: "H" + "two" + "O" 而不是 "H₂O"

**影响:**
- ❌ 化学式被破坏
- ❌ 药理参数(IC50, EC50, Ki, Kd等)丢失含义
- ❌ 数学公式不连贯

### 问题2: 参考文献标注丢失上下文

**示例:**
```
原文: 该研究表明药物有效[1,2]。

当前切分:
1. "该研究表明药物有效"
2. "[1,2]"
3. "。"
```

**后果:**
- `[1,2]` 脱离句子,可能被错误翻译
- 上标格式可能丢失
- 参考文献编号可能被误译

### 问题3: 数学/化学符号的普遍性

在医药、科研文档中,上下标非常常见:
- 药理参数: EC₅₀, IC₅₀, Ki, Kd, t₁/₂
- 化学式: H₂O, CO₂, Ca²⁺, SO₄²⁻
- 数学: x², log₁₀, e^x
- 单位: m², cm³, 10⁶
- 参考文献: [1], [2,3], ¹, ²

## 解决方案

### 方案1: 保留上下标标记 ⭐⭐⭐⭐⭐ 推荐

**核心思路:** 在合并段落时,用特殊标记保留上下标信息

**实现方式:**

1. **读取时转换**
   ```
   EC50 → EC<sub>50</sub>
   参考文献[1,2] → 参考文献<sup>[1,2]</sup>
   H2O → H<sub>2</sub>O
   ```

2. **发送给模型翻译**
   ```
   请翻译(保持<sub>和<sup>标记):
   EC<sub>50</sub> 值为 10 μM。
   ```

3. **翻译后恢复格式**
   ```
   译文: EC<sub>50</sub> value is 10 μM.
   ↓
   应用回Word: EC₅₀ value is 10 μM.
   ```

**优点:**
- ✅ 完全保留上下标信息
- ✅ 让模型理解这是一个整体概念
- ✅ 翻译后可以准确恢复格式
- ✅ 对化学式、数学公式友好

**实现代码示例:**

```python
def extract_paragraph_with_subscript_superscript(paragraph):
    """提取段落文本,保留上下标标记"""
    full_text = []
    runs_info = []
    
    for run in paragraph.find_all('w:r'):
        text_elem = run.find('w:t')
        if not text_elem or not text_elem.string:
            continue
        
        text = str(text_elem.string)
        styles = extract_run_style(run)
        
        # 检查是否是上标或下标
        rpr = run.find('w:rPr')
        if rpr:
            vert_align = rpr.find('w:vertAlign')
            if vert_align:
                align_val = vert_align.get('w:val')
                if align_val == 'subscript':
                    text = f'<sub>{text}</sub>'
                    styles['subscript'] = True
                elif align_val == 'superscript':
                    text = f'<sup>{text}</sup>'
                    styles['superscript'] = True
        
        full_text.append(text)
        runs_info.append({
            'original_text': text_elem.string,
            'marked_text': text,
            'styles': styles
        })
    
    return ''.join(full_text), runs_info
```

**Prompt示例:**

```
系统提示词:
你是专业的医药文档翻译助手。文本中可能包含:
- <sub>标签表示下标,如 EC<sub>50</sub>
- <sup>标签表示上标,如参考文献<sup>[1]</sup>
请保持这些标记不变,只翻译文本内容。

用户输入:
请翻译(保持标记):
EC<sub>50</sub> 值为 10 μM,该研究表明药物有效<sup>[1,2]</sup>。

期望输出:
The EC<sub>50</sub> value is 10 μM, and the study demonstrates drug efficacy<sup>[1,2]</sup>.
```

### 方案2: 智能识别科学术语

**核心思路:** 识别常见的科学术语模式,整体保留

**实现:**
- 使用正则表达式识别: `EC50`, `IC50`, `H2O`, `CO2` 等
- 匹配到的术语作为不可分割单元
- 标记为"禁止翻译"或"保持原样"

**优点:**
- ✅ 保护常见科学术语

**缺点:**
- ⚠️ 无法覆盖所有情况
- ⚠️ 需要维护术语库
- ⚠️ 新术语可能遗漏

### 方案3: 结合使用

1. 段落级合并(基础)
2. 上下标标记转换(核心)
3. 科学术语保护(补充)

## 技术实现要点

### 修改范围

扩展之前的方案,在以下文件中增加上下标处理:

| 文件 | 新增内容 |
|------|---------|
| `DocxAccessor.py` | 添加上下标检测和标记转换 |
| `DocxReader.py` | 生成带标记的源文本 |
| `PromptBuilder.py` | 添加上下标处理说明到系统提示词 |
| `DocxWriter.py` | 解析标记并恢复为Word格式 |

### 格式信息扩展

```python
# 在run的styles中添加
styles = {
    'bold': True/False,
    'italic': True/False,
    'subscript': True/False,      # 新增
    'superscript': True/False,    # 新增
    'original_text': '50',        # 新增: 原始文本
    'marked_text': '<sub>50</sub>', # 新增: 带标记的文本
}
```

### 译文恢复逻辑

```python
def restore_subscript_superscript(translated_text, runs_info):
    """从译文中提取标记并恢复为Word格式"""
    import re
    
    # 提取所有标记
    sub_pattern = r'<sub>(.*?)</sub>'
    sup_pattern = r'<sup>(.*?)</sup>'
    
    # 标记位置
    marks = []
    for match in re.finditer(sub_pattern, translated_text):
        marks.append({
            'type': 'subscript',
            'text': match.group(1),
            'start': match.start(),
            'end': match.end()
        })
    
    for match in re.finditer(sup_pattern, translated_text):
        marks.append({
            'type': 'superscript',
            'text': match.group(1),
            'start': match.start(),
            'end': match.end()
        })
    
    # 移除标记,恢复纯文本
    clean_text = re.sub(r'<su[bp]>|</su[bp]>', '', translated_text)
    
    return clean_text, marks
```

## 测试用例

### 测试1: 药理参数
```
源文: EC<sub>50</sub> 值为 10 μM。
期望: EC₅₀ value is 10 μM.
```

### 测试2: 化学式
```
源文: H<sub>2</sub>O 和 CO<sub>2</sub>
期望: H₂O and CO₂
```

### 测试3: 参考文献
```
源文: 该研究表明有效<sup>[1,2]</sup>。
期望: The study demonstrates efficacy<sup>[1,2]</sup>.
```

### 测试4: 数学公式
```
源文: x<sup>2</sup> + y<sup>2</sup> = z<sup>2</sup>
期望: x² + y² = z²
```

### 测试5: 混合格式
```
源文: **重要**的 EC<sub>50</sub> 值<sup>[1]</sup>
期望: **Important** EC₅₀ value<sup>[1]</sup>
```

## 预期效果

### 改进前
```
翻译条目:
1. "EC"
2. "50"
3. " 值为 10 μM。"

结果: 可能译为 "EC" "fifty" "value is 10 μM"
```

### 改进后
```
翻译条目:
1. "EC<sub>50</sub> 值为 10 μM。"

结果: "EC<sub>50</sub> value is 10 μM." → EC₅₀ value is 10 μM.
```

**质量提升:** ⭐⭐ → ⭐⭐⭐⭐⭐ (对科研文档)

## 风险和注意事项

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 模型不遵守标记 | 中 | 在prompt中强调,使用示例 |
| 标记被翻译 | 低 | 使用明确的HTML风格标记 |
| 复杂嵌套 | 低 | 先支持简单情况 |

## 总结

**上标和下标问题确实存在,而且对科研/医药文档影响很大!**

**推荐方案:**
1. ✅ 段落级合并(基础)
2. ✅ 表格按行翻译(基础)
3. ✅ 上下标标记转换(必需!)

**实施优先级:**
- P0: 段落合并 + 表格行
- P0: 上下标标记(对科研文档至关重要)
- P1: 复杂格式优化

---
生成时间: 2026-06-13
