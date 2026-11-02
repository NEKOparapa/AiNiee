"""Shared, compact import and recent-project surface for media workspaces."""

import copy

from PyQt5.QtCore import QDateTime, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QListWidgetItem, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    CaptionLabel, CardWidget, FluentIcon, IconWidget, ListItemDelegate, ListWidget, PrimaryPushButton,
    PushButton, SimpleCardWidget, StrongBodyLabel, SubtitleLabel, TransparentToolButton,
    isDarkTheme, qconfig, themeColor,
)

from Frontend.core.config import ConfigMixin


class MediaDropCard(SimpleCardWidget, ConfigMixin):
    pathsDropped = pyqtSignal(list)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.setBorderRadius(16)
        self.setAcceptDrops(True)
        self.setMinimumHeight(248)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._dragging = False
        self._title = self.tra("将图片拖到这里" if kind == "image" else "将音频拖到这里")
        icon = FluentIcon.PHOTO if kind == "image" else FluentIcon.MUSIC

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addStretch(1)
        self.icon_tile = QFrame(self)
        self.icon_tile.setObjectName("mediaImportIconTile")
        self.icon_tile.setFixedSize(56, 56)
        icon_layout = QVBoxLayout(self.icon_tile)
        icon_layout.setContentsMargins(14, 14, 14, 14)
        self.icon_widget = IconWidget(icon, self.icon_tile)
        self.icon_widget.setFixedSize(28, 28)
        icon_layout.addWidget(self.icon_widget)
        layout.addWidget(self.icon_tile, 0, Qt.AlignHCenter)

        self.title_label = SubtitleLabel(self._title, self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        formats = "PNG · JPG · WebP" if kind == "image" else "MP3 · WAV · FLAC · M4A · OGG"
        caption = CaptionLabel(formats, self)
        caption.setAlignment(Qt.AlignCenter)
        caption.setTextColor("#707070", "#a6a6a6")
        layout.addWidget(caption)
        layout.addSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        self.pick_files = PrimaryPushButton(icon, self.tra("选择图片" if kind == "image" else "选择音频"), self)
        self.pick_folder = PushButton(FluentIcon.FOLDER, self.tra("文件夹"), self)
        self.pick_zip = PushButton(FluentIcon.ZIP_FOLDER, "ZIP", self)
        for button in (self.pick_files, self.pick_folder, self.pick_zip):
            button.setMinimumHeight(36)
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self._refresh_accent()
        qconfig.themeColorChanged.connect(self._refresh_accent)

    def _refresh_accent(self, *_):
        color = themeColor()
        self.icon_tile.setStyleSheet(
            "QFrame#mediaImportIconTile {"
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 0.09);"
            "border: none; border-radius: 16px; }"
        )
        self.update()

    def _accepts_drop(self, event):
        urls = event.mimeData().urls()
        return self.isEnabled() and bool(urls) and all(url.isLocalFile() for url in urls)

    def _set_dragging(self, dragging):
        self._dragging = dragging
        self.title_label.setText(self.tra("松开以导入") if dragging else self._title)
        self.update()

    def dragEnterEvent(self, event):
        if self._accepts_drop(event):
            self._set_dragging(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepts_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_dragging(False)
        event.accept()

    def dropEvent(self, event):
        self._set_dragging(False)
        if self._accepts_drop(event):
            event.acceptProposedAction()
            self.pathsDropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
        else:
            event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.backgroundColor)
        color = themeColor() if self._dragging else (
            QColor(255, 255, 255, 65) if isDarkTheme() else QColor(0, 0, 0, 55))
        pen = QPen(color, 1.5)
        pen.setDashPattern([5, 4])
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5),
                                self.borderRadius, self.borderRadius)


class _ProjectTitle(StrongBodyLabel):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setText(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, self.width()))


class _HistoryItemDelegate(ListItemDelegate):
    def paint(self, painter, option, index):
        # The row card owns its native hover effect; omit the list's highlight.
        pass


class _HistoryRow(CardWidget, ConfigMixin):
    deleteRequested = pyqtSignal(str, str)

    def __init__(self, workspace_id, title, details, icon, parent=None):
        super().__init__(parent)
        self.setBorderRadius(4)
        self.setMouseTracking(True)
        self.setToolTip(title + ("\n" + details if details else ""))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)
        marker = IconWidget(icon, self)
        marker.setFixedSize(22, 22)
        marker.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(marker)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        title_label = _ProjectTitle(title, self)
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        text.addWidget(title_label)
        caption = CaptionLabel(details, self)
        caption.setTextColor("#707070", "#a6a6a6")
        caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        text.addWidget(caption)
        layout.addLayout(text, 1)
        self.delete_button = TransparentToolButton(FluentIcon.DELETE, self)
        self.delete_button.setFixedSize(32, 32)
        self.delete_button.setIconSize(QSize(16, 16))
        self.delete_button.setToolTip(self.tra("删除项目"))
        self.delete_button.setAccessibleName(self.tra("删除项目：") + title)
        # Button events must never reach the list, including a double click.
        self.delete_button.setAttribute(Qt.WA_NoMousePropagation)
        self.delete_button.clicked.connect(lambda checked=False: self.deleteRequested.emit(workspace_id, title))
        layout.addWidget(self.delete_button)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        event.ignore()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        # The row belongs to the list viewport. Ignored non-button events keep
        # the native item selection and double-click behavior intact.
        event.ignore()


