from math import ceil

from PyQt5.QtCore import QPersistentModelIndex, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextDocument, QTextOption
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemDelegate,
    QPlainTextEdit,
    QStyleOptionViewItem,
)
from qfluentwidgets import PlainTextEdit, TableWidget
from qfluentwidgets.components.widgets.table_view import TableItemDelegate


class MultilineCellEditor(PlainTextEdit):
    submitRequested = pyqtSignal()
    cancelRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._close_requested = False
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTabChangesFocus(False)
        self.setMinimumHeight(0)

    def _emit_submit(self):
        if self._close_requested:
            return

        self._close_requested = True
        self.submitRequested.emit()

    def _emit_cancel(self):
        if self._close_requested:
            return

        self._close_requested = True
        self.cancelRequested.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
                return

            event.accept()
            self._emit_submit()
            return

        if event.key() == Qt.Key_Escape:
            event.accept()
            self._emit_cancel()
            return

        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._emit_submit()


class MultilineTableItemDelegate(TableItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
        self._auto_height_columns = set()
        self._multiline_edit_columns = set()

    def setAutoHeightColumns(self, columns):
        self._auto_height_columns = {int(column) for column in columns}

    def setMultilineEditColumns(self, columns):
        self._multiline_edit_columns = {int(column) for column in columns}

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.column() not in self._auto_height_columns:
            return size

        text = self.parent().getSizeHintText(index)
        if not text:
            return size

        available_width = self._get_available_text_width(index)
        if available_width <= 0:
            return size

        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)

        document = QTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(style_option.font)
        text_option = document.defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(text_option)
        document.setPlainText(str(text))
        document.setTextWidth(available_width)

        height = ceil(document.size().height()) + self.margin * 2 + 10
        return QSize(size.width(), max(size.height(), height))

    def createEditor(self, parent, option, index):
        if index.column() not in self._multiline_edit_columns:
            return super().createEditor(parent, option, index)

        editor = MultilineCellEditor(parent)
        editor.setProperty("transparent", False)
        editor.setStyle(QApplication.style())

        persistent_index = QPersistentModelIndex(index)
        editor.submitRequested.connect(lambda editor=editor: self._commit_and_close_editor(editor))
        editor.cancelRequested.connect(lambda editor=editor: self._cancel_editor(editor))
        editor.textChanged.connect(lambda index=persistent_index, editor=editor: self._on_editor_text_changed(index, editor))
        editor.destroyed.connect(lambda _=None, row=index.row(), column=index.column(): self._on_editor_closed(row, column))
        self.parent().registerEditor(persistent_index, editor)
        return editor

    def setEditorData(self, editor, index):
        if not isinstance(editor, MultilineCellEditor):
            super().setEditorData(editor, index)
            return

        text = index.data(Qt.EditRole)
        if text is None:
            text = index.data(Qt.DisplayRole)

        text = "" if text is None else str(text)
        editor.blockSignals(True)
        editor.setPlainText(text)
        editor.blockSignals(False)
        self.parent().setEditingText(index.row(), index.column(), text)
        self.parent().resizeRowToContentsSafe(index.row())
        self.parent().syncEditorGeometry(index, editor)

    def setModelData(self, editor, model, index):
        if not isinstance(editor, MultilineCellEditor):
            super().setModelData(editor, model, index)
            return

        model.setData(index, editor.toPlainText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        if index.column() not in self._multiline_edit_columns:
            super().updateEditorGeometry(editor, option, index)
            return

        self.parent().syncEditorGeometry(index, editor)

    def _get_available_text_width(self, index):
        view = self.parent()
        width = view.columnWidth(index.column())
        if index.column() == 0:
            return max(0, width - 24)
        return max(0, width - 16)

    def _on_editor_text_changed(self, index, editor):
        if not index.isValid():
            return

        view = self.parent()
        view.setEditingText(index.row(), index.column(), editor.toPlainText())
        view.resizeRowToContentsSafe(index.row())
        view.syncEditorGeometry(index, editor)

    def _on_editor_closed(self, row, column):
        view = self.parent()
        view.clearEditingText(row, column)
        view.unregisterEditor(row, column)
        QTimer.singleShot(0, lambda row=row, view=view: view.resizeRowToContentsSafe(row))

    def _commit_and_close_editor(self, editor):
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)

    def _cancel_editor(self, editor):
        self.closeEditor.emit(editor, QAbstractItemDelegate.RevertModelCache)


class AutoHeightTableWidget(TableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_height_columns = set()
        self._multiline_edit_columns = set()
        self._editing_texts = {}
        self._active_editors = {}

        self._resize_rows_timer = QTimer(self)
        self._resize_rows_timer.setSingleShot(True)
        self._resize_rows_timer.setInterval(60)
        self._resize_rows_timer.timeout.connect(self._resize_all_rows_to_contents)

        self._multiline_delegate = MultilineTableItemDelegate(self)
        self.setItemDelegate(self._multiline_delegate)
        self.horizontalHeader().sectionResized.connect(self._on_section_resized)

    def setAutoHeightColumns(self, columns):
        self._auto_height_columns = {int(column) for column in columns}
        self._multiline_delegate.setAutoHeightColumns(self._auto_height_columns)
        self.scheduleResizeRowsToContents()

    def setMultilineEditColumns(self, columns):
        self._multiline_edit_columns = {int(column) for column in columns}
        self._multiline_delegate.setMultilineEditColumns(self._multiline_edit_columns)

    def scheduleResizeRowsToContents(self, interval_ms=60):
        if not self._auto_height_columns:
            return

        self._resize_rows_timer.start(max(0, int(interval_ms)))

    def resizeRowToContentsSafe(self, row):
        if row < 0 or row >= self.rowCount():
            return

        self.resizeRowToContents(row)
        minimum_height = self.verticalHeader().defaultSectionSize()
        if self.rowHeight(row) < minimum_height:
            self.setRowHeight(row, minimum_height)

    def setEditingText(self, row, column, text):
        self._editing_texts[(row, column)] = "" if text is None else str(text)

    def clearEditingText(self, row, column):
        self._editing_texts.pop((row, column), None)

    def getSizeHintText(self, index):
        return self._editing_texts.get(
            (index.row(), index.column()),
            index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or "",
        )

    def registerEditor(self, index, editor):
        if not index.isValid():
            return

        self._active_editors[(index.row(), index.column())] = editor

    def unregisterEditor(self, row, column):
        self._active_editors.pop((row, column), None)

    def syncEditorGeometry(self, index, editor=None):
        if not index.isValid():
            return

        if isinstance(index, QPersistentModelIndex):
            index = self.model().index(index.row(), index.column(), index.parent())
            if not index.isValid():
                return

        editor = editor or self._active_editors.get((index.row(), index.column()))
        if editor is None:
            return

        rect = self.visualRect(index)
        if not rect.isValid():
            return

        rect = rect.adjusted(8, 0, -8, 0)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        editor.setGeometry(rect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scheduleResizeRowsToContents()

    def _on_section_resized(self, logical_index, old_size, new_size):
        if logical_index in self._auto_height_columns and old_size != new_size:
            self.scheduleResizeRowsToContents()

    def _resize_all_rows_to_contents(self):
        if not self._auto_height_columns or self.rowCount() <= 0:
            return

        self.resizeRowsToContents()
        minimum_height = self.verticalHeader().defaultSectionSize()
        for row in range(self.rowCount()):
            if self.rowHeight(row) < minimum_height:
                self.setRowHeight(row, minimum_height)

        for (row, column), editor in list(self._active_editors.items()):
            if editor is not None:
                self.syncEditorGeometry(self.model().index(row, column), editor)
