"""Independent media workspaces over explicit, resumable backend interfaces."""
import copy
import threading
import time
from pathlib import PurePosixPath
from uuid import uuid4

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHeaderView, QHBoxLayout,
    QListWidgetItem, QProgressBar, QSplitter, QStackedWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, CheckBox, ComboBox,
    ListWidget, PlainTextEdit, PrimaryPushButton, PushButton, TitleLabel, TreeWidget)

from Frontend.core.config import ConfigMixin
from Frontend.components.toast import ToastMixin
from Frontend.services.media_client import MediaClient
from Frontend.pages.workspace.translation.language_settings_card import LanguageSettingsCard


class MediaWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    workspaceReady = pyqtSignal(object)
    stageChanged = pyqtSignal(str)

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.cancelled = threading.Event()
        self.operation_id = None

    def run(self):
        try:
            self.completed.emit(self.action(self))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.operation_id = None


class MediaDropCard(CardWidget):
    pathsDropped = pyqtSignal(list)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(190)
        layout = QVBoxLayout(self)
        title = TitleLabel("将图片、文件夹或 ZIP 拖到这里" if kind == "image" else "将音频、文件夹或 ZIP 拖到这里", self)
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        layout.addStretch()
        layout.addWidget(title)
        description = BodyLabel("PNG · JPG · WebP" if kind == "image" else "MP3 · WAV · FLAC · M4A · OGG", self)
        description.setAlignment(Qt.AlignCenter)
        layout.addWidget(description)
        layout.addStretch()

    def dragEnterEvent(self, event):
        if self.isEnabled() and event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if self.isEnabled() and paths:
            self.pathsDropped.emit(paths)
            event.acceptProposedAction()


