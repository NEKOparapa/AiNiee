###源码
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (CardWidget, StrongBodyLabel, CaptionLabel,
                            PushButton, pyqtSignal)

class ActionCard(CardWidget):
    """
    一个左侧显示描述文本，右侧显示一个操作按钮的卡片组件。
    """
    clicked = pyqtSignal()  # 定义一个点击信号

    def __init__(self, title: str, description: str, button_text: str, icon=None, parent=None):
        super().__init__(parent)
        self.setBorderRadius(4)

        # 主布局
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 16, 16, 16)
        self.hbox.setSpacing(12)

        # 左侧文本布局
        self.vbox = QVBoxLayout()
        self.titleLabel = StrongBodyLabel(title, self)
        self.descriptionLabel = CaptionLabel(description, self)
        self.descriptionLabel.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        
        self.vbox.addWidget(self.titleLabel)
        self.vbox.addWidget(self.descriptionLabel)
        self.vbox.setSpacing(4)

        # 中间的项目名标签
        self.project_name_label = CaptionLabel("", self)
        self.project_name_label.setObjectName('projectNameLabel')
        self.project_name_label.hide() # 默认隐藏

        # 右侧按钮
        self.button = PushButton(icon, button_text, self) if icon else PushButton(button_text, self)
        self.button.setFixedWidth(120)
        self.button.setFixedHeight(32)

        # 组装布局
        self.hbox.addLayout(self.vbox)
        self.hbox.addStretch(1)
        self.hbox.addWidget(self.project_name_label) # 将项目名标签放在中间
        self.hbox.addStretch(1)
        self.hbox.addWidget(self.button)

        # 信号连接
        self.button.clicked.connect(self.clicked)

    # 设置项目名并显示标签的方法
    def set_project_name(self, name: str):
        """设置项目名并显示标签"""
        if name:
            self.project_name_label.setText(f"项目: {name}")
            self.project_name_label.show()
        else:
            self.project_name_label.hide()
            
    # 隐藏项目名标签的方法
    def hide_project_name(self):
        """隐藏项目名标签"""
        self.project_name_label.hide()