"""Independent media workspaces over explicit, resumable backend interfaces."""
import copy
import math
import threading
import time
from pathlib import PurePosixPath
from uuid import uuid4

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHeaderView, QHBoxLayout,
    QSplitter, QStackedWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from qfluentwidgets import (CaptionLabel, ComboBox, FluentIcon, IconWidget,
    MessageBox, PrimaryPushButton, SearchLineEdit, SimpleCardWidget,
    SingleDirectionScrollArea, StrongBodyLabel, TransparentPushButton, TreeWidget)

from Frontend.core.config import ConfigMixin
from Frontend.core.media_task_config import read_media_export_settings
from Frontend.components.toast import ToastMixin
from Frontend.services.media_client import MediaClient
from Frontend.pages.media.start_page import MediaStartPage
from Frontend.pages.media.monitoring_panel import MediaMonitoringPanel
from Frontend.pages.media.workflow_header import MediaWorkflowHeader
from Frontend.pages.media.workflow_selector import MediaWorkflowSelector
from Frontend.pages.media.workflow_state import prerequisite_message, workflow_states
from Frontend.pages.workspace.translation.language_settings_card import LanguageSettingsCard


class MediaWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    workspaceReady = pyqtSignal(object)
    stageChanged = pyqtSignal(str)
    stageFinished = pyqtSignal(str, object)

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.cancelled = threading.Event()
        self.operation_id = None
        self.operation_kind = None

    def run(self):
        try:
            self.completed.emit(self.action(self))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.operation_id = None


