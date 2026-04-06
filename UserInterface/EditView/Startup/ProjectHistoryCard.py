from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import CaptionLabel, CardWidget, FluentIcon, PushButton, StrongBodyLabel, TransparentToolButton

from ModuleFolders.Config.Config import ConfigMixin


class ProjectHistoryCard(ConfigMixin, CardWidget):
    """历史项目卡片。"""

    continue_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = dict(entry or {})
        self.project_id = str(self.entry.get("project_id", "")).strip()

        self.setBorderRadius(4)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_label = StrongBodyLabel(self.entry.get("project_name", self.project_id), self)
        meta_label = CaptionLabel(self._build_meta_text(), self)
        meta_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))

        text_layout.addWidget(title_label)
        text_layout.addWidget(meta_label)

        self.continue_btn = PushButton(self.tra("继续"), self)
        self.continue_btn.setFixedSize(96, 32)
        self.continue_btn.clicked.connect(lambda: self.continue_clicked.emit(self.project_id))

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE, self)
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.project_id))

        progress_label = CaptionLabel(self._build_progress_text(), self)
        progress_label.setAlignment(Qt.AlignCenter)
        progress_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))

        layout.addLayout(text_layout)
        layout.addStretch(1)
        layout.addWidget(progress_label, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        layout.addWidget(self.continue_btn)
        layout.addWidget(self.delete_btn)

    def _build_meta_text(self) -> str:
        create_time = self.entry.get("project_create_time", "")
        if create_time:
            return f"{self.tra('创建时间')}: {create_time}"
        return self.project_id

    def _build_progress_text(self) -> str:
        total_line = int(self.entry.get("total_line", 0) or 0)
        line = int(self.entry.get("line", 0) or 0)
        if total_line <= 0:
            return self.tra("进度: 未开始")

        percent = min(100, int(line / total_line * 100))
        if self.entry.get("is_complete"):
            return f"{self.tra('进度')}: {self.tra('已完成')} ({line}/{total_line})"

        return f"{self.tra('进度')}: {percent}% ({line}/{total_line})"
