from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import CardWidget, StrongBodyLabel, CaptionLabel, PushButton, TransparentToolButton, FluentIcon, pyqtSignal

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class ProjectHistoryCard(CardWidget, ConfigMixin, Base):
    """历史项目卡片，显示项目名、路径、进度，并提供继续和删除按钮"""
    continue_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setBorderRadius(4)

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(16, 12, 16, 12)
        hbox.setSpacing(12)

        # 左侧：项目名 + 路径
        vbox = QVBoxLayout()
        vbox.setSpacing(2)

        name_label = StrongBodyLabel(entry.get("project_name", ""), self)
        vbox.addWidget(name_label)

        path_label = CaptionLabel(entry.get("output_path", ""), self)
        path_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        vbox.addWidget(path_label)

        # 进度标签
        total = entry.get("total_line", 0)
        done = entry.get("line", 0)
        is_complete = entry.get("is_complete", False)
        if total > 0:
            pct = int(done / total * 100)
            status_text = self.tra("已完成") if is_complete else f"{pct}%  ({done}/{total})"
        else:
            status_text = ""
        progress_label = CaptionLabel(status_text, self)
        progress_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))

        # 右侧：继续按钮 + 删除按钮
        btn = PushButton(self.tra("继续"), self)
        btn.setFixedSize(100, 32)
        btn.clicked.connect(lambda: self.continue_clicked.emit())

        delete_btn = TransparentToolButton(FluentIcon.DELETE, self)
        delete_btn.setIconSize(QSize(16, 16))
        delete_btn.setFixedSize(32, 32)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit())

        hbox.addLayout(vbox)
        hbox.addStretch(1)
        hbox.addWidget(progress_label)
        hbox.addSpacing(16)
        hbox.addWidget(btn)
        hbox.addWidget(delete_btn)