class MediaWorkspacePage(QFrame, ConfigMixin, ToastMixin):
    def __init__(self, name, kind, parent=None, backend=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.kind = kind
        self.client = MediaClient(backend or self.config_backend())
        self.workspace = None
        self._worker = None
        self._aux_workers = []
        self._history_worker = None
        self._history_revision = 0
        self._disposed = False
        self._dirty = False
        self._pending_edits = {}
        self._pending_generation_options = {}
        self._updating_image_options = False
        self._file_rows = {}
        self._selected_id = None
        self._selecting = False
        self._polling = False
        self._stage_label = ""
        self._active_stage = ""
        self._live_progress = {}
        self._run_started = None
        self._run_elapsed = 0
        self._run_state = ""
        self._status_message = ""
        self._stage_results = {}
        self._planned_stages = []
        self._build_ui()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_workspace)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(1200)
        self._progress_timer.timeout.connect(self._poll_operation)
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(1000)
        self._metrics_timer.timeout.connect(self._refresh_metrics)

    @property
    def busy(self):
        return self._worker is not None

    @staticmethod
    def _brief_message(text):
        text = " ".join(str(text).split())
        return text if len(text) <= 180 else text[:177] + "…"

    def _set_status(self, text):
        self._status_message = str(text or "")
        summary = self._brief_message(self._status_message)
        self.status_label.setText(summary)
        self.status_label.setToolTip(self._status_message if summary != self._status_message else "")
        self.monitoring.set_status(self._status_message)
        self._refresh_status_visibility()

    def _refresh_status_visibility(self, *unused):
        hide_footer = (self.stack.currentWidget() is self.work_page
                       and (self.kind == "image"
                            or self.workflow_stack.currentWidget() is self.translation_page))
        self.status_label.setVisible(bool(self._status_message) and not hide_footer)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.stack = QStackedWidget(self)
        outer.addWidget(self.stack, 1)
        self.start_page = MediaStartPage(self.kind, self)
        self.start_page.layout().setContentsMargins(24, 24, 24, 20)
        self.import_stop_button = TransparentPushButton(FluentIcon.CANCEL_MEDIUM, self.tra("停止导入"), self.start_page)
        self.import_stop_button.clicked.connect(self.stop_operation)
        self.import_stop_button.hide()
        self.start_page.layout().insertWidget(1, self.import_stop_button, 0, Qt.AlignRight)
        self.drop_card = self.start_page.drop_card
        self.pick_files = self.start_page.pick_files
        self.pick_folder = self.start_page.pick_folder
        self.pick_zip = self.start_page.pick_zip
        self.history_list = self.start_page.history_list
        self.drop_card.pathsDropped.connect(self.import_paths)
        self.pick_files.clicked.connect(self._choose_files)
        self.pick_folder.clicked.connect(self._choose_folder)
        self.pick_zip.clicked.connect(self._choose_zip)
        self.history_list.itemDoubleClicked.connect(lambda item: self.load_workspace(item.data(Qt.UserRole)))
        self.start_page.deleteRequested.connect(self._delete_workspace)
        self.stack.addWidget(self.start_page)

        self.work_page = QWidget(self)
        work = QVBoxLayout(self.work_page)
        work.setContentsMargins(0, 0, 0, 0)
        work.setSpacing(0)
        self.workflow_header = MediaWorkflowHeader(self.work_page)
        self.back_button = self.workflow_header.back_button
        self.save_button = self.workflow_header.save_button
        self.export_button = self.workflow_header.export_button
        self.workflow_header.backRequested.connect(self._back)
        self.workflow_header.saveRequested.connect(self.save_workspace)
        self.workflow_header.exportRequested.connect(self._export)
        self.workflow_header.stepChanged.connect(self._switch_workflow_page)
        work.addWidget(self.workflow_header)
        self.workflow_stack = QStackedWidget(self.work_page)
        work.addWidget(self.workflow_stack, 1)
        self._build_translation_page()
        self._build_proofreading_page()
        self.workflow_stack.addWidget(self.translation_page)
        self.workflow_stack.addWidget(self.proofreading_page)
        self.workflow_header.set_current_step("translation")
        self.stack.addWidget(self.work_page)

        self.status_label = CaptionLabel("", self)
        self.status_label.setWordWrap(True)
        self.status_label.setContentsMargins(24, 6, 24, 8)
        self.status_label.hide()
        outer.addWidget(self.status_label)
        self.stack.currentChanged.connect(self._refresh_status_visibility)
        self.workflow_stack.currentChanged.connect(self._refresh_status_visibility)
        self._refresh_metrics()

    def _build_translation_page(self):
        self.translation_page = QWidget(self.work_page)
        layout = QVBoxLayout(self.translation_page)
        layout.setContentsMargins(0, 12, 0, 20)
        layout.setSpacing(16)
        scroller = SingleDirectionScrollArea(self.translation_page, orient=Qt.Vertical)
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget(scroller)
        content.setObjectName("mediaTranslationContent")
        content.setStyleSheet("QWidget#mediaTranslationContent { background: transparent; }")
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 12, 24, 8)
        body.setSpacing(16)
        self.monitoring = MediaMonitoringPanel(content)
        body.addWidget(self.monitoring)

        self.workflow_selector = None
        if self.kind == "audio":
            options_card = SimpleCardWidget(content)
            options_card.setBorderRadius(12)
            options = QVBoxLayout(options_card)
            options.setContentsMargins(18, 14, 18, 14)
            options.setSpacing(12)
            self.workflow_selector = MediaWorkflowSelector(self.kind, options_card)
            options.addWidget(self.workflow_selector)
            body.addWidget(options_card)
        body.addStretch(1)
        scroller.setWidget(content)
        layout.addWidget(scroller, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(24, 0, 24, 0)
        bottom.setSpacing(12)
        bottom.addStretch(1)
        self.command_card = SimpleCardWidget(self.translation_page)
        self.command_card.setBorderRadius(18)
        commands = QHBoxLayout(self.command_card)
        commands.setContentsMargins(18, 16, 18, 16)
        commands.setSpacing(12)
        self.translate_button = PrimaryPushButton(FluentIcon.PLAY, self.tra("开始翻译"), self.command_card)
        self.translate_button.clicked.connect(self._run_primary)
        self.stop_button = TransparentPushButton(FluentIcon.CANCEL_MEDIUM, self.tra("停止"), self.command_card)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_operation)
        commands.addWidget(self.translate_button)
        commands.addWidget(self.stop_button)
        bottom.addWidget(self.command_card)

        self.language_card = SimpleCardWidget(self.translation_page)
        self.language_card.setBorderRadius(18)
        languages = QHBoxLayout(self.language_card)
        languages.setContentsMargins(18, 16, 18, 16)
        languages.setSpacing(8)
        self.source_combo, self.target_combo = ComboBox(self.language_card), ComboBox(self.language_card)
        for text, value in LanguageSettingsCard.SOURCE_LANGUAGE_PAIRS:
            self.source_combo.addItem(self.tra(text), userData=value)
        for text, value in LanguageSettingsCard.TARGET_LANGUAGE_PAIRS:
            self.target_combo.addItem(self.tra(text), userData=value)
        self.source_combo.setMinimumWidth(108)
        self.target_combo.setMinimumWidth(100)
        self.source_combo.setAccessibleName(self.tra("原文语言"))
        self.target_combo.setAccessibleName(self.tra("译文语言"))
        languages.addWidget(self.source_combo)
        arrow = IconWidget(FluentIcon.RIGHT_ARROW, self.language_card)
        arrow.setFixedSize(16, 16)
        languages.addWidget(arrow)
        languages.addWidget(self.target_combo)
        bottom.addWidget(self.language_card)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        if self.workflow_selector is not None:
            self.workflow_selector.selectionChanged.connect(self._refresh_metrics)
        if self.kind == "image":
            self.source_combo.currentIndexChanged.connect(self._generation_preferences_changed)
            self.target_combo.currentIndexChanged.connect(self._generation_preferences_changed)

    def _build_proofreading_page(self):
        self.proofreading_page = QWidget(self.work_page)
        layout = QVBoxLayout(self.proofreading_page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)
        splitter = QSplitter(Qt.Horizontal, self.proofreading_page)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { width: 8px; background: transparent; }")
        sidebar = QWidget(splitter)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(10)
        files_card = SimpleCardWidget(sidebar)
        files_card.setBorderRadius(12)
        files = QVBoxLayout(files_card)
        files.setContentsMargins(10, 14, 10, 12)
        files.setSpacing(10)
        title = StrongBodyLabel(self.tra("项目文件"), files_card)
        title.setAlignment(Qt.AlignCenter)
        files.addWidget(title)
        self.file_tree = TreeWidget(files_card)
        self.file_tree.setHeaderLabels([self.tra("文件")] if self.kind == "image"
                                       else [self.tra("文件"), self.tra("已译/条目")])
        self.file_tree.setHeaderHidden(True)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        if self.kind == "audio":
            self.file_tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
            self.file_tree.setColumnWidth(1, 60)
            self.file_tree.setColumnHidden(1, True)
        self.file_tree.setMinimumWidth(200)
        self.file_tree.setIndentation(16)
        self.file_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_tree.currentItemChanged.connect(self._file_selected)
        files.addWidget(self.file_tree, 1)
        self.file_search = SearchLineEdit(files_card)
        self.file_search.setPlaceholderText(self.tra("搜索文件"))
        self.file_search.textChanged.connect(self._filter_files)
        files.addWidget(self.file_search)
        side.addWidget(files_card, 1)

        editor_card = SimpleCardWidget(splitter)
        editor_card.setBorderRadius(12)
        editor = QVBoxLayout(editor_card)
        editor.setContentsMargins(16, 14, 16, 16)
        editor.setSpacing(12)
        if self.kind == "image":
            from Frontend.pages.media.image_preview import ImagePreview
            self.preview = ImagePreview(editor_card)
            self.preview_button = self.preview.refresh_button
            self.preview_button.clicked.connect(lambda: self.preview.refresh_translated())
        else:
            from Frontend.pages.media.audio_preview import AudioPreview
            self.preview = AudioPreview(editor_card)
            self.preview_button = TransparentPushButton(editor_card)
            self.preview_button.hide()
        if self.kind == "audio":
            self.preview.translationEdited.connect(self._translation_edited)
        editor.addWidget(self.preview, 1)
        splitter.addWidget(sidebar)
        splitter.addWidget(editor_card)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 1000])
        layout.addWidget(splitter, 1)

    def _switch_workflow_page(self, route):
        page = {"translation": self.translation_page, "proofreading": self.proofreading_page}.get(route)
        if page is None:
            return
        self.workflow_header.set_current_step(route)
        self.workflow_stack.setCurrentWidget(page)

    def _filter_files(self, text=None):
        query = self.file_search.text().strip().casefold()

        def visit(row):
            if row.data(0, Qt.UserRole):
                visible = not query or query in row.toolTip(0).casefold()
            else:
                visible = any([visit(row.child(index)) for index in range(row.childCount())])
            row.setHidden(not visible)
            return visible

        root = self.file_tree.invisibleRootItem()
        for index in range(root.childCount()):
            visit(root.child(index))

    def _image_mode(self):
        return "generation" if self.kind == "image" else "audio"

    def _record_generation_options(self):
        options = self.workspace["model"].setdefault("extra", {}).setdefault("image_generation_options", {})
        values = {"source_language": self.source_combo.currentData(), "target_language": self.target_combo.currentData()}
        for key, value in values.items():
            if options.get(key) != value:
                self._pending_generation_options[key] = value
                options[key] = value

    def _generation_preferences_changed(self, *unused):
        if self.kind != "image" or self._updating_image_options or self.busy or not self.workspace or self._image_mode() != "generation":
            return
        self._record_generation_options()
        if self._pending_generation_options:
            self._mark_options_dirty()

    def _mark_options_dirty(self):
        self._dirty = True
        self._run_state = ""
        self._stage_results.pop("generate", None)
        self._set_status(self.tra("流程设置已修改，正在自动保存…"))
        self._save_timer.start(800)
        self._refresh_tree_progress()
        self._file_selected(self._file_rows.get(self._selected_id) or self.file_tree.currentItem())

    def _selected_stages(self):
        return ["generate"] if self.kind == "image" else self.workflow_selector.selected_stages()

    def _run_primary(self):
        if self.busy or not self.workspace:
            return
        stages = self._selected_stages()
        if not stages:
            return
        self.run_stages(stages)

    def showEvent(self, event):
        super().showEvent(event)
        if self.stack.currentWidget() is self.start_page and not self.busy:
            QTimer.singleShot(0, self._load_history)

    def _choose_files(self):
        filter_ = "图片 (*.png *.jpg *.jpeg *.webp)" if self.kind == "image" else "音频 (*.mp3 *.wav *.flac *.m4a *.ogg *.aac *.opus)"
        paths, _ = QFileDialog.getOpenFileNames(self, self.tra("选择文件"), "", filter_)
        if paths:
            self.import_paths(paths)

    def _choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.tra("选择文件夹"))
        if path:
            self.import_paths([path])

    def _choose_zip(self):
        paths, _ = QFileDialog.getOpenFileNames(self, self.tra("选择 ZIP"), "", "ZIP (*.zip)")
        if paths:
            self.import_paths(paths)

    def _set_busy(self, value, *, cancellable=False):
        for widget in (self.drop_card, self.pick_files, self.pick_folder, self.pick_zip,
                       self.history_list, self.back_button,
                       self.save_button, self.translate_button,
                       self.preview_button, self.export_button, self.source_combo, self.target_combo):
            widget.setEnabled(not value)
        if self.kind == "audio":
            self.preview.set_editable(not value)
        if self.workflow_selector is not None:
            self.workflow_selector.set_busy(value)
        self.stop_button.setEnabled(value and cancellable)
        self.import_stop_button.setVisible(value and cancellable and self.stack.currentWidget() is self.start_page)
        self.import_stop_button.setEnabled(value and cancellable)

    def _start_worker(self, action, completed, label, *, cancellable=False):
        if self.busy:
            return False
        self._history_revision += 1
        self._save_timer.stop()
        worker = MediaWorker(action, self)
        self._worker = worker
        if cancellable:
            self._run_started = time.monotonic()
            self._run_elapsed = 0
            self._run_state = "准备中"
            self._active_stage = ""
            self._live_progress = {}
            self._metrics_timer.start()
        self._set_busy(True, cancellable=cancellable)
        self._set_status(label)
        self._refresh_metrics()
        worker.workspaceReady.connect(self._apply_workspace)
        worker.stageChanged.connect(self._stage_changed)
        worker.stageFinished.connect(self._stage_finished)
        worker.completed.connect(completed)
        worker.failed.connect(self._request_failed)
        worker.finished.connect(lambda: self._finish_worker(worker))
        worker.start()
        if cancellable:
            self._progress_timer.start()
        return True

    def _finish_worker(self, worker):
        if self._worker is worker:
            if self._run_started is not None:
                self._run_elapsed = time.monotonic() - self._run_started
                self._run_started = None
                self._metrics_timer.stop()
                self._live_progress = {}
            self._worker = None
            self._progress_timer.stop()
            self._set_busy(False)
            self._refresh_metrics()
            if self.isVisible() and self.stack.currentWidget() is self.start_page:
                QTimer.singleShot(0, self._load_history)
        worker.deleteLater()

    def _request_failed(self, message):
        if self._run_started is not None:
            self._run_state = "未完成"
            if self._active_stage:
                self._stage_results[self._active_stage] = {"status": "未完成", "detail": self._brief_message(message)}
        self._set_status(self.tra("操作未完成，未保存的修改仍保留在页面" if self._dirty
                                         else "请求未完成，可重新打开项目读取后端已保存的进度"))
        self.error_toast(self.tra("操作失败"), message)

    def _stage_changed(self, stage):
        if self._worker and self._worker.cancelled.is_set():
            return
        self._active_stage = stage
        self._live_progress = {}
        labels = {"recognize": "正在转录字幕…",
                  "translate": "正在翻译…",
                  "generate": "正在生成图片译文…", "export": "正在导出…"}
        self._stage_label = self.tra(labels.get(stage, "正在处理…"))
        self._run_state = {"recognize": "转录中",
                           "translate": "翻译中", "generate": "生成中",
                           "export": "导出中"}.get(stage, "处理中")
        self._set_status(self._stage_label)
        self._refresh_metrics()

    def _stage_finished(self, stage, result):
        status = result.get("status", "failed")
        report = result.get("report", {})
        if report.get("operation_errors") or not result.get("workspace", {}).get("persisted", True):
            status = "failed"
        if status != "success":
            detail = next((str(entry.get("message") or entry.get("reason"))
                           for key in ("operation_errors", "errors", "failed_items", "warnings")
                           for entry in report.get(key, []) if isinstance(entry, dict)
                           and (entry.get("message") or entry.get("reason"))), "")
            self._stage_results[stage] = {
                "status": self.tra({"partial": "部分完成", "cancelled": "已停止"}.get(status, "未完成")),
                "detail": self._brief_message(detail),
            }
        else:
            self._stage_results.pop(stage, None)
        self._refresh_metrics()

    def _progress_message(self, progress):
        def counts(current_key, total_key):
            current, total = progress.get(current_key), progress.get(total_key)
            if (type(current) in (int, float) and type(total) in (int, float)
                    and math.isfinite(current) and math.isfinite(total) and current >= 0 and total > 0):
                return int(current), int(total)
            return None

        for current_key, total_key in (("completed_chunks", "total_chunks"), ("line", "total_line"),
                                       ("current", "total"), ("completed_files", "total_files")):
            value = counts(current_key, total_key)
            if value:
                return f"{self._stage_label} {value[0]} / {value[1]}"
        return ""

    def _poll_operation(self):
        owner = self._worker
        if not owner or not owner.operation_id or owner.cancelled.is_set() or self._polling:
            return
        identifier = owner.operation_id
        self._polling = True
        worker = MediaWorker(lambda unused: self.client.job(identifier), self)
        def show(job):
            if self._worker is not owner or owner.operation_id != identifier or owner.cancelled.is_set():
                return
            if job.get("id") != identifier:
                return
            if job.get("state") == "queued":
                self._live_progress = {}
                self._run_state = "排队中"
                self._set_status(self.tra("正在排队，等待本类型的前序任务完成…"))
                self._refresh_metrics()
                return
            if job.get("state") != "running":
                return
            if self._run_state == "排队中":
                if owner.operation_kind == "import":
                    self._run_state = "读取中"
                else:
                    self._stage_changed(self._active_stage)
            progress = job.get("progress", {})
            if owner.operation_kind == "import":
                self._live_progress = progress
                message = self._progress_message(progress)
                if message:
                    self._set_status(message)
                return
            if (not self.workspace or progress.get("workspace_id") != self.workspace["workspace_id"]
                    or progress.get("stage") != self._active_stage):
                return
            self._live_progress = progress
            self._refresh_metrics()
            message = self._progress_message(progress)
            if message:
                self._set_status(message)
        def finished():
            self._polling = False
            self._finish_aux(worker)
        self._aux_workers.append(worker)
        worker.completed.connect(show)
        worker.finished.connect(finished)
        worker.start()

    def _load_history(self):
        if (self._disposed or self.busy or self._history_worker is not None
                or not self.isVisible() or self.stack.currentWidget() is not self.start_page):
            return
        revision = self._history_revision

        def fetch(worker):
            return self.client.history(self.kind), self.client.backend.load_config()

        worker = MediaWorker(fetch, self)
        self._history_worker = worker
        self._aux_workers.append(worker)

        def current():
            return (not self._disposed and self._history_worker is worker
                    and revision == self._history_revision and not self.busy
                    and self.isVisible() and self.stack.currentWidget() is self.start_page)

        def completed(result):
            if not current():
                return
            history, config = result
            rows = history if isinstance(history, list) else history.get("workspaces", history.get("items", []))
            self.start_page.set_history(rows)
            if not self.workspace:
                for combo, key in ((self.source_combo, "source_language"), (self.target_combo, "target_language")):
                    index = combo.findData(config.get(key))
                    if index >= 0:
                        combo.setCurrentIndex(index)

        def failed(message):
            if current():
                self.error_toast(self.tra("读取项目失败"), self._brief_message(message))

        def finished():
            if self._history_worker is worker:
                self._history_worker = None
            self._finish_aux(worker)
            if revision != self._history_revision:
                QTimer.singleShot(0, self._load_history)

        worker.completed.connect(completed)
        worker.failed.connect(failed)
        worker.finished.connect(finished)
        worker.start()

    def import_paths(self, paths):
        if paths:
            def action(worker):
                worker.operation_kind = "import"
                worker.operation_id = uuid4().hex
                if worker.cancelled.is_set():
                    return {"status": "cancelled"}
                return self.client.import_files(self.kind, list(paths), operation_id=worker.operation_id)

            def completed(workspace):
                if workspace.get("workspace_id") and workspace.get("model"):
                    self._loaded(workspace)
                elif workspace.get("status") == "cancelled":
                    self._set_status(self.tra("已停止导入。"))
                else:
                    self._show_report(workspace.get("status", "failed"), workspace.get("report", {}))

            self._stage_label = self.tra("正在读取图片…" if self.kind == "image" else "正在读取文件…")
            self._start_worker(action, completed, self._stage_label, cancellable=True)

    def load_workspace(self, identifier):
        self._start_worker(lambda worker: self.client.load(identifier), self._loaded, self.tra("正在恢复项目…"))

    def _delete_workspace(self, identifier, title):
        if self.busy:
            return
        content = self.tra("删除项目“{}”？").format(title)
        content += "\n" + self.tra("项目进度、预览和缓存将被删除，无法恢复。原始文件和已导出的文件会保留。")
        dialog = MessageBox(self.tra("删除项目"), content, self.window())
        dialog.yesButton.setText(self.tra("删除"))
        dialog.cancelButton.setText(self.tra("取消"))
        if not dialog.exec() or self.busy:
            return
        if self.workspace and self.workspace["workspace_id"] == identifier:
            # Release a cached audio file before Windows removes its workspace.
            self.preview.clear()

        def completed(result):
            if not isinstance(result, dict) or result.get("status") != "deleted" or result.get("workspace_id") != identifier:
                self._request_failed(self.tra("未能确认项目删除结果，请重新进入页面查看。"))
                return
            self.start_page.remove_history(identifier)
            if self.workspace and self.workspace["workspace_id"] == identifier:
                self.workspace = None
                self._dirty = False
                self._clear_pending_changes()
                self._selected_id = None
                self._file_rows.clear()
                self.file_tree.clear()
            self._set_status("")
            self.success_toast(self.tra("项目已删除"), title)

        self._start_worker(lambda worker: self.client.delete(identifier), completed, self.tra("正在删除项目…"))

    def _loaded(self, workspace):
        self._selected_id = None
        self._dirty = False
        self._run_elapsed = 0
        self._run_state = {"partial": "部分完成", "failed": "未完成", "cancelled": "已停止"}.get(workspace.get("status"), "")
        self._live_progress = {}
        self._stage_results.clear()
        self._planned_stages = []
        self.file_search.clear()
        self._apply_workspace(workspace)
        self._switch_workflow_page("translation")
        self.stack.setCurrentWidget(self.work_page)
        self._set_status("")
        if workspace.get("status") in ("partial", "failed", "cancelled") or not workspace.get("persisted", True):
            self._show_report(workspace.get("status", "success"), workspace.get("report", {}))

    def _apply_workspace(self, workspace):
        self.workspace = copy.deepcopy(workspace)
        self._live_progress = {}
        self._dirty = not workspace.get("persisted", True)
        self._clear_pending_changes()
        model = workspace["model"]
        self._updating_image_options = True
        try:
            languages = model.get("translation_context", {})
            if self.kind == "image":
                extra = model.get("extra", {})
                options = extra.get("image_generation_options", {})
                if self._image_mode() == "generation":
                    languages = {**languages, **{key: options[key] for key in ("source_language", "target_language") if key in options}}
            for combo, key in ((self.source_combo, "source_language"), (self.target_combo, "target_language")):
                value = languages.get(key)
                index = combo.findData(value) if value else -1
                if index >= 0:
                    combo.setCurrentIndex(index)
        finally:
            self._updating_image_options = False
        self._selecting = True
        self.file_tree.clear()
        self._file_rows = {}
        folders, first, selected = {}, None, None
        for path, file in model["files"].items():
            parts = PurePosixPath(path.replace("\\", "/")).parts
            parent = self.file_tree.invisibleRootItem()
            for index, part in enumerate(parts[:-1]):
                key = parts[:index+1]
                if key not in folders:
                    folders[key] = QTreeWidgetItem(parent, [part])
                parent = folders[key]
            columns = [parts[-1]] if self.kind == "image" else [parts[-1], self._file_progress(file)]
            row = QTreeWidgetItem(parent, columns)
            row.setData(0, Qt.UserRole, file["file_id"])
            self._file_rows[file["file_id"]] = row
            row.setToolTip(0, path)
            first = first or row
            if file["file_id"] == self._selected_id:
                selected = row
        self.file_tree.expandAll()
        self._selecting = False
        if selected or first:
            self.file_tree.setCurrentItem(selected or first)
        else:
            self._selected_id = None
            self.preview.clear()
        self._filter_files()
        self._refresh_metrics()

    def _file_progress(self, file):
        items = file.get("items", [])
        translated = sum(i.get("translation_status") in (1, 2) and bool(i.get("translated_text")) for i in items)
        return f"{translated}/{len(items)}" if items else self.tra("待读取原文")

    def _generation_status(self, file):
        asset = next((entry for entry in self.workspace.get("files", []) if entry["file_id"] == file["file_id"]), {})
        state = file.get("extra", {}).get("image_generation", {})
        status = asset.get("generation_status") or state.get("status")
        if status == "complete" and self._pending_generation_options:
            status = "stale"
        return status

    def _refresh_tree_progress(self):
        if not self.workspace:
            return
        for file in self.workspace["model"]["files"].values():
            row = self._file_rows.get(file["file_id"])
            if row and self.kind == "audio":
                row.setText(1, self._file_progress(file))
            if self.kind == "audio" and file["file_id"] == self._selected_id:
                items = file.get("items", [])
                translated = sum(item.get("translation_status") in (1, 2)
                                 and bool(str(item.get("translated_text") or "").strip()) for item in items)
                self.preview.set_translation_progress(translated, len(items))
        self._refresh_metrics()

    def _refresh_metrics(self, *unused):
        files = list((self.workspace or {}).get("model", {}).get("files", {}).values())
        generation = self.kind == "image" and self._image_mode() == "generation"
        completed = total = recognized = 0
        for file in files:
            extra = file.get("extra", {})
            items = file.get("items", [])
            recognition = extra.get("transcription", {}) if self.kind == "audio" else {}
            identified = recognition.get("status") == "complete"
            if self.kind == "audio" and not extra.get("transcription_checkpoint"):
                identified = identified or any(str(item.get("source_text", "")).strip() for item in items)
            recognized += bool(identified)
            if generation:
                state = self._generation_status(file)
                total += 1
                completed += state == "complete"
            else:
                candidates = [item for item in items if item.get("translation_status", 0) in (0, 1, 2)]
                total += len(candidates)
                completed += sum(item.get("translation_status") in (1, 2)
                                 and bool(str(item.get("translated_text") or "").strip()) for item in candidates)
        running = self._run_started is not None
        if running and self._active_stage == "translate":
            # Only media stage progress is admitted by _poll_operation.
            live_total, live_done = self._live_progress.get("total_line"), self._live_progress.get("line")
            if isinstance(live_total, (int, float)) and isinstance(live_done, (int, float)) and live_total > 0:
                total, completed = int(live_total), min(int(live_total), max(0, int(live_done)))
        stage = self._run_state
        if not stage:
            stage = "已完成" if total and completed == total else "待继续" if completed else "待开始"
        elapsed = time.monotonic() - self._run_started if running else self._run_elapsed
        self.monitoring.set_metrics(completed=completed, total=total, files=len(files), recognized=recognized,
                                    elapsed=elapsed, stage=self.tra(stage), status=self._status_message,
                                    running=running, generation=generation)
        self._refresh_workflow()

    def _refresh_workflow(self):
        mode = self._image_mode()
        generation = self.kind == "image" and mode == "generation"
        generation_states = ({file["file_id"]: self._generation_status(file)
                              for file in self.workspace["model"]["files"].values()}
                             if generation and self.workspace else None)
        states = workflow_states(self.workspace, self.kind, mode, generation_states)
        for key, value in self._stage_results.items():
            if key in states:
                states[key] = {**states[key], **value}
        running = self._run_started is not None
        if running:
            for key in self._planned_stages:
                if key in states and key not in self._stage_results and key != self._active_stage:
                    if self._planned_stages.index(key) > (self._planned_stages.index(self._active_stage)
                                                         if self._active_stage in self._planned_stages else -1):
                        states[key] = {**states[key], "status": self.tra("等待执行")}
            if self._active_stage in states:
                states[self._active_stage] = {**states[self._active_stage],
                                             "status": self.tra("停止中" if self._worker.cancelled.is_set()
                                                                else "排队中" if self._run_state == "排队中" else "处理中"),
                                             "active": True}
        if self.workflow_selector is not None:
            self.workflow_selector.set_states(states)

        selected = self._selected_stages()
        available = ["generate"] if generation else ["recognize", "translate"]
        labels = {"recognize": "开始转录", "translate": "开始翻译", "generate": "生成译图"}
        caption = ("请选择步骤" if not selected else labels[selected[0]] if len(selected) == 1
                   else "一键翻译" if selected == available else "执行所选步骤")
        self.translate_button.setText(self.tra(caption))
        hint = prerequisite_message(self.workspace, self.kind, mode, selected) if self.workspace else ""
        if not selected:
            hint = self.tra("请至少选择一个执行步骤")
        if self.workflow_selector is not None:
            self.workflow_selector.set_hint("" if running else self.tra(hint))
        self.translate_button.setEnabled(bool(self.workspace and selected) and not self.busy and not hint)

    def _file_selected(self, row, previous=None):
        if self._selecting or not row or not self.workspace:
            return
        identifier = row.data(0, Qt.UserRole)
        if not identifier:
            return
        self._selected_id = identifier
        file = next((f for f in self.workspace["model"]["files"].values() if f["file_id"] == identifier), None)
        asset = next((f for f in self.workspace.get("files", []) if f["file_id"] == identifier), {})
        source = self.client.asset_url(asset.get("source_url"))
        if self.kind == "image":
            pending_mode = bool(self._pending_generation_options)
            translated = "" if pending_mode else self.client.asset_url(asset.get("translated_url"))
            self.preview.set_file(file, source_url=source, translated_url=translated, headers=self.client.headers)
        else:
            self.preview.set_file(file, source_url=source, headers=self.client.headers)
        if self.kind == "audio":
            self.preview.set_editable(not self.busy)

    def _translation_edited(self, identifier, text):
        if self.kind != "audio" or self.busy or not self.workspace:
            return
        for file in self.workspace["model"]["files"].values():
            for item in file["items"]:
                if item["item_id"] == identifier:
                    item["translated_text"] = text
                    item["translation_status"] = 1 if text.strip() else 0
                    item["model"] = "manual" if text.strip() else ""
                    self._pending_edits[identifier] = {"source_text": item.get("source_text", ""),
                        "translated_text": text, "translation_status": item["translation_status"], "model": item["model"]}
                    self.workspace["model"]["stats_data"] = None
                    self._run_state = ""
                    for stage in ("translate", "export"):
                        self._stage_results.pop(stage, None)
                    self._dirty = True
                    self._set_status(self.tra("译文已修改，正在自动保存…"))
                    self._refresh_tree_progress()
                    self._save_timer.start(800)
                    return

    def _clear_pending_changes(self):
        self._pending_edits.clear()
        self._pending_generation_options.clear()

    def _prepare_checkpoint(self):
        """Merge actual local changes over the latest server checkpoint, never stale paid results."""
        identifier = self.workspace["workspace_id"]
        model = copy.deepcopy(self.workspace["model"])
        dirty = self._dirty
        unpersisted_result = not self.workspace.get("persisted", True)
        edits = copy.deepcopy(self._pending_edits)
        generation_patch = copy.deepcopy(self._pending_generation_options)

        def prepare():
            if not dirty:
                return self.client.load(identifier)
            if unpersisted_result or not (edits or generation_patch):
                return self.client.save(identifier, model)
            latest = self.client.load(identifier)
            merged = copy.deepcopy(latest["model"])
            items = {item["item_id"]: item for file in merged["files"].values() for item in file.get("items", [])}
            for item_id, change in edits.items():
                item = items.get(item_id)
                if item is None or item.get("source_text", "") != change["source_text"]:
                    raise ValueError("后端原文已变化，请重新打开项目后校对；本地修改仍保留在页面。")
                item.update({key: change[key] for key in ("translated_text", "translation_status", "model")})
            if edits:
                merged["stats_data"] = None
            if generation_patch:
                extra = merged.setdefault("extra", {})
                extra.setdefault("image_generation_options", {}).update(generation_patch)
            return self.client.save(identifier, merged)

        return prepare

    def save_workspace(self):
        if not self.workspace or self.busy:
            return
        prepare = self._prepare_checkpoint()
        dirty = self._dirty
        def done(workspace):
            if dirty and self.kind == "audio":
                # Avoid rebuilding the audio table editor after an ordinary save.
                self.workspace = copy.deepcopy(workspace)
                self._dirty = not workspace.get("persisted", True)
                self._clear_pending_changes()
            else:
                # A refresh may recover newer server checkpoints after a lost response.
                self._apply_workspace(workspace)
            self._set_status("")
            if not workspace.get("persisted", True):
                self._set_status(self.tra("结果已保留在页面，但未能写入项目文件，请重试保存"))
            self._refresh_metrics()
        self._start_worker(lambda worker: prepare(),
                           done, self.tra("正在保存项目…"))

    def _audio_recognition_config(self):
        try:
            current = self.client.backend.load_config()
            provider_id = current.get("active_transcription_platform")
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取转录接口配置，请检查后端连接后重试。"))
            return None
        return {"provider_id": provider_id} if isinstance(provider_id, str) and provider_id else {}

    def run_stages(self, stages, options=None):
        if not self.workspace or self.busy:
            return
        stages = list(stages)
        if not stages:
            return
        allowed = {"generate", "export"} if self.kind == "image" else {"recognize", "translate", "export"}
        if set(stages) - allowed:
            self.warning_toast(self.tra("不支持的步骤"), self.tra("图片翻译仅支持单步生成译图。" if self.kind == "image" else "请选择转录或翻译字幕步骤。"))
            return
        hint = prerequisite_message(self.workspace, self.kind, self._image_mode(), stages)
        if hint:
            if self.workflow_selector is not None:
                self.workflow_selector.set_hint(self.tra(hint))
            self.warning_toast(self.tra("缺少前置结果"), self.tra(hint))
            return
        workspace_id = self.workspace["workspace_id"]
        recognition_config = {"retranscribe": True}
        if self.kind == "audio" and "recognize" in stages:
            provider_config = self._audio_recognition_config()
            if provider_config is None:
                return
            recognition_config.update(provider_config)
        prepare = self._prepare_checkpoint()
        config = {"source_language": self.source_combo.currentData(), "target_language": self.target_combo.currentData(),
                  "retranslate": True}
        generation_config = {"source_language": self.source_combo.currentData(), "target_language": self.target_combo.currentData(),
                             "regenerate": True}
        export_options = copy.deepcopy(options or {})
        mode = self._image_mode()
        def action(worker):
            if "export" in stages:
                settings = read_media_export_settings(self.client.backend.load_config(), self.kind)
                for key, value in settings.items():
                    export_options.setdefault(key, value)
            # A lost HTTP response does not mean the paid call was lost. Load
            # server checkpoints unless the user actually changed local text.
            checkpoint = prepare()
            worker.workspaceReady.emit(checkpoint)
            results = []
            for stage in stages:
                if worker.cancelled.is_set():
                    break
                worker.stageChanged.emit(stage)
                missing = prerequisite_message(checkpoint, self.kind, mode, [stage])
                if missing:
                    raise ValueError(missing)
                worker.operation_id = uuid4().hex
                if worker.cancelled.is_set():
                    worker.operation_id = None
                    break
                result = self.client.run(workspace_id, stage, worker.operation_id,
                                         config=generation_config if stage == "generate" else config if stage == "translate" else recognition_config if stage == "recognize" else {},
                                         options=export_options if stage == "export" else {})
                worker.operation_id = None
                results.append({**result, "stage": stage})
                checkpoint = result["workspace"]
                worker.workspaceReady.emit(checkpoint)
                worker.stageFinished.emit(stage, result)
                if (result["status"] in ("failed", "cancelled") or result["report"].get("operation_errors")
                        or not checkpoint.get("persisted", True)):
                    break
            return {"results": results, "cancelled": worker.cancelled.is_set()}
        def done(payload):
            results = payload["results"]
            if payload["cancelled"]:
                self._run_state = "已停止"
                self._set_status(self.tra("已停止，当前结果已保存"))
            elif results:
                status = "failed" if any(r["status"] == "failed" or r["report"].get("operation_errors") or not r["workspace"].get("persisted", True) for r in results) else "cancelled" if any(r["status"] == "cancelled" for r in results) else "partial" if any(r["status"] == "partial" for r in results) else "success"
                self._run_state = {"success": "已完成", "partial": "部分完成", "failed": "未完成", "cancelled": "已停止"}[status]
                report = {key: [entry for result in results for entry in result["report"].get(key, [])]
                          for key in ("operation_errors", "errors", "failed_items", "warnings")}
                self._show_report(status, report)
                if results[-1]["stage"] == "export" and results[-1]["status"] == "success" and results[-1].get("files"):
                    count = len(results[-1]["files"])
                    self.success_toast(self.tra("导出完成"), f"{count} " + self.tra("个文件已导出至")
                                       + " " + str(export_options.get("output_dir", "")))
            if self.workspace and not self.workspace.get("persisted", True):
                self._set_status(self.tra("结果已保留在页面，但未能写入项目文件，请重试保存"))
        self._planned_stages = stages
        invalidated = set(stages)
        if "recognize" in stages:
            invalidated.update(("translate", "export"))
        elif "translate" in stages or "generate" in stages:
            invalidated.add("export")
        for stage in invalidated:
            self._stage_results.pop(stage, None)
        self._start_worker(action, done, self.tra("准备处理…"), cancellable=True)

    def stop_operation(self):
        if not self._worker:
            return
        self._worker.cancelled.set()
        self._run_state = "停止中"
        self._refresh_metrics()
        self.stop_button.setEnabled(False)
        self.import_stop_button.setEnabled(False)
        self._set_status(self.tra("正在停止，等待在途请求完成并保存结果…"))
        identifier = self._worker.operation_id
        if identifier:
            owner = self._worker
            def cancel(unused):
                # A click can race HTTP admission. Retry only this exact ID until
                # accepted or the owning call finishes; never stop a later stage.
                for attempt in range(30):
                    if owner.operation_id != identifier:
                        return
                    result = self.client.stop(identifier)
                    if result.get("status") != "idle":
                        return result
                    time.sleep(0.1)
            worker = MediaWorker(cancel, self)
            self._aux_workers.append(worker)
            worker.failed.connect(lambda message: self.warning_toast(self.tra("停止请求未完成"), message))
            worker.finished.connect(lambda: self._finish_aux(worker))
            worker.start()

    def _finish_aux(self, worker):
        if worker in self._aux_workers:
            self._aux_workers.remove(worker)
        worker.deleteLater()

    def _show_report(self, status, report):
        messages = {"failed": "处理未完成，已有进度已保留",
                    "partial": "部分完成，已有进度已保留",
                    "cancelled": "已停止，当前结果已保存"}
        issue = next((str(entry.get("message") or entry.get("reason"))
                      for key in ("operation_errors", "errors", "failed_items", "warnings")
                      for entry in report.get(key, []) if isinstance(entry, dict)
                      and (entry.get("message") or entry.get("reason"))), "")
        text = self.tra(messages.get(status, ""))
        self._set_status(text + ("；" + issue if text and issue else ""))
        if self.workspace and not self.workspace.get("persisted", True):
            self._set_status(self.tra("结果已保留在页面，但未能写入项目文件，请重试保存"))
        if issue:
            if status == "failed":
                self.error_toast(self.tra("处理未完成"), self._brief_message(issue))
            elif status != "cancelled":
                self.warning_toast(self.tra("处理提示"), self._brief_message(issue))

    def _export(self):
        hint = prerequisite_message(self.workspace, self.kind, self._image_mode(), ["export"])
        if hint:
            self.warning_toast(self.tra("缺少前置结果"), self.tra(hint))
            return
        directory = QFileDialog.getExistingDirectory(self, self.tra("选择导出目录"))
        if directory:
            self.run_stages(["export"], {"output_dir": directory})

    def _back(self):
        if self.busy:
            return
        if self._dirty:
            self.save_workspace()
            return
        self.prepare_to_leave()
        self._set_status("")
        self.stack.setCurrentWidget(self.start_page)
        self._load_history()

    def prepare_to_leave(self):
        stop = getattr(self.preview, "stop_playback", None)
        if stop:
            stop()
        return True

    def prepare_to_close(self):
        if self.busy or self._aux_workers:
            self.warning_toast(self.tra("正在处理媒体项目"), self.tra("请先停止并等待结果保存后再退出。"))
            return False
        if self._dirty:
            self.save_workspace()
            self.info_toast(self.tra("正在保存"), self.tra("译文保存完成后即可退出。"))
            return False
        return self.prepare_to_leave()

    def cleanup(self):
        self._disposed = True
        self._history_revision += 1
        self._save_timer.stop()
        self._progress_timer.stop()
        self._metrics_timer.stop()
        self.preview.clear()


class ImageTranslationPage(MediaWorkspacePage):
    def __init__(self, name="image_translation_page", parent=None, backend=None):
        super().__init__(name, "image", parent, backend)


class AudioTranslationPage(MediaWorkspacePage):
    def __init__(self, name="audio_translation_page", parent=None, backend=None):
        super().__init__(name, "audio", parent, backend)