class MediaWorkspacePage(QFrame, ConfigMixin, ToastMixin):
    def __init__(self, name, kind, parent=None, backend=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.kind = kind
        self.client = MediaClient(backend or self.config_backend())
        self.workspace = None
        self._worker = None
        self._aux_workers = []
        self._dirty = False
        self._pending_edits = {}
        self._pending_image_extra = {}
        self._pending_generation_options = {}
        self._updating_image_options = False
        self._file_rows = {}
        self._selected_id = None
        self._initialized = False
        self._selecting = False
        self._polling = False
        self._stage_label = ""
        self._build_ui()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_workspace)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(1200)
        self._progress_timer.timeout.connect(self._poll_operation)

    @property
    def busy(self):
        return self._worker is not None

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 16)
        self.title = TitleLabel(self.tra("图片翻译" if self.kind == "image" else "音频翻译"), self)
        outer.addWidget(self.title)
        self.description = CaptionLabel(self.tra("读取 → 文字识别 → 翻译 → 图片对照与导出" if self.kind == "image"
                                                 else "读取 → 转录 → 翻译 → 字幕试听与导出"), self)
        outer.addWidget(self.description)
        self.stack = QStackedWidget(self)
        outer.addWidget(self.stack, 1)
        self.start_page = QWidget(self)
        start = QVBoxLayout(self.start_page)
        start.setContentsMargins(0, 16, 0, 0)
        self.drop_card = MediaDropCard(self.kind, self.start_page)
        self.drop_card.pathsDropped.connect(self.import_paths)
        start.addWidget(self.drop_card)
        buttons = QHBoxLayout()
        self.pick_files = PrimaryPushButton(self.tra("选择图片" if self.kind == "image" else "选择音频"), self)
        self.pick_folder = PushButton(self.tra("选择文件夹"), self)
        self.pick_zip = PushButton(self.tra("选择 ZIP"), self)
        self.pick_files.clicked.connect(self._choose_files)
        self.pick_folder.clicked.connect(self._choose_folder)
        self.pick_zip.clicked.connect(self._choose_zip)
        buttons.addStretch()
        for button in (self.pick_files, self.pick_folder, self.pick_zip):
            buttons.addWidget(button)
        buttons.addStretch()
        start.addLayout(buttons)
        note = CaptionLabel(self.tra("读取不会调用在线识别服务。项目进度自动保存，可从最近项目继续。"), self)
        note.setAlignment(Qt.AlignCenter)
        start.addWidget(note)
        row = QHBoxLayout()
        row.addWidget(BodyLabel(self.tra("最近项目"), self))
        row.addStretch()
        self.refresh_history_button = PushButton(self.tra("刷新"), self)
        self.refresh_history_button.clicked.connect(self.refresh_history)
        row.addWidget(self.refresh_history_button)
        start.addLayout(row)
        self.history_list = ListWidget(self)
        self.history_list.itemDoubleClicked.connect(lambda item: self.load_workspace(item.data(Qt.UserRole)))
        self.history_list.setMinimumHeight(100)
        start.addWidget(self.history_list, 1)
        self.open_history = PushButton(self.tra("打开选中项目"), self)
        self.open_history.clicked.connect(self._open_history)
        start.addWidget(self.open_history, 0, Qt.AlignRight)
        self.stack.addWidget(self.start_page)

        self.work_page = QWidget(self)
        work = QVBoxLayout(self.work_page)
        work.setContentsMargins(0, 6, 0, 0)
        header = QHBoxLayout()
        self.back_button = PushButton(self.tra("返回项目列表"), self)
        self.back_button.clicked.connect(self._back)
        header.addWidget(self.back_button)
        self.project_label = BodyLabel(self)
        header.addWidget(self.project_label, 1)
        self.save_button = PushButton(self.tra("保存项目"), self)
        self.save_button.clicked.connect(self.save_workspace)
        header.addWidget(self.save_button)
        work.addLayout(header)
        if self.kind == "image":
            self._build_image_options(work)
        settings = QHBoxLayout()
        self.source_combo, self.target_combo = ComboBox(self), ComboBox(self)
        for text, value in LanguageSettingsCard.SOURCE_LANGUAGE_PAIRS:
            self.source_combo.addItem(self.tra(text), userData=value)
        for text, value in LanguageSettingsCard.TARGET_LANGUAGE_PAIRS:
            self.target_combo.addItem(self.tra(text), userData=value)
        settings.addWidget(BodyLabel(self.tra("原文"), self))
        settings.addWidget(self.source_combo)
        settings.addWidget(BodyLabel("→", self))
        settings.addWidget(self.target_combo)
        self.retranslate_check = CheckBox(self.tra("重译已完成内容"), self)
        settings.addWidget(self.retranslate_check)
        settings.addStretch()
        self.format_combo = ComboBox(self)
        self.format_combo.addItems(["PNG", "JPEG", "WEBP"] if self.kind == "image" else ["SRT", "VTT", "ASS", "LRC"])
        settings.addWidget(BodyLabel(self.tra("导出格式"), self))
        settings.addWidget(self.format_combo)
        self.subtitle_mode = ComboBox(self)
        for label, mode in (("双语字幕", "bilingual"), ("仅译文", "translated"), ("仅原文", "source")):
            self.subtitle_mode.addItem(self.tra(label), userData=mode)
        self.subtitle_mode.setVisible(self.kind == "audio")
        settings.addWidget(self.subtitle_mode)
        work.addLayout(settings)
        if self.kind == "image":
            self.source_combo.currentIndexChanged.connect(self._generation_preferences_changed)
            self.target_combo.currentIndexChanged.connect(self._generation_preferences_changed)
        actions = QHBoxLayout()
        self.recognize_button = PushButton(self.tra("识别原文" if self.kind == "image" else "转录字幕"), self)
        self.translate_button = PrimaryPushButton(self.tra("开始 / 继续翻译"), self)
        self.preview_button = PushButton(self.tra("更新译图预览"), self)
        self.preview_button.setVisible(self.kind == "image")
        self.stop_button = PushButton(self.tra("停止"), self)
        self.stop_button.setEnabled(False)
        self.export_button = PushButton(self.tra("导出结果"), self)
        self.recognize_button.clicked.connect(lambda: self.run_stages(["recognize"]))
        self.translate_button.clicked.connect(self._run_primary)
        self.preview_button.clicked.connect(lambda: self.run_stages(["preview"]))
        self.stop_button.clicked.connect(self.stop_operation)
        self.export_button.clicked.connect(self._export)
        for button in (self.recognize_button, self.translate_button, self.preview_button, self.stop_button):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(self.export_button)
        work.addLayout(actions)
        splitter = QSplitter(Qt.Horizontal, self)
        self.file_tree = TreeWidget(splitter)
        self.file_tree.setHeaderLabels([self.tra("文件"), self.tra("已译/条目")])
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_tree.setMinimumWidth(190)
        self.file_tree.setIndentation(16)
        self.file_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_tree.currentItemChanged.connect(self._file_selected)
        if self.kind == "image":
            from Frontend.pages.media.image_preview import ImagePreview
            self.preview = ImagePreview(splitter)
        else:
            from Frontend.pages.media.audio_preview import AudioPreview
            self.preview = AudioPreview(splitter)
        self.preview.translationEdited.connect(self._translation_edited)
        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280 if self.kind == "image" else 240, 1000])
        work.addWidget(splitter, 1)
        self.stack.addWidget(self.work_page)
        footer = QHBoxLayout()
        self.status_label = CaptionLabel(self.tra("等待导入文件"), self)
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.details_button = PushButton(self.tra("处理详情"), self)
        self.details_button.clicked.connect(lambda: self.details.setVisible(not self.details.isVisible()))
        footer.addWidget(self.details_button)
        outer.addLayout(footer)
        self.progress = QProgressBar(self)
        self.progress.setMaximumHeight(5)
        self.progress.setTextVisible(False)
        self.progress.hide()
        outer.addWidget(self.progress)
        self.details = PlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(125)
        self.details.hide()
        outer.addWidget(self.details)
        if self.kind == "image":
            self._update_image_controls()

    def _build_image_options(self, layout):
        row = QHBoxLayout()
        row.addWidget(BodyLabel(self.tra("翻译流程"), self))
        self.image_mode_combo = ComboBox(self)
        self.image_mode_combo.addItem(self.tra("识别、翻译与回填"), userData="ocr")
        self.image_mode_combo.addItem(self.tra("图像模型直接翻译"), userData="generation")
        self.image_mode_combo.setMinimumWidth(210)
        row.addWidget(self.image_mode_combo)
        self.generation_text_combo = ComboBox(self)
        self.generation_text_combo.addItem(self.tra("由图像模型翻译"), userData="direct")
        self.generation_text_combo.addItem(self.tra("按已有原文译文换字"), userData="specified")
        row.addWidget(self.generation_text_combo)
        row.addStretch()
        self.generation_prompt_button = PushButton(self.tra("补充要求"), self)
        self.generation_prompt_button.setCheckable(True)
        row.addWidget(self.generation_prompt_button)
        layout.addLayout(row)
        self.generation_help = CaptionLabel(self)
        self.generation_help.setWordWrap(True)
        layout.addWidget(self.generation_help)
        self.generation_prompt = PlainTextEdit(self)
        self.generation_prompt.setPlaceholderText(self.tra("可补充排版或画面保留要求；留空使用接口默认要求。最终结果仍需对照原图复核。"))
        self.generation_prompt.setMaximumHeight(76)
        layout.addWidget(self.generation_prompt)
        self.image_mode_combo.currentIndexChanged.connect(self._image_mode_changed)
        self.generation_text_combo.currentIndexChanged.connect(self._generation_preferences_changed)
        self.generation_prompt.textChanged.connect(self._generation_preferences_changed)
        self.generation_prompt_button.toggled.connect(self._update_image_controls)

    def _image_mode(self):
        return self.image_mode_combo.currentData() if self.kind == "image" else "ocr"

    def _update_image_controls(self, *unused):
        if self.kind != "image":
            return
        generation = self._image_mode() == "generation"
        specified = self.generation_text_combo.currentData() == "specified"
        self.generation_text_combo.setVisible(generation)
        self.generation_prompt_button.setVisible(generation)
        self.generation_prompt.setVisible(generation and self.generation_prompt_button.isChecked())
        self.generation_help.setVisible(generation)
        if specified:
            self.generation_help.setText(self.tra(
                "按中间模型已有原文和译文换字，不会自动识别文字。请先在识别翻译流程中准备并校对条目；生成结果仍需人工复核。"))
        else:
            self.generation_help.setText(self.tra(
                "图像模型直接生成整页译图，不会自动产生逐条原文和译文。请对照原图检查错字、漏字和画面变化。"))
        self.recognize_button.setVisible(not generation)
        self.preview_button.setVisible(not generation)
        self.translate_button.setText(self.tra("开始 / 继续生成" if generation else "开始 / 继续翻译"))
        self.retranslate_check.setText(self.tra("重新生成全部页面" if generation else "重译已完成内容"))
        self.description.setText(self.tra("读取 → 图像模型生成 → 原图对照与导出" if generation
                                         else "读取 → 文字识别 → 翻译 → 图片对照与导出"))
        self.file_tree.setHeaderLabels([self.tra("文件"), self.tra("生成状态" if generation else "已译/条目")])
        update_preview = getattr(self.preview, "set_generation_mode", None)
        if update_preview:
            update_preview(generation, specified=specified)

    def _image_mode_changed(self, *unused):
        if self._updating_image_options or self.busy or not self.workspace:
            return
        mode = self._image_mode()
        extra = self.workspace["model"].setdefault("extra", {})
        extra["image_translation_mode"] = mode
        self._pending_image_extra["image_translation_mode"] = mode
        self.retranslate_check.setChecked(False)
        self._updating_image_options = True
        try:
            options = extra.get("image_generation_options", {})
            values = options if mode == "generation" else self.workspace["model"].get("translation_context", {})
            for combo, key in ((self.source_combo, "source_language"), (self.target_combo, "target_language")):
                index = combo.findData(values.get(key))
                if index >= 0:
                    combo.setCurrentIndex(index)
        finally:
            self._updating_image_options = False
        self._update_image_controls()
        if mode == "generation":
            self._record_generation_options()
        self._mark_options_dirty()

    def _record_generation_options(self):
        options = self.workspace["model"].setdefault("extra", {}).setdefault("image_generation_options", {})
        values = {"text_mode": self.generation_text_combo.currentData(),
                  "prompt": self.generation_prompt.toPlainText(),
                  "source_language": self.source_combo.currentData(), "target_language": self.target_combo.currentData()}
        for key, value in values.items():
            if options.get(key) != value:
                self._pending_generation_options[key] = value
                options[key] = value

    def _generation_preferences_changed(self, *unused):
        if self.kind != "image" or self._updating_image_options or self.busy or not self.workspace or self._image_mode() != "generation":
            return
        self._record_generation_options()
        self._update_image_controls()
        if self._pending_generation_options:
            self._mark_options_dirty()

    def _mark_options_dirty(self):
        self._dirty = True
        self.status_label.setText(self.tra("流程设置已修改，正在自动保存…"))
        self._save_timer.start(800)
        self._refresh_tree_progress()
        self._file_selected(self._file_rows.get(self._selected_id) or self.file_tree.currentItem())

    def _run_primary(self):
        if self.kind == "image" and self._image_mode() == "generation":
            self.run_stages(["generate"])
        else:
            self.run_stages(["recognize", "translate"] + (["preview"] if self.kind == "image" else []))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            QTimer.singleShot(0, self.refresh_history)

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

    def _open_history(self):
        item = self.history_list.currentItem()
        if item:
            self.load_workspace(item.data(Qt.UserRole))

    def _set_busy(self, value, *, cancellable=False):
        for widget in (self.drop_card, self.pick_files, self.pick_folder, self.pick_zip,
                       self.refresh_history_button, self.open_history, self.history_list, self.back_button,
                       self.save_button, self.recognize_button, self.translate_button,
                       self.preview_button, self.export_button, self.source_combo, self.target_combo,
                       self.retranslate_check, self.format_combo, self.subtitle_mode):
            widget.setEnabled(not value)
        self.preview.set_editable(not value)
        if self.kind == "image":
            for widget in (self.image_mode_combo, self.generation_text_combo,
                           self.generation_prompt_button, self.generation_prompt):
                widget.setEnabled(not value)
        self.stop_button.setEnabled(value and cancellable)
        self.progress.setRange(0, 0 if value else 100)
        self.progress.setVisible(value)

    def _start_worker(self, action, completed, label, *, cancellable=False):
        if self.busy:
            return False
        self._save_timer.stop()
        worker = MediaWorker(action, self)
        self._worker = worker
        self._set_busy(True, cancellable=cancellable)
        self.status_label.setText(label)
        worker.workspaceReady.connect(self._apply_workspace)
        worker.stageChanged.connect(self._stage_changed)
        worker.completed.connect(completed)
        worker.failed.connect(self._request_failed)
        worker.finished.connect(lambda: self._finish_worker(worker))
        worker.start()
        if cancellable:
            self._progress_timer.start()
        return True

    def _finish_worker(self, worker):
        if self._worker is worker:
            self._worker = None
            self._progress_timer.stop()
            self._set_busy(False)
        worker.deleteLater()

    def _request_failed(self, message):
        self.status_label.setText(self.tra("操作未完成，未保存的修改仍保留在页面" if self._dirty
                                         else "请求未完成，可重新打开项目读取后端已保存的进度"))
        self.details.appendPlainText(message)
        self.details.show()
        self.error_toast(self.tra("操作失败"), message)

    def _stage_changed(self, text):
        self._stage_label = text
        self.status_label.setText(text)
        self.progress.setRange(0, 0)

    def _poll_operation(self):
        owner = self._worker
        if not owner or not owner.operation_id or owner.cancelled.is_set() or self._polling:
            return
        identifier = owner.operation_id
        self._polling = True
        worker = MediaWorker(lambda unused: self.client.backend.request("GET", "/api/status", timeout=3), self)
        def show(status):
            if self._worker is not owner or owner.operation_id != identifier or owner.cancelled.is_set():
                return
            if (status.get("operation") or {}).get("id") != identifier:
                return
            progress = status.get("pipeline_progress", {})
            if self.kind == "image" and self._image_mode() == "generation":
                row = self._file_rows.get(progress.get("file_id"))
                if row:
                    row.setText(1, self.tra(self._generation_status_label(progress.get("status", "request_in_flight"))))
            for current_key, total_key in (("completed_chunks", "total_chunks"), ("line", "total_line"),
                                           ("current", "total"), ("completed_files", "total_files")):
                current, total = progress.get(current_key), progress.get(total_key)
                if isinstance(current, (int, float)) and isinstance(total, (int, float)) and total > 0:
                    self.progress.setRange(0, int(total))
                    self.progress.setValue(int(current))
                    self.status_label.setText(f"{self._stage_label} {int(current)} / {int(total)}")
                    break
        def finished():
            self._polling = False
            self._finish_aux(worker)
        self._aux_workers.append(worker)
        worker.completed.connect(show)
        worker.finished.connect(finished)
        worker.start()

    def refresh_history(self):
        def fetch(worker):
            return self.client.history(self.kind), self.client.backend.load_config()
        def completed(result):
            history, config = result
            rows = history if isinstance(history, list) else history.get("workspaces", history.get("items", []))
            self.history_list.clear()
            for row in rows:
                item = QListWidgetItem(str(row.get("project_name") or row.get("name") or "未命名项目"))
                item.setData(Qt.UserRole, row["workspace_id"])
                item.setToolTip(str(row.get("updated_at", "")))
                self.history_list.addItem(item)
            if not self.workspace:
                for combo, key in ((self.source_combo, "source_language"), (self.target_combo, "target_language")):
                    index = combo.findData(config.get(key))
                    if index >= 0:
                        combo.setCurrentIndex(index)
            self.status_label.setText(self.tra("选择文件或打开最近项目") if rows else self.tra("等待导入文件"))
        self._start_worker(fetch, completed, self.tra("读取最近项目…"))

    def import_paths(self, paths):
        if paths:
            self._start_worker(lambda worker: self.client.import_files(self.kind, list(paths)),
                               self._loaded, self.tra("正在读取文件…"))

    def load_workspace(self, identifier):
        self._start_worker(lambda worker: self.client.load(identifier), self._loaded, self.tra("正在恢复项目…"))

    def _loaded(self, workspace):
        self._selected_id = None
        self._dirty = False
        self._apply_workspace(workspace)
        self.stack.setCurrentWidget(self.work_page)
        self._show_report(workspace.get("status", "success"), workspace.get("report", {}))

    def _apply_workspace(self, workspace):
        self.workspace = copy.deepcopy(workspace)
        self._dirty = not workspace.get("persisted", True)
        self._clear_pending_changes()
        model = workspace["model"]
        self.project_label.setText(f"{model.get('project_name', '')} · {len(model['files'])} 个文件")
        self._updating_image_options = True
        try:
            languages = model.get("translation_context", {})
            if self.kind == "image":
                extra = model.get("extra", {})
                mode = extra.get("image_translation_mode", "ocr")
                self.image_mode_combo.setCurrentIndex(max(0, self.image_mode_combo.findData(mode)))
                options = extra.get("image_generation_options", {})
                self.generation_text_combo.setCurrentIndex(max(0, self.generation_text_combo.findData(options.get("text_mode", "direct"))))
                self.generation_prompt.setPlainText(str(options.get("prompt", "")))
                if self._image_mode() == "generation":
                    languages = {**languages, **{key: options[key] for key in ("source_language", "target_language") if key in options}}
            for combo, key in ((self.source_combo, "source_language"), (self.target_combo, "target_language")):
                value = languages.get(key)
                index = combo.findData(value) if value else -1
                if index >= 0:
                    combo.setCurrentIndex(index)
        finally:
            self._updating_image_options = False
        self._update_image_controls()
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
            row = QTreeWidgetItem(parent, [parts[-1], self._file_progress(file)])
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

    @staticmethod
    def _generation_status_label(status):
        return {"prepared": "待生成", "request_in_flight": "生成中", "unknown": "结果待确认",
                "generated_pending_download": "待下载", "download_failed": "下载失败",
                "complete": "已生成", "failed": "失败", "stale": "需重新生成",
                "unavailable": "译图待恢复"}.get(status, "待生成")

    def _file_progress(self, file):
        if self.kind == "image" and self._image_mode() == "generation":
            asset = next((entry for entry in self.workspace.get("files", []) if entry["file_id"] == file["file_id"]), {})
            state = file.get("extra", {}).get("image_generation", {})
            status = asset.get("generation_status") or state.get("status")
            edits_affect_file = any(item.get("item_id") in self._pending_edits for item in file.get("items", []))
            if status == "complete" and (self._pending_generation_options or
                    (self.generation_text_combo.currentData() == "specified" and edits_affect_file)):
                status = "stale"
            return self.tra(self._generation_status_label(status))
        items = file.get("items", [])
        translated = sum(i.get("translation_status") in (1, 2) and bool(i.get("translated_text")) for i in items)
        return f"{translated}/{len(items)}" if items else self.tra("待读取原文")

    def _refresh_tree_progress(self):
        if not self.workspace:
            return
        for file in self.workspace["model"]["files"].values():
            row = self._file_rows.get(file["file_id"])
            if row:
                row.setText(1, self._file_progress(file))

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
            pending_mode = bool(self._pending_image_extra) or bool(self._pending_generation_options)
            pending_text = self._image_mode() == "generation" and self.generation_text_combo.currentData() == "specified" and any(
                item.get("item_id") in self._pending_edits for item in (file or {}).get("items", []))
            translated = "" if pending_mode or pending_text else self.client.asset_url(asset.get("translated_url"))
            self.preview.set_file(file, source_url=source, translated_url=translated, headers=self.client.headers)
        else:
            self.preview.set_file(file, source_url=source, headers=self.client.headers)
        self.preview.set_editable(not self.busy)

    def _translation_edited(self, identifier, text):
        if self.busy or not self.workspace:
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
                    self._dirty = True
                    self.status_label.setText(self.tra("译文已修改，保存后请重新生成图片" if self.kind == "image" and self._image_mode() == "generation"
                                                     else "译文已修改，正在自动保存…"))
                    self._refresh_tree_progress()
                    if self.kind == "image" and self._image_mode() == "generation" and self.generation_text_combo.currentData() == "specified" and file["file_id"] == self._selected_id:
                        invalidate = getattr(self.preview, "invalidate_translated", None)
                        if invalidate:
                            invalidate()
                    self._save_timer.start(800)
                    return

    def _clear_pending_changes(self):
        self._pending_edits.clear()
        self._pending_image_extra.clear()
        self._pending_generation_options.clear()

    def _prepare_checkpoint(self):
        """Merge actual local changes over the latest server checkpoint, never stale paid results."""
        identifier = self.workspace["workspace_id"]
        model = copy.deepcopy(self.workspace["model"])
        dirty = self._dirty
        unpersisted_result = not self.workspace.get("persisted", True)
        edits = copy.deepcopy(self._pending_edits)
        extra_patch = copy.deepcopy(self._pending_image_extra)
        generation_patch = copy.deepcopy(self._pending_generation_options)

        def prepare():
            if not dirty:
                return self.client.load(identifier)
            if unpersisted_result or not (edits or extra_patch or generation_patch):
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
            if extra_patch or generation_patch:
                extra = merged.setdefault("extra", {})
                extra.update(extra_patch)
                if generation_patch:
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
            self.status_label.setText(self.tra("项目已保存") + (self.tra("；修改译文后请更新译图预览") if self.kind == "image" else ""))
            if self.kind == "image" and self._image_mode() == "generation":
                self.status_label.setText(self.tra("项目已保存；文字或生成要求有变化时请重新生成译图"))
            if not workspace.get("persisted", True):
                self.status_label.setText(self.tra("结果已保留在页面，但未能写入项目文件，请查看详情并重试保存"))
        self._start_worker(lambda worker: prepare(),
                           done, self.tra("正在保存项目…"))

    def run_stages(self, stages, options=None):
        if not self.workspace or self.busy:
            return
        generation = self.kind == "image" and self._image_mode() == "generation"
        if generation and any(stage in ("recognize", "translate", "preview") for stage in stages):
            self.warning_toast(self.tra("请切换流程"), self.tra("当前使用图像生成流程；识别和逐条翻译请切回“识别、翻译与回填”。"))
            return
        if not generation and "generate" in stages:
            self.warning_toast(self.tra("请切换流程"), self.tra("请先选择“图像模型直接翻译”。"))
            return
        workspace_id = self.workspace["workspace_id"]
        prepare = self._prepare_checkpoint()
        config = {"source_language": self.source_combo.currentData(), "target_language": self.target_combo.currentData(),
                  "retranslate": self.retranslate_check.isChecked()}
        generation_config = {"source_language": self.source_combo.currentData(), "target_language": self.target_combo.currentData(),
                             "regenerate": self.retranslate_check.isChecked()}
        if generation:
            generation_config["text_mode"] = self.generation_text_combo.currentData()
            prompt = self.generation_prompt.toPlainText()
            if prompt.strip():
                generation_config["prompt"] = prompt
        export_options = copy.deepcopy(options or {})
        if self.kind == "image":
            export_options["mode"] = self._image_mode()
        labels = {"recognize": self.tra("正在识别原文…" if self.kind == "image" else "正在转录字幕…"),
                  "translate": self.tra("正在翻译…"), "preview": self.tra("正在生成译图预览…"),
                  "generate": self.tra("正在生成图片译文…"), "export": self.tra("正在导出…")}
        def action(worker):
            # A lost HTTP response does not mean the paid call was lost. Load
            # server checkpoints unless the user actually changed local text.
            checkpoint = prepare()
            worker.workspaceReady.emit(checkpoint)
            if generation and "generate" in stages and generation_config["text_mode"] == "specified":
                pairs = [item for file in checkpoint["model"]["files"].values() for item in file.get("items", [])
                         if str(item.get("source_text", "")).strip() and str(item.get("translated_text", "")).strip()]
                if not pairs:
                    raise ValueError("缺少原文译文：请先切回识别翻译流程准备并校对条目，或通过接口传入替换清单；此模式不会自动调用OCR。")
            results = []
            for stage in stages:
                if worker.cancelled.is_set():
                    break
                worker.operation_id = uuid4().hex
                if worker.cancelled.is_set():
                    worker.operation_id = None
                    break
                worker.stageChanged.emit(labels[stage])
                result = self.client.run(workspace_id, stage, worker.operation_id,
                                         config=generation_config if stage == "generate" else config if stage == "translate" else {},
                                         options=export_options if stage == "export" else {})
                worker.operation_id = None
                results.append(result)
                worker.workspaceReady.emit(result["workspace"])
                if result["status"] in ("failed", "cancelled") or result["report"].get("operation_errors"):
                    break
            return {"results": results, "cancelled": worker.cancelled.is_set()}
        def done(payload):
            results = payload["results"]
            self.details.clear()
            for result in results:
                self._append_details(result["report"])
            if payload["cancelled"]:
                self.status_label.setText(self.tra("已停止，进度已保存，可继续处理"))
            elif results:
                status = "failed" if any(r["status"] == "failed" or r["report"].get("operation_errors") for r in results) else "cancelled" if any(r["status"] == "cancelled" for r in results) else "partial" if any(r["status"] == "partial" for r in results) else "success"
                self._show_report(status, results[-1]["report"], append=False)
                if stages == ["export"] and results[-1].get("files"):
                    self.details.appendPlainText("\n".join(f["path"] for f in results[-1]["files"]))
                    self.details.show()
            if self.workspace and not self.workspace.get("persisted", True):
                self.status_label.setText(self.tra("结果已保留在页面，但未能写入项目文件，请查看详情并重试保存"))
            self.retranslate_check.setChecked(False)
        self._start_worker(action, done, self.tra("准备处理…"), cancellable=True)

    def stop_operation(self):
        if not self._worker:
            return
        self._worker.cancelled.set()
        self.stop_button.setEnabled(False)
        self.status_label.setText(self.tra("正在停止，等待在途请求完成并保存结果…"))
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
            worker.failed.connect(lambda message: self.details.appendPlainText(message))
            worker.finished.connect(lambda: self._finish_aux(worker))
            worker.start()

    def _finish_aux(self, worker):
        if worker in self._aux_workers:
            self._aux_workers.remove(worker)
        worker.deleteLater()

    def _append_details(self, report):
        for key in ("operation_errors", "errors", "failed_items", "warnings"):
            for entry in report.get(key, [])[:100]:
                self.details.appendPlainText(f"{entry.get('path', '')} {entry.get('message', entry.get('reason', ''))}".strip())

    def _show_report(self, status, report, *, append=True):
        if append:
            self.details.clear()
            self._append_details(report)
        messages = {"success": "处理完成，项目已保存", "partial": "部分完成，部分内容需要复核；已保存可用结果",
                    "failed": "处理未完成，请查看详情；已有进度已保留", "cancelled": "已停止，进度已保存，可继续处理"}
        self.status_label.setText(self.tra(messages.get(status, "项目已读取")))
        if self.workspace and not self.workspace.get("persisted", True):
            self.status_label.setText(self.tra("结果已保留在页面，但未能写入项目文件，请查看详情并重试保存"))
        if status in ("failed", "partial"):
            self.details.show()
        else:
            self.details.hide()

    def _export(self):
        directory = QFileDialog.getExistingDirectory(self, self.tra("选择导出目录"))
        if directory:
            options = {"output_dir": directory, "format": self.format_combo.currentText().lower()}
            if self.kind == "audio":
                options["mode"] = self.subtitle_mode.currentData()
            self.run_stages(["export"], options)

    def _back(self):
        if self.busy:
            return
        if self._dirty:
            self.save_workspace()
            return
        self.prepare_to_leave()
        self.details.hide()
        self.stack.setCurrentWidget(self.start_page)
        self.refresh_history()

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
        self._save_timer.stop()
        self._progress_timer.stop()
        self.preview.clear()


class ImageTranslationPage(MediaWorkspacePage):
    def __init__(self, name="image_translation_page", parent=None, backend=None):
        super().__init__(name, "image", parent, backend)


class AudioTranslationPage(MediaWorkspacePage):
    def __init__(self, name="audio_translation_page", parent=None, backend=None):
        super().__init__(name, "audio", parent, backend)
