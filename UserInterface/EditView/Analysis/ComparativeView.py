import os
from pathlib import Path
import re
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QFileDialog,
    QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle
)
from PyQt5.QtGui import QTextDocument, QAbstractTextDocumentLayout, QPalette
from qfluentwidgets import (
    TableWidget, PrimaryPushButton, BodyLabel, InfoBar, ProgressBar,
    SpinBox, TransparentPushButton
)
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Domain.FileReader.BaseReader import InputConfig
from ModuleFolders.Domain.FileReader.BabeldocPdfReader import BabeldocPdfReader
from ModuleFolders.Domain.FileReader.DocxReader import DocxReader
from ModuleFolders.Service.ComparativeAnalysis.SmartAlignmentService import SmartAlignmentService
from ModuleFolders.Service.ComparativeAnalysis.QAEvaluationTask import QAEvaluationTask


from qfluentwidgets import TableItemDelegate

class WordWrapDelegate(TableItemDelegate):
    '''Auto word-wrap delegate for table cells, supporting qfluentwidgets themes.'''
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_painting = False

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # 如果正在底层 paint 中被调用，清空文本，阻止底层绘制重叠的单行死板文本
        if self._is_painting:
            option.text = ''

    def paint(self, painter, option, index):
        # 允许底层绘制背景、指示器、悬停效果等，但通过 _is_painting=True 让其内部调用的 initStyleOption 将文本清空
        self._is_painting = True
        super().paint(painter, option, index)
        self._is_painting = False
        
        # 现在恢复正常状态，获取带有正确文本和主题颜色的 option
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        
        painter.save()
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setPlainText(options.text)
        doc.setTextWidth(max(options.rect.width(), 1))
        
        ctx = QAbstractTextDocumentLayout.PaintContext()
        # options.palette.color() 已被 TableItemDelegate 正确设置为主颜色或自定义颜色
        ctx.palette.setColor(QPalette.Text, options.palette.color(QPalette.Active, QPalette.Text))
        if options.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, options.palette.color(QPalette.Active, QPalette.HighlightedText))
            
        style = QApplication.style() if options.widget is None else options.widget.style()
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options)
        
        painter.translate(text_rect.topLeft())
        painter.setClipRect(text_rect.translated(-text_rect.topLeft()))
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setPlainText(options.text)
        w = options.rect.width() if options.rect.width() > 0 else 300
        doc.setTextWidth(w)
        
        # 获取基础文字高度并加上 Fluent 样式的边距
        base_size = super().sizeHint(option, index)
        return QSize(int(doc.idealWidth()), int(doc.size().height()) + base_size.height() - super(TableItemDelegate, self).sizeHint(option, index).height() + 8)


