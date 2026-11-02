"""Asynchronous, independent source/translated image comparison for media pages."""
from PyQt5.QtCore import (
    QByteArray, QBuffer, QEvent, QIODevice, QObject, QRunnable, Qt,
    QThreadPool, QTimer, QUrl, pyqtSignal, pyqtSlot,
)
from PyQt5.QtGui import QImage, QImageReader, QPainter, QPixmap, QTransform
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt5.QtWidgets import (
    QAbstractItemView, QFrame, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QHeaderView, QSplitter, QStackedWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, CardWidget, PushButton, Slider, StrongBodyLabel, TableWidget

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(StrongBodyLabel(self.tra(title), self))
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
        self.dimensions.clear()
        self.label.clear()
        self.label.setText(self.tra(message))
        self.stack.setCurrentWidget(self.label)

    def set_image(self, image):
        self._pixmap = QPixmap.fromImage(image)
        self.dimensions.setText(f"{image.width()} × {image.height()}")
        self.scene.clear()
        self.scene.addPixmap(self._pixmap)
        self.scene.setSceneRect(0, 0, image.width(), image.height())
        self.stack.setCurrentWidget(self.scroll)

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
        self._editable = True
        self._generation_mode = False
        self._specified_text = False
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
        layout.setSpacing(10)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
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
        self.text_button = PushButton(self.tra("文字校对（0）"), self)
        self.text_button.setCheckable(True)
        self.text_button.toggled.connect(self._toggle_text)
        toolbar.addWidget(self.text_button)
        layout.addLayout(toolbar)
        self.image_splitter = QSplitter(Qt.Horizontal, self)
        self.image_splitter.setChildrenCollapsible(False)
        self.source_pane = _ImagePane("原图", self.image_splitter)
        self.translated_pane = _ImagePane("译图", self.image_splitter)
        self._panes = {"source": self.source_pane, "translated": self.translated_pane}
        for pane in self._panes.values():
            self.image_splitter.addWidget(pane)
            pane.scroll.viewport().installEventFilter(self)
        self.image_splitter.setSizes([600, 600])
        layout.addWidget(self.image_splitter, 1)
        self.text_panel = CardWidget(self)
        text_layout = QVBoxLayout(self.text_panel)
        text_layout.setContentsMargins(12, 8, 12, 8)
        self.edit_hint = CaptionLabel(self.tra("双击译文校对；重新生成预览后会更新图片。"), self.text_panel)
        self.edit_hint.setWordWrap(True)
        text_layout.addWidget(self.edit_hint)
        self.text_table = TableWidget(self.text_panel)
        self.text_table.setColumnCount(3)
        self.text_table.setHorizontalHeaderLabels([self.tra("序号"), self.tra("原文"), self.tra("译文")])
        self.text_table.verticalHeader().hide()
        self.text_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.text_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.text_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.text_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.text_table.setWordWrap(True)
        self.text_table.setSortingEnabled(False)
        self.text_table.itemChanged.connect(self._text_changed)
        text_layout.addWidget(self.text_table, 1)
        self.text_panel.setMinimumHeight(180)
        self.text_panel.setMaximumHeight(260)
        layout.addWidget(self.text_panel)
        self.text_panel.hide()
        self.set_editable(True)

    def set_file(self, file, source_url="", translated_url="", headers=None):
        """Select a wire CacheFile; each URL is the authenticated backend asset URL."""
        headers = dict(headers or {})
        file = file or {}
        file_id = file.get("file_id")
        same_file = bool(file_id) and file_id == self._file_id
        previous_source = self._urls["source"]
        same_headers = headers == self._headers
        self._file_id, self._headers = file_id, headers
        self._urls = {"source": str(source_url or ""), "translated": str(translated_url or "")}
        if not same_file:
            self._fit_mode = True
        self._set_text_items(file.get("items", []))
        if not same_file or not same_headers or previous_source != self._urls["source"] or self.source_pane._pixmap.isNull():
            self._load("source", self._urls["source"])
        # The file/URL may stay the same after an export. Always request fresh bytes.
        self._load("translated", self._urls["translated"])
        self._set_zoom_enabled(bool(file_id))

    def clear(self):
        self.set_file(None)

    def refresh_translated(self, url=None):
        if url is not None:
            self._urls["translated"] = str(url)
        self._load("translated", self._urls["translated"])

    def set_generation_mode(self, enabled, *, specified=False):
        self._generation_mode = bool(enabled)
        self._specified_text = bool(specified)
        show_editor = not self._generation_mode or self._specified_text
        self.text_button.setVisible(show_editor)
        if not show_editor:
            self.text_button.setChecked(False)
            self.text_panel.hide()
        self.edit_hint.setText(self.tra("修改译文后需重新生成图片；指定换字结果仍需对照原图复核。" if self._generation_mode
                                      else "双击译文校对；重新生成预览后会更新图片。"))
        if self.translated_pane._pixmap.isNull() and not self._urls["translated"]:
            self.translated_pane.show_message(self._empty_translation_message())

    def invalidate_translated(self):
        """Do not display an older specified-text render while its text is edited."""
        self._urls["translated"] = ""
        self._cancel("translated")
        self.translated_pane.show_message("译文已修改，请重新生成图片。")

    def _empty_translation_message(self):
        return ("生成图尚未就绪\n开始生成或继续下载后，会显示在这里。" if self._generation_mode else
                "译图尚未生成\n完成翻译并生成预览后，会显示在这里。")

    def set_editable(self, editable):
        self._editable = bool(editable)
        self.text_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
            if self._editable else QAbstractItemView.NoEditTriggers)

    def _set_zoom_enabled(self, enabled):
        for widget in (self.fit_button, self.actual_button, self.zoom_out_button,
                       self.zoom_slider, self.zoom_in_button):
            widget.setEnabled(enabled)

    def _set_text_items(self, items):
        self._loading_table = True
        self.text_table.blockSignals(True)
        try:
            self._translation_values = {}
            self.text_table.setRowCount(len(items))
            for row, entry in enumerate(items):
                item_id = str(entry.get("item_id", ""))
                source = str(entry.get("source_text") or "")
                translated = str(entry.get("translated_text") or "")
                self._translation_values[item_id] = translated
                for column, value in enumerate((str(row + 1), source, translated)):
                    cell = QTableWidgetItem(value)
                    cell.setData(Qt.UserRole, item_id)
                    if column != 2 or not item_id:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    self.text_table.setItem(row, column, cell)
                self.text_table.setRowHeight(row, 64)
        finally:
            self.text_table.blockSignals(False)
            self._loading_table = False
        self.text_button.setText(self.tra("文字校对") + f"（{len(items)}）")
        self.text_button.setEnabled(bool(items))
        if not items:
            self.text_button.setChecked(False)
            self.text_panel.hide()

    def _text_changed(self, item):
        if self._loading_table or not self._editable or item.column() != 2:
            return
        item_id = item.data(Qt.UserRole)
        if not item_id or item_id not in self._translation_values:
            return
        value = item.text()
        if self._translation_values[item_id] == value:
            return
        self._translation_values[item_id] = value
        self.translationEdited.emit(item_id, value)

    def _toggle_text(self, visible):
        self.text_panel.setVisible(visible)
        if self._fit_mode:
            self._fit_timer.start(0)

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
