from PyQt5.QtGui import QColor 
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget 

from qfluentwidgets import (
    CardWidget, FlowLayout, CaptionLabel, StrongBodyLabel,HorizontalSeparator,
    IconWidget, FluentIcon 
)

class APITypeCard(CardWidget):
    def __init__(self, title: str, description: str, icon: FluentIcon = None, parent: QWidget = None, init=None):

        super().__init__(parent)

        # --- 基础设置 ---
        self.setBorderRadius(8) # 增加圆角
        self.setContentsMargins(0, 0, 0, 0) 

        # --- 主垂直布局 ---
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(16, 12, 16, 16) # 调整边距 (左, 上, 右, 下) 
        self.container.setSpacing(12) 

        # --- 头部区域 (图标 + 文本) ---
        self.head_container = QFrame(self) 
        self.head_hbox = QHBoxLayout(self.head_container)
        self.head_hbox.setContentsMargins(0, 0, 0, 0) # 头部内部无额外边距
        self.head_hbox.setSpacing(12) # 图标和文本之间的间距

        # 可选：添加图标
        self.icon_widget = None
        if icon:
            self.icon_widget = IconWidget(icon, self)
            self.icon_widget.setFixedSize(20, 20) 
            self.head_hbox.addWidget(self.icon_widget)

        # 文本容器 (标题 + 描述)
        self.text_container = QFrame(self) 
        self.text_vbox = QVBoxLayout(self.text_container)
        self.text_vbox.setContentsMargins(0, 0, 0, 0)
        self.text_vbox.setSpacing(4) # 标题和描述之间的间距可以小一些

        self.title_label = StrongBodyLabel(title, self)
        self.text_vbox.addWidget(self.title_label)

        self.description_label = CaptionLabel(description, self)
        self.text_vbox.addWidget(self.description_label)

        self.head_hbox.addWidget(self.text_container, 1) # 让文本区域占据主要空间

        # 添加头部容器到主布局
        self.container.addWidget(self.head_container)

        # --- 分割线 ---

        self.line = HorizontalSeparator(self)
        self.container.addWidget(self.line)

        # --- 流式布局区域 ---
        self.flow_container = QFrame(self) # Frame 用于容纳 FlowLayout
        self.flow_layout = FlowLayout(self.flow_container, needAni=False) 
        self.flow_layout.setContentsMargins(0, 0, 0, 0) # 流式布局本身无边距
        self.flow_layout.setHorizontalSpacing(8) # 水平间距
        self.flow_layout.setVerticalSpacing(8)   # 垂直间距
        self.container.addWidget(self.flow_container)

        # --- 初始化回调 ---
        if init:
            init(self)

    def set_title(self, title: str) -> None:
        """设置卡片标题"""
        self.title_label.setText(title)

    def set_description(self, description: str) -> None:
        """设置卡片描述"""
        self.description_label.setText(description)

    def set_icon(self, icon: FluentIcon) -> None:
        """设置或更新卡片图标"""
        if self.icon_widget:
            self.icon_widget.setIcon(icon)
        elif icon: 
            self.icon_widget = IconWidget(icon, self)
            self.icon_widget.setFixedSize(20, 20)
            # 插入到 HBox 的最前面
            self.head_hbox.insertWidget(0, self.icon_widget)

    def add_widget(self, widget: QWidget) -> None:
        """向流式布局区域添加控件"""
        self.flow_layout.addWidget(widget)

    def add_widget_to_head(self, widget: QWidget, stretch: int = 0) -> None:
        """
        向头部区域添加控件（在文本区域之后）。
        """
        if stretch > 0:
            self.head_hbox.addStretch(stretch)
        self.head_hbox.addWidget(widget)

    def take_all_widgets(self) -> list[QWidget]:
        """移除流式布局中的所有控件并返回它们（不删除）"""
        return self.flow_layout.takeAllWidgets()

    def clear_widgets(self) -> None:
        """移除并删除流式布局中的所有控件"""
        widgets = self.flow_layout.takeAllWidgets()
        for widget in widgets:
            widget.deleteLater()