# AiNiee PDF翻译及打包问题修复报告 (2026-06-18)

## 📌 问题一：PDF 表格翻译乱码/漏译问题

### 问题描述
在使用 `AiNiee` 翻译包含表格的 PDF 文件时，正文内容可以被正确提取并翻译，但表格内的文本在翻译后依然是外语（或者出现乱码、排版异常）。

### 根本原因
通过分析 `ModuleFolders/Domain/FileAccessor/BabeldocPdfAccessor.py` 发现，代码中对底层的 `babeldoc` 库进行了一个**强行劫持操作（Monkey Patch）**：
```python
# 将 babeldoc 原本处理 PDF 表格的函数覆盖为一个仅返回 False 的空函数
from babeldoc.core.pdf.parser.table import TableParser
TableParser.process = lambda *args, **kwargs: False
```
由于 `TableParser.process` 被强制覆盖并返回 `False`，导致 `pdf2zh` 引擎（Babeldoc 底层依赖）完全放弃了对 PDF 表格的抽取和解析能力。这使得表格内的文字要么没被读取，要么作为背景块处理，从而导致翻译环节完全略过表格内容。

### 修复方案
**移除代码中对 `TableParser.process` 的劫持。**
在 `BabeldocPdfAccessor.py` 中注释掉了这段 `Monkey Patch` 逻辑：
```python
# from babeldoc.core.pdf.parser.table import TableParser
# TableParser.process = lambda *args, **kwargs: False
```
解除屏蔽后，恢复了 `babeldoc` 原生的表格解析能力，PDF 表格能够被正确拆解为结构化数据并进行翻译，并在写回时保持排版。

---

## 📌 问题二：PyInstaller 打包后加载 FileReader 子模块失败

### 问题描述
执行打包后，双击运行 `dist\AiNiee\AiNiee.exe`，当进行到翻译项目数据载入环节时，程序崩溃并抛出异常：
```
[ERROR] 翻译项目数据载入失败，请检查项目类型与输入文件夹设置。
No module named 'ModuleFolders.Domain.FileReader.TxtReader'
```

### 根本原因
`AiNiee` 的 `FileReader` 和 `FileOutputer` 是通过 `importlib` **动态懒加载（Lazy Import）** 子模块（例如 `TxtReader.py`、`DocxReader.py` 等）。
为了让 PyInstaller 能够打包这些隐式依赖，`AiNiee.spec` 中使用了 `collect_submodules`：
```python
hiddenimports += collect_submodules('ModuleFolders.Domain.FileReader')
```
**但是**，当 PyInstaller 运行并计算 `AiNiee.spec` 时，它所在的 Python 环境路径（`sys.path`）默认并没有包含项目根目录（即 `ModuleFolders` 所在的父目录）。因此，`collect_submodules` 无法找到 `ModuleFolders` 包，直接静默返回了空列表。这导致所有的 Reader 和 Writer 模块均未被打包进 `.exe` 内。

### 修复方案
在 `AiNiee.spec` 的最顶部加入系统路径注册逻辑，确保 `collect_submodules` 能够成功扫描到项目本地文件夹：
```python
import sys
import os
sys.path.insert(0, os.path.abspath(SPECPATH))
```
修改后，再次使用 `pyinstaller -y AiNiee.spec` 进行构建。PyInstaller 成功扫描到了诸如 `AssReader`、`BabeldocPdfReader`、`TxtReader` 等底层支持模块，并正确将其封入应用包中。

---

## 🚀 总结
1. 解除对 `babeldoc` 的表格屏蔽后，大大提升了 PDF 翻译中带有复杂表格排版的能力。
2. 修复 `AiNiee.spec` 文件使得构建流水线能够真实有效地收集所有动态导入插件，解决了环境发布后的启动崩溃问题。
