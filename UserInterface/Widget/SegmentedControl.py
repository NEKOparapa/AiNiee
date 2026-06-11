from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QButtonGroup, QSizePolicy, QGraphicsDropShadowEffect,
)

from qfluentwidgets import isDarkTheme, themeColor, qconfig, setFont


class SegmentedControl(QWidget):
    """分段控件：大圆角轨道内嵌可滑动的小圆角高亮块，选中项主题色实心+对比色字，切换带缓动动画。"""

    currentChanged = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(36)
        self._buttons = []
        self._current_key = None

        # 滑动高亮块（位于按钮下层，绝对定位，不进布局）
        self._indicator = QWidget(self)
        self._indicator.setObjectName("segIndicator")
        self._indicator.setAttribute(Qt.WA_StyledBackground, True)
        self._indicator.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 柔和投影，让选中块从凹陷轨道上微微高起
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setXOffset(0)
        shadow.setYOffset(1)
        shadow.setColor(QColor(0, 0, 0, 90))
        self._indicator.setGraphicsEffect(shadow)

        self._anim = QPropertyAnimation(self._indicator, b"geometry", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(3, 3, 3, 3)
        self._hbox.setSpacing(0)

        try:
            qconfig.themeChanged.connect(self._apply_style)
            self.destroyed.connect(self._on_destroyed)
        except Exception:
            pass

    def _on_destroyed(self, *_args) -> None:
        try:
            qconfig.themeChanged.disconnect(self._apply_style)
        except (TypeError, RuntimeError):
            pass

    def add_item(self, key: str, text: str) -> None:
        button = QPushButton(text, self)
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setProperty("segKey", key)
        button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        setFont(button, 14)
        button.clicked.connect(lambda _checked, k=key: self._on_clicked(k))
        self._group.addButton(button)
        self._hbox.addWidget(button)
        self._buttons.append(button)
        button.raise_()
        self._apply_style()

    def set_current_key(self, key: str) -> None:
        self._current_key = key
        for button in self._buttons:
            button.setChecked(button.property("segKey") == key)
        self._update_text_colors()
        QTimer.singleShot(0, lambda: self._move_indicator(animate=False))

    def _on_clicked(self, key: str) -> None:
        if key == self._current_key:
            return
        self._current_key = key
        self._update_text_colors()
        self._move_indicator(animate=True)
        self.currentChanged.emit(key)

    def _current_button(self):
        for button in self._buttons:
            if button.property("segKey") == self._current_key:
                return button
        return None

    def _move_indicator(self, animate: bool) -> None:
        button = self._current_button()
        if button is None:
            return
        target = button.geometry()
        self._anim.stop()
        if animate and self._indicator.width() > 0:
            self._anim.setStartValue(self._indicator.geometry())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._indicator.setGeometry(target)
        self._indicator.lower()
        self._indicator.show()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 延迟到布局完成后再定位，避免滚动区内首次显示时按钮 geometry 仍为零矩形
        QTimer.singleShot(0, lambda: self._move_indicator(animate=False))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._move_indicator(animate=False)

    def _update_text_colors(self) -> None:
        accent_color = themeColor()
        yiq = (accent_color.red() * 299 + accent_color.green() * 587 + accent_color.blue() * 114) / 1000
        selected_text = "#000000" if yiq >= 128 else "#ffffff"
        if isDarkTheme():
            normal_text = "#e8e8e8"
            hover = "rgba(255, 255, 255, 0.06)"
        else:
            normal_text = "#1a1a1a"
            hover = "rgba(0, 0, 0, 0.04)"
        for button in self._buttons:
            checked = button.property("segKey") == self._current_key
            color = selected_text if checked else normal_text
            base = (
                "QPushButton {"
                "  background: transparent;"
                "  border: none;"
                "  padding: 0px 16px;"
                f"  color: {color};"
                "}"
            )
            if not checked:
                base += f"QPushButton:hover {{ background: {hover}; border-radius: 5px; }}"
            button.setStyleSheet(base)

    def _apply_style(self) -> None:
        accent_color = themeColor()
        accent = accent_color.name()
        accent_light = accent_color.lighter(112).name()
        accent_dark = accent_color.darker(116).name()
        if isDarkTheme():
            track_bg = "rgba(0, 0, 0, 0.22)"
            track_border = "rgba(0, 0, 0, 0.28)"
        else:
            track_bg = "rgba(0, 0, 0, 0.06)"
            track_border = "rgba(0, 0, 0, 0.12)"
        self.setStyleSheet(
            "SegmentedControl {"
            f"  background: {track_bg};"
            f"  border: 1px solid {track_border};"
            "  border-radius: 7px;"
            "}"
        )
        # 选中块：顶部提亮的竖向渐变 + 略深描边，营造微微高起的立体质感
        self._indicator.setStyleSheet(
            "#segIndicator {"
            f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent_light}, stop:1 {accent});"
            f"  border: 1px solid {accent_dark};"
            "  border-radius: 5px;"
            "}"
        )
        self._update_text_colors()
