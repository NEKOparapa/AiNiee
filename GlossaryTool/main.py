import os
import sys
import json
import threading

# 切换工作目录
# 优先检查是否存在本地资源目录（独立运行模式）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

if os.path.exists(os.path.join(current_dir, "Resource")):
    # 独立运行模式：使用当前目录作为工作目录
    os.chdir(current_dir)
else:
    # 依附模式：使用项目根目录作为工作目录
    os.chdir(project_root)

# 确保父目录在 sys.path 中，以便可以导入 GlossaryTool 包
if project_root not in sys.path:
    sys.path.append(project_root)

from PyQt5.QtCore import Qt, pyqtSignal, QThread, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QFileDialog, QSplitter, QListWidget, QAbstractItemView, QFrame)
from qfluentwidgets import (FluentWindow, ComboBox, CheckBox, StrongBodyLabel, 
                            CaptionLabel, PrimaryPushButton, FluentIcon, 
                            SubtitleLabel, BodyLabel, LineEdit, PushButton, InfoBar, ListWidget,
                            ProgressBar, SimpleCardWidget, HeaderCardWidget)

# 使用本地模块
from GlossaryTool.Base import Base
from GlossaryTool.NERProcessor import NERProcessor
from GlossaryTool.TermResultPage import TermResultPage
from GlossaryTool.FileReader import FileReader

class ExtractionWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, items_data, model_name, entity_types):
        super().__init__()
        self.items_data = items_data
        self.model_name = model_name
        self.entity_types = entity_types

    def run(self):
        try:
            processor = NERProcessor()
            results = processor.extract_terms(
                items_data=self.items_data,
                model_name=self.model_name,
                entity_types=self.entity_types,
                progress_callback=self._on_progress
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
            
    def _on_progress(self, current, total):
        self.progress.emit(current, total)

class GlossaryConfigWidget(QWidget, Base):
    extractionRequested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        # 定义标签集 (参考 TermExtractionDialog)
        self.JAPANESE_TYPES = ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"]
        self.CHINESE_TYPES = self.JAPANESE_TYPES
        self.ENGLISH_TYPES = self.JAPANESE_TYPES
        self.KOREAN_TYPES = ["DT", "LC", "OG", "PS", "QT"]
        self.DEFAULT_TYPES = self.JAPANESE_TYPES
        
        # 存储选中的文件路径
        self.selected_files = []

        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        # 1. 标题
        title_label = SubtitleLabel("术语提取配置", self)
        self.main_layout.addWidget(title_label)

        # 2. 模型选择卡片
        model_card = SimpleCardWidget(self)
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(15, 15, 15, 15)
        
        model_header = StrongBodyLabel("1. 选择NER模型", model_card)
        model_layout.addWidget(model_header)
        model_layout.addSpacing(5)
        
        model_h_layout = QHBoxLayout()
        self.model_combo = ComboBox(self)
        self.load_ner_models()
        
        self.open_model_btn = PushButton(FluentIcon.FOLDER, "打开目录", self)
        self.open_model_btn.clicked.connect(self._open_model_folder)
        
        model_h_layout.addWidget(self.model_combo, 1)
        model_h_layout.addWidget(self.open_model_btn)
        model_layout.addLayout(model_h_layout)
        
        prefix_tip = self.tra("提示: 日语选择ja模型，英语选择en模型，韩语选择ko模型")
        model_layout.addWidget(CaptionLabel(prefix_tip, self))
        
        self.main_layout.addWidget(model_card)

        # 3. 实体类型选择卡片
        entity_card = SimpleCardWidget(self)
        entity_layout_main = QVBoxLayout(entity_card)
        entity_layout_main.setContentsMargins(15, 15, 15, 15)

        entity_header = StrongBodyLabel("2. 提取类型", entity_card)
        entity_layout_main.addWidget(entity_header)
        entity_layout_main.addSpacing(5)

        self.entity_container = QWidget(self)
        self.entity_layout = QGridLayout(self.entity_container)
        self.entity_layout.setContentsMargins(0, 0, 0, 0)
        self.entity_checkboxes = {}
        entity_layout_main.addWidget(self.entity_container)
        
        self.main_layout.addWidget(entity_card)

        # 4. 文件选择卡片
        file_card = SimpleCardWidget(self)
        file_layout_main = QVBoxLayout(file_card)
        file_layout_main.setContentsMargins(15, 15, 15, 15)
        
        file_header = StrongBodyLabel("3. 选择输入文件", file_card)
        file_layout_main.addWidget(file_header)
        file_layout_main.addSpacing(5)
        
        # 顶部按钮区域
        file_btns_layout = QHBoxLayout()
        self.browse_btn = PushButton(FluentIcon.ADD, "添加文件", self)
        self.browse_btn.clicked.connect(self._browse_files)
        
        self.clear_btn = PushButton(FluentIcon.DELETE, "清空列表", self)
        self.clear_btn.clicked.connect(self._clear_files)
        
        file_btns_layout.addWidget(self.browse_btn)
        file_btns_layout.addWidget(self.clear_btn)
        file_btns_layout.addStretch(1)
        file_layout_main.addLayout(file_btns_layout)
        
        # 文件列表显示
        self.file_list_widget = ListWidget(self)
        self.file_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list_widget.setMaximumHeight(150)
        file_layout_main.addWidget(self.file_list_widget)
        
        self.main_layout.addWidget(file_card)

        # 5. 进度条 (初始隐藏)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.main_layout.addWidget(self.progress_bar)
        
        self.progress_label = CaptionLabel("", self)
        self.progress_label.hide()
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.progress_label)

        # 6. 操作按钮
        action_layout = QHBoxLayout()
        self.extract_btn = PrimaryPushButton(FluentIcon.PLAY, "提取术语表", self)
        self.extract_btn.clicked.connect(self._on_extract)
        action_layout.addStretch(1)
        action_layout.addWidget(self.extract_btn)
        self.main_layout.addLayout(action_layout)

        self.main_layout.addStretch(1)

        # 信号连接
        self.model_combo.currentTextChanged.connect(self._update_entity_checkboxes)
        if self.model_combo.count() > 0:
            self._update_entity_checkboxes(self.model_combo.currentText())

    def load_ner_models(self):
        """扫描NER模型"""
        # 优先从当前目录 Resource 找，或者上级目录 Resource 找
        paths_to_check = [
            os.path.join('.', 'Resource', 'Models', 'ner'),
            os.path.join('..', 'Resource', 'Models', 'ner'),
        ]
        
        model_dir = None
        for p in paths_to_check:
            if os.path.exists(p):
                model_dir = p
                break
                
        if not model_dir:
            self.model_combo.addItem("未找到模型目录")
            self.model_combo.setEnabled(False)
            return

        models = []
        try:
            models = [d.name for d in os.scandir(model_dir) if d.is_dir()]
        except:
            pass

        if models:
            self.model_combo.addItems(sorted(models))
        else:
            self.model_combo.addItem("目录中无可用模型")
            self.model_combo.setEnabled(False)

    def _update_entity_checkboxes(self, model_name: str):
        # 清空旧布局
        while self.entity_layout.count():
            item = self.entity_layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
        self.entity_checkboxes.clear()

        # 确定类型
        if model_name.startswith(('ja_', 'ja-')): types = self.JAPANESE_TYPES
        elif model_name.startswith(('en_', 'en-')): types = self.ENGLISH_TYPES
        elif model_name.startswith(('zh_', 'zh-')): types = self.CHINESE_TYPES
        elif model_name.startswith(('ko_', 'ko-')): types = self.KOREAN_TYPES
        else: types = self.DEFAULT_TYPES

        # 标签映射
        type_map = {
            "PERSON": "人物 (Person)", "ORG": "组织 (Org)", "GPE": "国家/城市 (GPE)",
            "LOC": "地点 (Loc)", "PRODUCT": "产品/作品 (Product)", "EVENT": "事件 (Event)",
            "DT": "日期 (Date)", "LC": "地点 (Location)", "PS": "人物 (Person)", 
            "QT": "数量 (Quantity)", "OG": "组织 (Org)"
        }

        row, col = 0, 0
        for t in types:
            display = type_map.get(t, t)
            cb = CheckBox(display, self)
            cb.setChecked(True)
            self.entity_checkboxes[t] = cb
            self.entity_layout.addWidget(cb, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
    
    def _clear_files(self):
        self.selected_files.clear()
        self.file_list_widget.clear()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        valid_exts = ('.txt', '.md', '.json', '.xml', '.html', '.docx', '.xlsx', '.epub', '.pdf', '.lrc', '.srt', '.ass', '.vtt')
        
        for url in urls:
            path = url.toLocalFile()
            if os.path.exists(path):
                if os.path.isfile(path):
                    if path.lower().endswith(valid_exts) and path not in self.selected_files:
                        self.selected_files.append(path)
                        self.file_list_widget.addItem(os.path.basename(path))
                elif os.path.isdir(path):
                    # 如果拖入的是文件夹，遍历其中的文件
                    for root, _, files in os.walk(path):
                        for file in files:
                            if file.lower().endswith(valid_exts):
                                full_path = os.path.join(root, file)
                                if full_path not in self.selected_files:
                                    self.selected_files.append(full_path)
                                    self.file_list_widget.addItem(os.path.basename(full_path))

    def _open_model_folder(self):
        # 优先从当前目录 Resource 找，或者上级目录 Resource 找
        paths_to_check = [
            os.path.join('.', 'Resource', 'Models', 'ner'),
            os.path.join('..', 'Resource', 'Models', 'ner'),
        ]
        
        model_dir = None
        for p in paths_to_check:
            if os.path.exists(p):
                model_dir = os.path.abspath(p)
                break
        
        if model_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(model_dir))
        else:
            InfoBar.warning("提示", "未找到模型目录", parent=self)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "选择文件", 
            os.getcwd(), 
            "Text Files (*.txt *.md *.json *.xml *.html *.docx *.xlsx *.epub *.pdf *.lrc *.srt *.ass *.vtt);;All Files (*)"
        )
        if files:
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
                    self.file_list_widget.addItem(os.path.basename(f))

    def _on_extract(self):
        model_name = self.model_combo.currentText()
        selected_types = [k for k, cb in self.entity_checkboxes.items() if cb.isChecked()]

        if not self.selected_files:
            InfoBar.error("错误", "请至少选择一个文件", parent=self)
            return
        
        if not model_name or "未找到" in model_name:
            InfoBar.error("错误", "请选择有效的模型", parent=self)
            return

        if not selected_types:
            InfoBar.error("错误", "请至少选择一个提取类型", parent=self)
            return

        # 收集文件数据
        items_data = []
        
        for file_path in self.selected_files:
            try:
                content = FileReader.read_file(file_path)
                if content.strip():
                    items_data.append({
                        "source_text": content,
                        "file_path": file_path
                    })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        if not items_data:
            InfoBar.warning("提示", "所选文件中没有有效的文本内容", parent=self)
            return

        self.extractionRequested.emit({
            "items_data": items_data,
            "model_name": model_name,
            "entity_types": selected_types
        })

    def show_progress(self):
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.progress_label.setText("准备开始...")
        self.progress_label.show()

    def update_progress(self, current, total):
        if total > 0:
            val = int((current / total) * 100)
            self.progress_bar.setValue(val)
            self.progress_label.setText(f"正在处理: {current}/{total}")

    def hide_progress(self):
        self.progress_bar.hide()
        self.progress_label.hide()

class GlossaryWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AiNiee 术语提取工具")
        self.resize(1200, 800)

        # 主布局
        self.main_widget = QSplitter(Qt.Horizontal)
        self.main_widget.setObjectName("glossaryInterface")
        self.addSubInterface(self.main_widget, FluentIcon.SEARCH, "提取工具")

        # 左侧配置
        self.config_widget = GlossaryConfigWidget(self)
        self.config_widget.setMinimumWidth(400)
        self.config_widget.setMaximumWidth(500)
        
        # 右侧结果 (初始为空白或占位)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setContentsMargins(0,0,0,0)
        self.placeholder_label = SubtitleLabel("请在左侧配置并开始提取，结果将显示在这里。", self)
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.result_layout.addWidget(self.placeholder_label)

        self.main_widget.addWidget(self.config_widget)
        self.main_widget.addWidget(self.result_container)
        self.main_widget.setStretchFactor(1, 1)

        # 连接信号
        self.config_widget.extractionRequested.connect(self._start_extraction)

    def _start_extraction(self, params):
        self.config_widget.extract_btn.setEnabled(False)
        self.config_widget.extract_btn.setText("提取中...")
        
        self.config_widget.show_progress()

        # 清理旧结果
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # 显示加载中
        loading_label = SubtitleLabel("正在提取术语，请稍候...", self)
        loading_label.setAlignment(Qt.AlignCenter)
        self.result_layout.addWidget(loading_label)

        # 启动线程
        self.worker = ExtractionWorker(
            params['items_data'],
            params['model_name'],
            params['entity_types']
        )
        self.worker.finished.connect(self._on_extraction_finished)
        self.worker.error.connect(self._on_extraction_error)
        self.worker.progress.connect(self._on_extraction_progress)
        self.worker.start()

    def _on_extraction_progress(self, current, total):
        self.config_widget.update_progress(current, total)

    def _on_extraction_finished(self, results):
        self.config_widget.extract_btn.setEnabled(True)
        self.config_widget.extract_btn.setText("提取术语表")
        self.config_widget.hide_progress()

        # 清理加载提示
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if not results:
            self.result_layout.addWidget(BodyLabel("未提取到任何术语。", self))
            return

        # 显示结果页面
        self.result_page = TermResultPage(results, self)
        self.result_layout.addWidget(self.result_page)
        
        InfoBar.success("完成", f"成功提取 {len(results)} 个术语", parent=self)

    def _on_extraction_error(self, error_msg):
        self.config_widget.extract_btn.setEnabled(True)
        self.config_widget.extract_btn.setText("提取术语表")
        self.config_widget.hide_progress()
        InfoBar.error("错误", f"提取过程中发生错误: {error_msg}", parent=self)

if __name__ == '__main__':
    # 启用高分屏支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 加载配置以获取语言设置
    config_path = os.path.join(project_root, "Resource", "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as reader:
                config = json.load(reader)
                Base.current_interface_language = config.get("interface_language", "简中")
        except:
            pass

    # 加载多语言配置
    translation_dir = os.path.join(project_root, "Resource", "Localization")
    combined_data = {}
    if os.path.exists(translation_dir):
        for filename in os.listdir(translation_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(translation_dir, filename)
                try: 
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for top_level_key in data:
                            if isinstance(data[top_level_key], dict):
                                for key, value in data[top_level_key].items():
                                    combined_data[key] = value
                except Exception as e:
                    print(f"Error loading translation file {filename}: {e}")
    Base.multilingual_interface_dict = combined_data

    window = GlossaryWindow()
    window.show()
    sys.exit(app.exec_())
