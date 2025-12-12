from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel


class InterfaceDropZoneWidget(QFrame):
    """
    一个专用于接口设置的自定义组件。
    包含一个居中对齐的描述标签和一排水平排列的拖放区域。
    """
    def __init__(self, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("interface-drop-zone-widget")

        # 主垂直布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(17, 8, 17, 8) # 上下留出一些边距
        self.main_layout.setSpacing(15)

        # 居中的描述文本
        self.description_label = CaptionLabel(description)
        self.description_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.description_label)

        # 水平排列拖拽区域的容器
        self.drop_areas_container = QFrame(self)
        self.drop_areas_hbox = QHBoxLayout(self.drop_areas_container)
        self.drop_areas_hbox.setContentsMargins(0, 0, 0, 0)
        self.drop_areas_hbox.setSpacing(15) # 设置拖拽区域之间的间距
        self.main_layout.addWidget(self.drop_areas_container)

    def add_drop_area(self, widget: QWidget):
        """向水平布局中添加一个拖拽区域"""
        self.drop_areas_hbox.addWidget(widget)