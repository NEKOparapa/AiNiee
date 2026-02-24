# AiNiee 术语提取工具 (独立版)

这是一个基于 PyQt5 和 QFluentWidgets 的独立术语提取工具，从 AiNiee 项目中提取而来。
它可以独立运行，无需依赖 AiNiee 的其他部分。

## 功能
- 从文本文件批量提取命名实体 (NER)
- 支持多种语言模型 (日语, 英语, 中文等)
- 结果导出与直接保存到术语表
- 支持拖拽文件/文件夹
- 支持 .txt, .docx, .epub, .pdf, .xlsx, .json 等多种格式

## 目录结构
- `main.py`: 程序入口
- `Resource/`: 资源目录 (存放配置文件和模型)
- `Resource/Models/ner/`: 存放 NER 模型

## 安装依赖

运行本工具需要安装以下 Python 库：

```bash
pip install -r requirements.txt
```

如果需要使用日语 NER 模型，还需要安装 `sudachipy` 和 `sudachidict-core`：

```bash
pip install sudachipy sudachidict-core
```

**注意**: Windows 下 Python 3.14 可能无法安装 `sudachipy`，请尝试使用 Python 3.10 - 3.13 版本。

## 模型配置

请将 spaCy NER 模型放置在 `Resource/Models/ner` 目录下。
例如：`Resource/Models/ner/ja_core_news_md`

## 运行

直接运行 `main.py`：

```bash
python main.py
```

或者如果放在 AiNiee 项目中，也可以通过项目根目录运行。
