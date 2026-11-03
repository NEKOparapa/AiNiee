"""Asynchronous, independent source/translated image comparison for media pages."""
import math

from PyQt5.QtCore import (
    QByteArray, QBuffer, QEvent, QIODevice, QObject, QPointF, QRunnable, Qt,
    QThreadPool, QTimer, QUrl, pyqtSignal, pyqtSlot,
)
from PyQt5.QtGui import QColor, QImage, QImageReader, QPainter, QPen, QPixmap, QPolygonF, QTransform
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt5.QtWidgets import (
    QAbstractItemView, QFrame, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QHeaderView, QSplitter, QStackedWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    BodyLabel, CaptionLabel, CardWidget, CheckBox, ComboBox, FluentIcon, PushButton, Slider,
    StrongBodyLabel, TabBar, TableWidget, TransparentToolButton,
)

from Frontend.core.config import ConfigMixin


MAX_PREVIEW_BYTES = 64 * 1024 * 1024
MAX_PREVIEW_PIXELS = 64 * 1024 * 1024


class _DecodeSignals(QObject):
    finished = pyqtSignal(str, int, object, str)


class _DecodeImage(QRunnable):
    """Keep decoding large pictures off the GUI thread; QPixmap stays on it."""
    def __init__(self, side, ticket, data):
        super().__init__()
        self.side, self.ticket, self.data = side, ticket, data
        self.signals = _DecodeSignals()

    def run(self):
        image, message = QImage(), ""
        try:
            buffer = QBuffer()
            buffer.setData(QByteArray(self.data))
            buffer.open(QIODevice.ReadOnly)
            reader = QImageReader(buffer)
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid() and size.width() * size.height() > MAX_PREVIEW_PIXELS:
                message = "图片尺寸过大，无法在预览中加载。"
            else:
                image = reader.read()
                if image.isNull():
                    message = "无法解码预览图片，请检查文件格式。"
            buffer.close()
        except Exception:
            message = "无法解码预览图片，请检查文件格式。"
        self.signals.finished.emit(self.side, self.ticket, image, message)


class _ImagePane(CardWidget, ConfigMixin):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._regions = []
        self._region_items = []
        self._show_regions = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        self.title_label = StrongBodyLabel(self.tra(title), self)
        heading.addWidget(self.title_label)
        heading.addStretch(1)
        self.dimensions = CaptionLabel("", self)
        heading.addWidget(self.dimensions)
        layout.addLayout(heading)
        self.stack = QStackedWidget(self)
        self.scene = QGraphicsScene(self)
        self.scroll = QGraphicsView(self.scene, self.stack)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scroll.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.scroll.setStyleSheet("QGraphicsView { background: transparent; border: none; }")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.label = BodyLabel(self.stack)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setMinimumSize(160, 120)
        self.stack.addWidget(self.label)
        self.stack.addWidget(self.scroll)
        layout.addWidget(self.stack, 1)
        self.setMinimumWidth(180)

    def show_message(self, message):
        self._pixmap = QPixmap()
        self.scene.clear()
        self._region_items = []
        self.dimensions.clear()
        self.label.clear()
        self.label.setText(self.tra(message))
        self.stack.setCurrentWidget(self.label)

    def set_image(self, image):
        self._pixmap = QPixmap.fromImage(image)
        self.dimensions.setText(f"{image.width()} × {image.height()}")
        self.scene.clear()
        self._region_items = []
        self.scene.addPixmap(self._pixmap)
        self.scene.setSceneRect(0, 0, image.width(), image.height())
        self._draw_regions()
        self.stack.setCurrentWidget(self.scroll)

    def set_regions(self, regions, visible):
        self._regions, self._show_regions = regions, bool(visible)
        self._draw_regions()

    def _draw_regions(self):
        for item in self._region_items:
            self.scene.removeItem(item)
        self._region_items = []
        if not self._show_regions or self._pixmap.isNull():
            return
        pen = QPen(QColor("#e47700"), 1.5)
        pen.setCosmetic(True)
        for region in self._regions:
            polygon = region.get("polygon") if isinstance(region, dict) else None
            if not isinstance(polygon, list) or len(polygon) < 3:
                continue
            points = []
            for point in polygon:
                if (not isinstance(point, (list, tuple)) or len(point) != 2
                        or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)):
                    break
                points.append(QPointF(max(0, min(self._pixmap.width(), point[0])),
                                      max(0, min(self._pixmap.height(), point[1]))))
            if len(points) == len(polygon):
                self._region_items.append(self.scene.addPolygon(QPolygonF(points), pen))

    def scale_to(self, factor):
        if self._pixmap.isNull():
            return
        # GraphicsView clips to the viewport instead of allocating a 300% raster.
        self.scroll.setTransform(QTransform.fromScale(factor, factor))