class QATaskThread(QThread):
    progress_updated = pyqtSignal(int, int)
    partial_eval = pyqtSignal(list)
    finished_eval = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, qa_task, aligned_data, parent=None):
        super().__init__(parent)
        self.qa_task = qa_task
        self.aligned_data = aligned_data

    def run(self):
        try:
            def progress_callback(c, t, current_results=None):
                self.progress_updated.emit(c, t)
                if current_results is not None and (c % 10 == 0 or c == t):
                    self.partial_eval.emit(list(current_results))
            results = self.qa_task.evaluate(self.aligned_data, progress_callback=progress_callback)
            if self.qa_task.is_stopped:
                self.error_occurred.emit('STOPPED')
            else:
                self.finished_eval.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ComparativeViewWidget(QWidget, ConfigMixin):
    def __init__(self, cache_manager, parent=None):
        super().__init__(parent)
        self.cache_manager = cache_manager
        self.aligned_data = []
        self.qa_task = None
        self.qa_thread = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header_layout = QHBoxLayout()

        self.import_button = PrimaryPushButton(self.tra('导入已翻译文件(PDF/Word)'), self)
        self.import_button.clicked.connect(self._on_import_clicked)

        self.remove_tags_button = TransparentPushButton(self.tra('移除<>等特殊标签'), self)
        self.remove_tags_button.clicked.connect(self._on_remove_tags_clicked)
        self.remove_tags_button.setEnabled(False)

        self.expand_row_button = TransparentPushButton(self.tra('展开选中行'), self)
        self.expand_row_button.clicked.connect(self._on_expand_row_clicked)
        self.expand_row_button.setEnabled(False)
        self.expand_row_button.hide()

        self.shrink_row_button = TransparentPushButton(self.tra('收起选中行'), self)
        self.shrink_row_button.clicked.connect(self._on_shrink_row_clicked)
        self.shrink_row_button.setEnabled(False)
        self.shrink_row_button.hide()

        self.start_qa_button = PrimaryPushButton(self.tra('开始 QA 评估'), self)
        self.start_qa_button.clicked.connect(self._on_start_qa_clicked)
        self.start_qa_button.setEnabled(False)

        self.thread_label = BodyLabel(self.tra('并发线程:'), self)
        self.thread_label.hide()

        self.thread_spin_box = SpinBox(self)
        self.thread_spin_box.setRange(1, 20)
        self.thread_spin_box.setValue(3)
        self.thread_spin_box.setFixedWidth(120)
        self.thread_spin_box.setEnabled(False)
        self.thread_spin_box.hide()

        self.status_label = BodyLabel(self.tra('未导入'), self)

        header_layout.addWidget(self.import_button)
        header_layout.addWidget(self.remove_tags_button)
        header_layout.addWidget(self.expand_row_button)
        header_layout.addWidget(self.shrink_row_button)
        header_layout.addWidget(self.start_qa_button)
        header_layout.addWidget(self.thread_label)
        header_layout.addWidget(self.thread_spin_box)
        header_layout.addWidget(self.status_label)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        self.progress_bar = ProgressBar(self)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.table = TableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            self.tra('行号'),
            self.tra('原文(AiNiee)'),
            self.tra('导入译文'),
            self.tra('QA评估结果')
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self._wrap_delegate = WordWrapDelegate(self.table)
        for col in range(1, 4):
            self.table.setItemDelegateForColumn(col, self._wrap_delegate)
        layout.addWidget(self.table)

    def _on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tra('选择译文文件'), '',
            self.tra('支持的文档 (*.docx *.pdf)')
        )
        if not file_path:
            return
        self.status_label.setText(self.tra('正在解析与对齐...'))
        self.import_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        QTimer.singleShot(100, lambda: self._process_file(file_path))

    def _process_file(self, file_path_str: str):
        try:
            path = Path(file_path_str)
            ext = path.suffix.lower()
            input_config = InputConfig(path)
            if ext == '.pdf':
                reader = BabeldocPdfReader(input_config)
            elif ext == '.docx':
                reader = DocxReader(input_config)
            else:
                raise ValueError('不支持的文件格式')
            cache_file = reader.read_source_file(path)
            imported_texts = [item.source_text for item in cache_file.items if item.source_text.strip()]
            if not imported_texts:
                raise ValueError('提取的文本为空')
            source_items = []
            for pt in self.cache_manager.project.file_project_types:
                for item in self.cache_manager.project.items_iter(pt):
                    if item.source_text.strip():
                        source_items.append(item)
            if not source_items:
                raise ValueError('当前项目为空，没有可以对比的原文')
            align_service = SmartAlignmentService(model_name='default', rpm_limit=60)
            self.aligned_data = align_service.align(source_items, imported_texts)
            self._rebuild_table()
            self.start_qa_button.setEnabled(True)
            self.remove_tags_button.setEnabled(True)
            self.expand_row_button.setEnabled(True)
            self.shrink_row_button.setEnabled(True)
            self.expand_row_button.show()
            self.shrink_row_button.show()
            self.thread_label.show()
            self.thread_spin_box.show()
            self.thread_spin_box.setEnabled(True)
            self.import_button.setEnabled(True)
            self.status_label.setText(self.tra('导入与对齐完成，等待开始评估...'))
            self.progress_bar.hide()
        except Exception as e:
            self.status_label.setText(self.tra('处理失败'))
            InfoBar.error(self.tra('错误'), str(e), duration=3000, parent=self)
            self.import_button.setEnabled(True)
            self.progress_bar.hide()

    def _rebuild_table(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        self.table.setRowCount(len(self.aligned_data))
        for i, (source_item, imported_text) in enumerate(self.aligned_data):
            item0 = QTableWidgetItem(str(i + 1))
            item1 = QTableWidgetItem(source_item.source_text)
            item2 = QTableWidgetItem(imported_text)
            item3 = QTableWidgetItem(self.tra('等待评估...'))
            for itm in (item0, item1, item2, item3):
                itm.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.table.setItem(i, 0, item0)
            self.table.setItem(i, 1, item1)
            self.table.setItem(i, 2, item2)
            self.table.setItem(i, 3, item3)

    def _update_qa_column(self, qa_results):
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtGui import QColor
        for i in range(self.table.rowCount()):
            if qa_results and i < len(qa_results) and qa_results[i]:
                qa = qa_results[i]
                qa_text = self.tra('通过') if qa.get('is_good') else qa.get('issues', self.tra('有瑕疵'))
            else:
                qa_text = self.tra('等待评估...')
            item_qa = self.table.item(i, 3)
            if item_qa is None:
                item_qa = QTableWidgetItem()
                item_qa.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                self.table.setItem(i, 3, item_qa)
            item_qa.setText(qa_text)
            if '通过' in qa_text:
                item_qa.setForeground(QColor('#2A9D68'))
            elif '等待' not in qa_text:
                item_qa.setForeground(QColor('#D64545'))

    def _on_remove_tags_clicked(self):
        if not self.aligned_data:
            return
        new_aligned = []
        for source_item, imported_text in self.aligned_data:
            cleaned_target = re.sub(r'<[^>]*>', '', imported_text)
            if hasattr(source_item, 'source_text') and source_item.source_text:
                source_item.source_text = re.sub(r'<[^>]*>', '', source_item.source_text)
            new_aligned.append((source_item, cleaned_target))
        self.aligned_data = new_aligned
        self._rebuild_table()
        InfoBar.success(self.tra('成功'), self.tra('已清理所有原文和译文中的<>标签'), duration=2000, parent=self)

    def _on_expand_row_clicked(self):
        selected_rows = set(item.row() for item in self.table.selectedItems())
        for row in selected_rows:
            self.table.resizeRowToContents(row)

    def _on_shrink_row_clicked(self):
        selected_rows = set(item.row() for item in self.table.selectedItems())
        for row in selected_rows:
            self.table.setRowHeight(row, 40)

    def _on_start_qa_clicked(self):
        if self.qa_thread is not None and self.qa_thread.isRunning():
            if self.qa_task is not None:
                self.qa_task.stop()
            self.start_qa_button.setEnabled(False)
            self.start_qa_button.setText(self.tra('正在停止...'))
            return
        self.start_qa_button.setText(self.tra('停止 QA 评估'))
        self.import_button.setEnabled(False)
        self.remove_tags_button.setEnabled(False)
        self.thread_spin_box.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setText(self.tra('正在进行 QA 评估...'))
        try:
            from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
            config = TaskConfig()
            config.initialize('proofread')
            config.prepare_for_active_platform('proofread')
            platform_config = config.get_active_platform_configuration()
            thread_count = self.thread_spin_box.value()
            self.qa_task = QAEvaluationTask(platform_config=platform_config, thread_counts=thread_count)
            self.qa_thread = QATaskThread(self.qa_task, self.aligned_data, self)
            self.qa_thread.progress_updated.connect(self._on_qa_progress)
            self.qa_thread.partial_eval.connect(self._on_qa_partial)
            self.qa_thread.finished_eval.connect(self._on_qa_finished)
            self.qa_thread.error_occurred.connect(self._on_qa_error)
            self.qa_thread.start()
        except Exception as e:
            self._on_qa_error(str(e))

    def _on_qa_progress(self, current: int, total: int):
        self.progress_bar.setValue(int((current / max(1, total)) * 100))

    def _on_qa_partial(self, current_results):
        self._update_qa_column(current_results)

    def _on_qa_finished(self, results):
        self._update_qa_column(results)
        self.status_label.setText(self.tra('分析完成'))
        self._cleanup_qa_ui()

    def _on_qa_error(self, error_msg: str):
        if error_msg == 'STOPPED':
            self.status_label.setText(self.tra('已停止 QA 评估'))
        else:
            self.status_label.setText(self.tra('QA 评估失败'))
            InfoBar.error(self.tra('错误'), error_msg, duration=3000, parent=self)
        self._cleanup_qa_ui()

    def _cleanup_qa_ui(self):
        self.start_qa_button.setText(self.tra('开始 QA 评估'))
        self.import_button.setEnabled(True)
        self.start_qa_button.setEnabled(True)
        self.remove_tags_button.setEnabled(True)
        self.thread_spin_box.setEnabled(True)
        self.progress_bar.hide()