class MediaStartPage(QWidget, ConfigMixin):
    deleteRequested = pyqtSignal(str, str)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._history_rows = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)
        self.drop_card = MediaDropCard(kind, self)
        self.pick_files = self.drop_card.pick_files
        self.pick_folder = self.drop_card.pick_folder
        self.pick_zip = self.drop_card.pick_zip
        layout.addWidget(self.drop_card)

        self.history_card = SimpleCardWidget(self)
        self.history_card.setBorderRadius(16)
        history = QVBoxLayout(self.history_card)
        history.setContentsMargins(12, 18, 12, 12)
        history.setSpacing(12)
        header = QHBoxLayout()
        header.setContentsMargins(8, 0, 8, 0)
        header.setSpacing(10)
        marker = IconWidget(FluentIcon.HISTORY, self.history_card)
        marker.setFixedSize(18, 18)
        header.addWidget(marker)
        header.addWidget(StrongBodyLabel(self.tra("最近项目"), self.history_card))
        header.addStretch(1)
        self.history_count = CaptionLabel("0", self.history_card)
        self.history_count.setTextColor("#707070", "#a6a6a6")
        header.addWidget(self.history_count)
        history.addLayout(header)

        self.history_stack = QStackedWidget(self.history_card)
        self.history_list = ListWidget(self.history_stack)
        self.history_list.setItemDelegate(_HistoryItemDelegate(self.history_list))
        self.history_list.setMinimumHeight(0)
        self.history_list.setSpacing(3)
        self.history_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_list.setStyleSheet("QListWidget { border: none; background: transparent; outline: none; }")
        self.history_stack.addWidget(self.history_list)

        self.empty_hint = QWidget(self.history_stack)
        empty = QVBoxLayout(self.empty_hint)
        empty.setContentsMargins(16, 24, 16, 24)
        empty.setSpacing(12)
        empty.addStretch(1)
        empty_icon = IconWidget(FluentIcon.FOLDER, self.empty_hint)
        empty_icon.setFixedSize(28, 28)
        empty.addWidget(empty_icon, 0, Qt.AlignHCenter)
        empty_label = CaptionLabel(self.tra("暂无最近项目"), self.empty_hint)
        empty_label.setTextColor("#838383", "#929292")
        empty_label.setAlignment(Qt.AlignCenter)
        empty.addWidget(empty_label)
        empty.addStretch(1)
        self.history_stack.addWidget(self.empty_hint)
        history.addWidget(self.history_stack, 1)
        layout.addWidget(self.history_card, 1)
        self.set_history([])

    def set_history(self, rows):
        """Populate recent projects; item UserRole remains the workspace ID."""
        if rows == self._history_rows:
            return
        current = self.history_list.currentItem()
        selected_id = current.data(Qt.UserRole) if current else None
        self.history_list.clear()
        icon = FluentIcon.PHOTO if self.kind == "image" else FluentIcon.MUSIC
        for row in rows:
            if not isinstance(row, dict) or not row.get("workspace_id"):
                continue
            title = str(row.get("project_name") or row.get("name") or self.tra("未命名项目"))
            details = []
            count = row.get("file_count")
            if type(count) is int and count >= 0:
                details.append(f"{count}{self.tra(' 个文件')}")
            updated = QDateTime.fromString(str(row.get("updated_at", "")), Qt.ISODateWithMs)
            if updated.isValid():
                details.append(updated.toLocalTime().toString("MM-dd HH:mm"))
            subtitle = " · ".join(details)
            workspace_id = str(row["workspace_id"])
            item = QListWidgetItem()
            item.setData(Qt.UserRole, workspace_id)
            item.setData(Qt.AccessibleTextRole, title)
            item.setToolTip(title + ("\n" + subtitle if subtitle else ""))
            item.setSizeHint(QSize(0, 68))
            self.history_list.addItem(item)
            widget = _HistoryRow(workspace_id, title, subtitle, icon, self.history_list)
            widget.deleteRequested.connect(self.deleteRequested.emit)
            self.history_list.setItemWidget(item, widget)
            if workspace_id == selected_id:
                self.history_list.setCurrentItem(item)
        self._sync_history_state()
        self._history_rows = copy.deepcopy(rows)

    def remove_history(self, workspace_id):
        """Remove a confirmed deletion locally, without reloading remote history."""
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            if item.data(Qt.UserRole) == workspace_id:
                self.history_list.removeItemWidget(item)
                self.history_list.takeItem(index)
                self._history_rows = [row for row in (self._history_rows or [])
                                      if not isinstance(row, dict) or str(row.get("workspace_id")) != workspace_id]
                self._sync_history_state()
                return True
        return False

    def _sync_history_state(self):
        count = self.history_list.count()
        self.history_count.setText(str(count))
        self.history_stack.setCurrentWidget(self.history_list if count else self.empty_hint)
