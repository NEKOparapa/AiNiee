from PyQt5.QtCore import QEvent, QRectF, QSize, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QStyleOptionViewItem
from qfluentwidgets import isDarkTheme, themeColor
from qfluentwidgets.components.widgets.table_view import TableItemDelegate


class SwitchTableItemDelegate(TableItemDelegate):
    """Draw boolean table items as switches without creating a widget per row."""

    @staticmethod
    def switch_rect(option):
        return QRectF(
            option.rect.center().x() - 18,
            option.rect.center().y() - 10,
            36,
            20,
        )

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # TableItemDelegate paints the indicator itself; suppress the native box.
        option.features &= ~QStyleOptionViewItem.HasCheckIndicator

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.data(Qt.CheckStateRole) is not None:
            return size.expandedTo(QSize(56, 32))
        return size

    def _drawCheckBox(self, painter, option, index):
        checked = index.data(Qt.CheckStateRole) == Qt.Checked
        dark = isDarkTheme()
        rect = self.switch_rect(option)
        painter.save()
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(themeColor())
        else:
            painter.setPen(QColor(255, 255, 255, 142) if dark else QColor(0, 0, 0, 122))
            painter.setBrush(QColor(255, 255, 255, 12) if dark else QColor(0, 0, 0, 6))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Qt.white if checked or dark else Qt.darkGray))
        x = rect.right() - 17 if checked else rect.left() + 3
        painter.drawEllipse(QRectF(x, rect.top() + 3, 14, 14))
        painter.restore()

    def editorEvent(self, event, model, option, index):
        state = index.data(Qt.CheckStateRole)
        if state is None:
            return super().editorEvent(event, model, option, index)
        if not (index.flags() & Qt.ItemIsEnabled and index.flags() & Qt.ItemIsUserCheckable):
            return False

        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            if event.button() != Qt.LeftButton or not self.switch_rect(option).contains(event.pos()):
                return False
            if event.type() == QEvent.MouseButtonPress:
                self.parent().setCurrentIndex(index)
            if event.type() != QEvent.MouseButtonRelease:
                return True
        elif event.type() == QEvent.KeyPress:
            if event.key() != Qt.Key_Space or event.isAutoRepeat():
                return False
        else:
            return False

        return model.setData(index, Qt.Unchecked if state == Qt.Checked else Qt.Checked, Qt.CheckStateRole)