class ImagePreview(QWidget, ConfigMixin):
    """Model data is read-only here; edits are emitted with stable item IDs."""
    translationEdited = pyqtSignal(str, str)
    previewError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._network = QNetworkAccessManager(self)
        self._tickets = {"source": 0, "translated": 0}
        self._replies = {}
        self._decoders = {}
        self._urls = {"source": "", "translated": ""}
        self._headers = {}
        self._file_id = None
        self._file_items = []
        self._render_state = {}
        self._render_warnings = []
        self._preview_current = False
        self._detection = {}
        self._repaired_url = ""
        self._translated_url = ""
        self._render_rows = {}
        self._unfilled_rows = []
        self._editable = True
        self._generation_mode = False
        self._loading_table = False
        self._translation_values = {}
        self._fit_mode = True
        self._zoom = 100
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._apply_fit)
        self._build_ui()
        self.clear()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.tab_bar = TabBar(self)
        self.tab_bar.setTabMaximumWidth(160)
        self.tab_bar.setTabShadowEnabled(False)
        self.tab_bar.setScrollable(True)
        self.tab_bar.setAddButtonVisible(False)
        self.tab_bar.setTabsClosable(False)
        self.tab_bar.setMovable(False)
        self.tab_bar.addTab("image_preview", self.tra("图片预览"))
        self.tab_bar.addTab("ocr_information", self.tra("OCR 信息"))
        header.addWidget(self.tab_bar, 1)
        self.refresh_button = TransparentToolButton(FluentIcon.SYNC, self)
        self.refresh_button.setFixedSize(32, 32)
        self.refresh_button.setToolTip(self.tra("修复图片并重新渲染译文"))
        self.refresh_button.setAccessibleName(self.tra("修复图片并重新渲染译文"))
        header.addWidget(self.refresh_button)
        layout.addLayout(header)
        detection_layout = QHBoxLayout()
        detection_layout.setContentsMargins(0, 8, 0, 0)
        self.detection_status_label = CaptionLabel(self)
        self.detection_status_label.setWordWrap(True)
        self.detection_status_label.setTextFormat(Qt.PlainText)
        detection_layout.addWidget(self.detection_status_label, 1)
        self.detection_overlay = CheckBox(self.tra("显示文字检测框"), self)
        self.detection_overlay.setChecked(True)
        self.detection_overlay.toggled.connect(self._update_detection_overlay)
        detection_layout.addWidget(self.detection_overlay)
        layout.addLayout(detection_layout)
        self.render_summary = QWidget(self)
        summary_layout = QHBoxLayout(self.render_summary)
        summary_layout.setContentsMargins(0, 8, 0, 0)
        self.render_status_label = CaptionLabel(self.render_summary)
        self.render_status_label.setTextFormat(Qt.PlainText)
        self.render_status_label.setWordWrap(True)
        summary_layout.addWidget(self.render_status_label, 1)
        self.render_details_button = PushButton(self.tra("查看未回填条目"), self.render_summary)
        self.render_details_button.clicked.connect(self._show_unfilled_items)
        summary_layout.addWidget(self.render_details_button)
        layout.addWidget(self.render_summary)
        self.stacked_widget = QStackedWidget(self)
        layout.addWidget(self.stacked_widget, 1)
        self.preview_page = QWidget(self.stacked_widget)
        preview_layout = QVBoxLayout(self.preview_page)
        preview_layout.setContentsMargins(0, 10, 0, 0)
        preview_layout.setSpacing(10)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.result_combo = ComboBox(self)
        self.result_combo.addItem(self.tra("译图"), userData="translated")
        self.result_combo.addItem(self.tra("修复图"), userData="repaired")
        self.result_combo.setAccessibleName(self.tra("查看译图或修复图"))
        self.result_combo.currentIndexChanged.connect(self._result_changed)
        toolbar.addWidget(self.result_combo)
        self.fit_button = PushButton(self.tra("适应窗口"), self)
        self.fit_button.clicked.connect(self.fit_to_window)
        self.actual_button = PushButton(self.tra("原尺寸"), self)
        self.actual_button.clicked.connect(lambda: self.set_zoom(100))
        self.zoom_out_button = PushButton("−", self)
        self.zoom_out_button.setFixedWidth(34)
        self.zoom_out_button.setAccessibleName(self.tra("缩小图片"))
        self.zoom_out_button.clicked.connect(lambda: self.set_zoom(max(10, self._zoom - 10)))
        self.zoom_in_button = PushButton("+", self)
        self.zoom_in_button.setFixedWidth(34)
        self.zoom_in_button.setAccessibleName(self.tra("放大图片"))
        self.zoom_in_button.clicked.connect(lambda: self.set_zoom(min(300, self._zoom + 10)))
        self.zoom_slider = Slider(Qt.Horizontal, self)
        self.zoom_slider.setRange(10, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(140)
        self.zoom_slider.setAccessibleName(self.tra("图片缩放比例"))
        self.zoom_slider.valueChanged.connect(self.set_zoom)
        self.zoom_label = CaptionLabel("100%", self)
        self.zoom_label.setMinimumWidth(50)
        for widget in (self.fit_button, self.actual_button, self.zoom_out_button,
                       self.zoom_slider, self.zoom_in_button, self.zoom_label):
            toolbar.addWidget(widget)
        toolbar.addStretch(1)
        preview_layout.addLayout(toolbar)
        self.image_splitter = QSplitter(Qt.Horizontal, self.preview_page)
        self.image_splitter.setChildrenCollapsible(False)
        self.image_splitter.setHandleWidth(8)
        self.image_splitter.setStyleSheet(
            "QSplitter::handle { width: 8px; background: transparent; }")
        self.source_pane = _ImagePane("原图", self.image_splitter)
        self.translated_pane = _ImagePane("译图", self.image_splitter)
        self._panes = {"source": self.source_pane, "translated": self.translated_pane}
        for pane in self._panes.values():
            self.image_splitter.addWidget(pane)
            pane.scroll.viewport().installEventFilter(self)
        self.image_splitter.setSizes([600, 600])
        preview_layout.addWidget(self.image_splitter, 1)
        self.stacked_widget.addWidget(self.preview_page)
        self.text_panel = CardWidget(self.stacked_widget)
        text_layout = QVBoxLayout(self.text_panel)
        text_layout.setContentsMargins(12, 8, 12, 8)
        self.translation_progress_label = CaptionLabel(self.text_panel)
        self.translation_progress_label.setTextColor("#707070", "#b0b0b0")
        self.translation_progress_label.setAlignment(Qt.AlignRight)
        text_layout.addWidget(self.translation_progress_label)
        self.ocr_stack = QStackedWidget(self.text_panel)
        self.ocr_empty = BodyLabel(self.tra("暂无 OCR 信息"), self.ocr_stack)
        self.ocr_empty.setAlignment(Qt.AlignCenter)
        self.ocr_empty.setTextColor("#777777", "#b0b0b0")
        self.ocr_stack.addWidget(self.ocr_empty)
        self.text_table = TableWidget(self.ocr_stack)
        self.text_table.setColumnCount(4)
        self.text_table.setHorizontalHeaderLabels([
            self.tra("序号"), self.tra("原文"), self.tra("译文"), self.tra("回填状态")])
        self.text_table.verticalHeader().hide()
        self.text_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.text_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.text_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.text_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.text_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.text_table.setWordWrap(True)
        self.text_table.setSortingEnabled(False)
        self.text_table.itemChanged.connect(self._text_changed)
        self.text_table.currentCellChanged.connect(self._show_render_detail)
        self.ocr_stack.addWidget(self.text_table)
        text_layout.addWidget(self.ocr_stack, 1)
        self.render_detail_label = CaptionLabel(self.text_panel)
        self.render_detail_label.setTextFormat(Qt.PlainText)
        self.render_detail_label.setWordWrap(True)
        self.render_detail_label.hide()
        text_layout.addWidget(self.render_detail_label)
        self.text_panel.setMinimumHeight(180)
        self.stacked_widget.addWidget(self.text_panel)
        self.tab_bar.currentChanged.connect(self._switch_tab)
        self.stacked_widget.currentChanged.connect(self.tab_bar.setCurrentIndex)
        self.set_editable(True)

    def _switch_tab(self, index):
        self.stacked_widget.setCurrentIndex(index)
        if index == 0 and self._fit_mode:
            self._fit_timer.start(0)

    def set_file(self, file, source_url="", translated_url="", headers=None, render_warnings=None, repaired_url=""):
        """Select a wire CacheFile; each URL is the authenticated backend asset URL."""
        headers = dict(headers or {})
        file = file or {}
        file_id = file.get("file_id")
        same_file = bool(file_id) and file_id == self._file_id
        previous_source = self._urls["source"]
        same_headers = headers == self._headers
        self._file_id, self._headers = file_id, headers
        self._file_items = [dict(entry) for entry in (file.get("items") or [])
                            if isinstance(entry, dict)]
        self._render_state = (file.get("extra") or {}).get("image_pipeline", {}).get("render", {})
        self._render_warnings = self._render_state.get("warnings", render_warnings or [])
        self._preview_current = bool(translated_url)
        detection = (file.get("extra") or {}).get("text_detection", {})
        self._detection = detection if isinstance(detection, dict) else {}
        self._repaired_url, self._translated_url = str(repaired_url or ""), str(translated_url or "")
        self._urls = {"source": str(source_url or ""), "translated": self._selected_result_url()}
        if not same_file:
            self._fit_mode = True
        self._sync_ocr_information()
        self._sync_detection_information(file)
        completed = sum(entry.get("translation_status") in (1, 2)
                        and bool(str(entry.get("translated_text") or "").strip())
                        for entry in self._file_items)
        self.set_translation_progress(completed, len(self._file_items))
        if not same_file or not same_headers or previous_source != self._urls["source"] or self.source_pane._pixmap.isNull():
            self._load("source", self._urls["source"])
        # The file/URL may stay the same after an export. Always request fresh bytes.
        self._load("translated", self._urls["translated"])
        self._set_zoom_enabled(bool(file_id))

    def clear(self):
        self.set_file(None)

    def refresh_translated(self, url=None):
        if url is not None:
            self._translated_url = str(url)
            self._urls["translated"] = self._selected_result_url()
        self._load("translated", self._urls["translated"])

    def _selected_result_url(self):
        return self._repaired_url if self.result_combo.currentData() == "repaired" and not self._generation_mode else self._translated_url

    def _result_changed(self, *unused):
        repaired = self.result_combo.currentData() == "repaired" and not self._generation_mode
        self.translated_pane.title_label.setText(self.tra("修复图" if repaired else "译图"))
        self._urls["translated"] = self._selected_result_url()
        self._load("translated", self._urls["translated"])

    def _sync_detection_information(self, file=None):
        file = file or {}
        source_hash = (file.get("source_ref") or {}).get("sha256")
        current = self._detection.get("status") == "complete" and self._detection.get("source_sha256") == source_hash and bool(source_hash)
        self._detection_current = current
        visible = bool(self._file_id) and not self._generation_mode
        self.detection_status_label.setVisible(visible)
        self.detection_overlay.setVisible(visible)
        self.detection_overlay.setEnabled(current and bool(self._detection.get("regions")))
        if current:
            count = len(self._detection.get("regions", []))
            text = self.tra("已检测 {0} 个文字区域；OCR 识别使用这些位置。").format(count) if count else self.tra("文本检测完成，未发现文字区域。")
        elif self._detection.get("status") in ("failed", "cancelled"):
            error = self._detection.get("error") or {}
            text = self.tra("文本检测未完成，可在翻译流程中重新检测。") + str(error.get("message") or "")
        else:
            text = self.tra("尚无文本检测结果，请在翻译流程中执行文本检测。")
        self.detection_status_label.setText(text)
        self._update_detection_overlay()

    def _update_detection_overlay(self, *unused):
        if hasattr(self, "source_pane"):
            self.source_pane.set_regions(self._detection.get("regions", []),
                getattr(self, "_detection_current", False) and self.detection_overlay.isChecked() and not self._generation_mode)

    def set_generation_mode(self, enabled):
        mode_changed = self._generation_mode != bool(enabled)
        self._generation_mode = bool(enabled)
        self.result_combo.setVisible(not self._generation_mode)
        self.detection_status_label.setVisible(bool(self._file_id) and not self._generation_mode)
        self.detection_overlay.setVisible(bool(self._file_id) and not self._generation_mode)
        self._update_detection_overlay()
        if mode_changed:
            self._sync_ocr_information()
            self._result_changed()
        if self.translated_pane._pixmap.isNull() and not self._urls["translated"]:
            self.translated_pane.show_message(self._empty_translation_message())

    def _empty_translation_message(self):
        if self.result_combo.currentData() == "repaired" and not self._generation_mode:
            return "修复图尚未生成\n完成图像修复后，可在这里检查消字结果。"
        return ("生成图尚未就绪\n生成完成后，会显示在这里。" if self._generation_mode else
                "译图尚未生成\n完成图像修复和文字渲染后，会显示在这里。")

    def set_editable(self, editable):
        self._editable = bool(editable)
        self.text_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
            if self._editable else QAbstractItemView.NoEditTriggers)

    def set_translation_progress(self, completed, total):
        """Refresh the current file count without changing table cells or focus."""
        total = max(0, int(total))
        completed = max(0, min(int(completed), total))
        self.translation_progress_label.setText(
            self.tra("已译 {0} / {1} 条").format(completed, total))
        self.translation_progress_label.setVisible(
            bool(self._file_items) and not self._generation_mode)

    def _set_zoom_enabled(self, enabled):
        for widget in (self.fit_button, self.actual_button, self.zoom_out_button,
                       self.zoom_slider, self.zoom_in_button):
            widget.setEnabled(enabled)

    def _sync_ocr_information(self):
        # Direct image generation has no per-item OCR information.
        items = [] if self._generation_mode else self._file_items
        self._sync_render_information()
        self._set_text_items(items)
        self.ocr_stack.setCurrentWidget(self.text_table if items else self.ocr_empty)
        self.translation_progress_label.setVisible(bool(items))

    def _set_text_items(self, items):
        self._loading_table = True
        self.text_table.blockSignals(True)
        try:
            self._translation_values = {}
            self.text_table.setRowCount(len(items))
            for row, entry in enumerate(items):
                item_id = str(entry.get("item_id", ""))
                source = str(entry.get("source_text") or "")
                if not source and (entry.get("extra") or {}).get("ocr", {}).get("status") == "pending":
                    source = self.tra("待 OCR 识别")
                translated = str(entry.get("translated_text") or "")
                self._translation_values[item_id] = translated
                status, reason = self._render_rows.get(item_id, ("", ""))
                for column, value in enumerate((str(row + 1), source, translated, status)):
                    cell = QTableWidgetItem(value)
                    cell.setData(Qt.UserRole, item_id)
                    cell.setToolTip(reason)
                    if column != 2 or not item_id:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    self.text_table.setItem(row, column, cell)
                self.text_table.setRowHeight(row, 64)
        finally:
            self.text_table.blockSignals(False)
            self._loading_table = False
        self._show_render_detail(self.text_table.currentRow())

    def _sync_render_information(self):
        """Describe actual rendered placements, independently of translation completion."""
        self._render_rows = {}
        self._unfilled_rows = []
        visible = (bool(self._render_state) or any(str(item.get("translated_text") or "").strip() for item in self._file_items)) and not self._generation_mode
        self.render_summary.setVisible(visible)
        if not visible:
            self.render_detail_label.hide()
            return
        placed = {entry.get("item_id") for entry in self._render_state.get("placements", [])}
        preserved = {entry.get("item_id"): entry.get("reason")
                     for entry in self._render_state.get("preserved", [])}
        warnings = {}
        for entry in self._render_warnings:
            if isinstance(entry, dict) and entry.get("item_id"):
                warnings.setdefault(entry["item_id"], []).append(str(entry.get("message") or entry.get("code") or ""))
        for row, item in enumerate(self._file_items):
            identifier = str(item.get("item_id", ""))
            reason = "\n".join(warnings.get(identifier, []))
            if not self._preview_current:
                status = self.tra("待回填")
                reason = self.tra("当前译文尚未生成译图，请点击右上角刷新按钮。")
            elif identifier in placed:
                status = self.tra("已回填，需复核" if reason else "已回填")
            elif identifier in preserved:
                excluded = preserved[identifier] == "excluded"
                status = self.tra("已排除" if excluded else "原文一致")
                reason = self.tra("本条已排除翻译，保留原图文字。" if excluded else
                                  "译文与原文一致，保留原图文字。")
            else:
                status = self.tra("未回填")
                reason = reason or self.tra("本条未写入译图，仍保留原图文字。")
                self._unfilled_rows.append(row)
            self._render_rows[identifier] = (status, reason)
        if self._preview_current:
            count = sum(str(item.get("item_id", "")) in placed for item in self._file_items)
            total = len(self._file_items)
            message = self.tra("本图已回填 {0} / {1} 条；{2} 条保留原文。").format(count, total, total - count)
            if self._unfilled_rows:
                message += self.tra("未回填原因可在 OCR 信息中逐条查看。")
        else:
            message = self.tra("当前译文尚未回填，请点击右上角刷新按钮生成译图。")
        self.render_status_label.setText(message)
        self.render_details_button.setVisible(bool(self._unfilled_rows))

    def _show_unfilled_items(self):
        self.stacked_widget.setCurrentIndex(1)
        if self._unfilled_rows:
            row = self._unfilled_rows[0]
            self.text_table.setCurrentCell(row, 3)
            self.text_table.scrollToItem(self.text_table.item(row, 3))

    def _show_render_detail(self, row, *unused):
        cell = self.text_table.item(row, 3) if row >= 0 else None
        reason = cell.toolTip() if cell else ""
        self.render_detail_label.setText(reason)
        self.render_detail_label.setVisible(bool(reason) and not self._generation_mode)

    def _text_changed(self, item):
        if self._loading_table or not self._editable or self._generation_mode or item.column() != 2:
            return
        item_id = item.data(Qt.UserRole)
        if not item_id or item_id not in self._translation_values:
            return
        value = item.text()
        if self._translation_values[item_id] == value:
            return
        self._translation_values[item_id] = value
        for entry in self._file_items:
            if str(entry.get("item_id", "")) == item_id:
                entry["translated_text"] = value
                break
        self._preview_current = False
        self._sync_render_information()
        # Preserve the active editor while invalidating all displayed render states.
        self.text_table.blockSignals(True)
        try:
            for row in range(self.text_table.rowCount()):
                cell = self.text_table.item(row, 3)
                status, reason = self._render_rows.get(str(cell.data(Qt.UserRole)), ("", ""))
                cell.setText(status)
                for column in range(self.text_table.columnCount()):
                    self.text_table.item(row, column).setToolTip(reason)
        finally:
            self.text_table.blockSignals(False)
        self._show_render_detail(self.text_table.currentRow())
        self.translationEdited.emit(item_id, value)

    def _cancel(self, side):
        self._tickets[side] += 1
        reply = self._replies.pop(side, None)
        if reply is not None:
            reply.abort()

    def _load(self, side, url):
        self._cancel(side)
        pane = self._panes[side]
        if not url:
            pane.show_message("请选择图片文件" if side == "source" else self._empty_translation_message())
            return
        pane.show_message("正在加载原图…" if side == "source" else "正在加载译图…")
        ticket = self._tickets[side]
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.AlwaysNetwork)
        request.setAttribute(QNetworkRequest.CacheSaveControlAttribute, False)
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.ManualRedirectPolicy)
        request.setRawHeader(b"Cache-Control", b"no-cache")
        for name, value in self._headers.items():
            request.setRawHeader(str(name).encode("utf-8"), str(value).encode("utf-8"))
        reply = self._network.get(request)
        self._replies[side] = reply
        reply.downloadProgress.connect(lambda received, total, s=side, t=ticket, r=reply:
                                       self._download_progress(s, t, r, received, total))
        reply.finished.connect(lambda s=side, t=ticket, r=reply: self._read_reply(s, t, r))

    def _download_progress(self, side, ticket, reply, received, total):
        if ticket != self._tickets[side]:
            return
        if received > MAX_PREVIEW_BYTES or total > MAX_PREVIEW_BYTES:
            self._cancel(side)
            self._show_error(side, "图片文件过大，无法在预览中加载。")

    def _read_reply(self, side, ticket, reply):
        try:
            if ticket != self._tickets[side]:
                return
            self._replies.pop(side, None)
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NoError or (status is not None and not 200 <= int(status) < 300):
                if status == 404 and side == "translated":
                    self._panes[side].show_message(self._empty_translation_message())
                else:
                    self._show_error(side, "预览访问被拒绝，请重新连接后端。" if status in (401, 403)
                                     else "图片预览加载失败，请检查后端连接或重新生成预览。")
                return
            data = bytes(reply.readAll())
            if len(data) > MAX_PREVIEW_BYTES:
                self._show_error(side, "图片文件过大，无法在预览中加载。")
                return
            decoder = _DecodeImage(side, ticket, data)
            self._decoders[side, ticket] = decoder
            decoder.signals.finished.connect(self._decoded)
            QThreadPool.globalInstance().start(decoder)
        finally:
            reply.deleteLater()

    @pyqtSlot(str, int, object, str)
    def _decoded(self, side, ticket, image, error):
        self._decoders.pop((side, ticket), None)
        if ticket != self._tickets[side]:
            return
        if error or image.isNull():
            self._show_error(side, error or "无法解码预览图片，请检查文件格式。")
            return
        self._panes[side].set_image(image)
        if self._fit_mode:
            self._apply_fit()
        else:
            self._apply_scale(self._zoom / 100)

    def _show_error(self, side, text):
        self._panes[side].show_message(text)
        self.previewError.emit(self.tra(text))

    def fit_to_window(self):
        self._fit_mode = True
        self._apply_fit()

    def _apply_fit(self):
        if not self._fit_mode:
            return
        factors = []
        for pane in self._panes.values():
            if not pane._pixmap.isNull():
                viewport = pane.scroll.viewport().size()
                factors.append(min(max(1, viewport.width() - 4) / pane._pixmap.width(),
                                   max(1, viewport.height() - 4) / pane._pixmap.height(), 1.0))
        if factors:
            factor = min(factors)
            self._zoom = max(1, round(factor * 100))
            self._apply_scale(factor)

    def set_zoom(self, percent):
        self._fit_mode = False
        self._zoom = min(300, max(10, int(percent)))
        self._apply_scale(self._zoom / 100)

    def _apply_scale(self, factor):
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(self._zoom)
        self.zoom_slider.blockSignals(False)
        self.zoom_label.setText(f"{self._zoom}%")
        for pane in self._panes.values():
            pane.scale_to(factor)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize and self._fit_mode:
            self._fit_timer.start(0)
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self._fit_timer.stop()
        for side in self._panes:
            self._cancel(side)
        super().closeEvent(event)
