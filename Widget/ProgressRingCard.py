from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import  QVBoxLayout, QHBoxLayout
from qfluentwidgets import (CardWidget, IconWidget,
                            FluentIcon, BodyLabel, ProgressRing)

class ProgressRingCard(CardWidget):
    """
    显示进度环的监控卡片
    """
    def __init__(self,
                 title: str,
                 icon: FluentIcon = None,
                 min_value: int = 0,
                 max_value: int = 100,
                 value: int = 0,
                 stroke_width: int = 8, # 调整进度环线条宽度
                 ring_size: tuple[int, int] = (100, 100), # 调整进度环大小
                 text_visible: bool = True,
                 parent =  None,
                 clicked = None
                 ):
        """
        初始化进度环卡片。

        参数:
            title (str): 卡片的标题。
            icon (FluentIcon, optional): 卡片左上角的图标。默认为 None。
            min_value (int, optional): 进度环的最小值。默认为 0。
            max_value (int, optional): 进度环的最大值。默认为 100。
            value (int, optional): 进度环的初始值。默认为 0。
            stroke_width (int, optional): 进度环线条的宽度。默认为 8。
            ring_size (tuple[int, int], optional): 进度环的固定尺寸 (宽, 高)。默认为 (100, 100)。
            text_visible (bool, optional): 是否显示进度环中心的文本（通常是百分比）。默认为 True。
            parent (QWidget, optional): 父级窗口。默认为 None。
            clicked (callable, optional): 卡片被点击时调用的函数。默认为 None。
        """
        super().__init__(parent)

        # --- 基本卡片设置 ---
        self.setBorderRadius(8) # 稍大的半径以获得更柔和的外观
        # self.setFixedSize(180, 130) # 考虑设置固定或最小尺寸以确保一致性

        # --- 主布局 ---
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(16, 12, 16, 12) # 调整边距
        self.mainLayout.setSpacing(8) # 各部分之间保持一致的间距

        # --- 顶部区域：图标（可选）和标题 ---
        self.topLayout = QHBoxLayout()
        self.topLayout.setContentsMargins(0, 0, 0, 0)
        self.topLayout.setSpacing(8) # 图标和标题之间的间距

        # 设置图标
        if icon:
            self.iconWidget = IconWidget(icon, self)
            self.iconWidget.setFixedSize(18, 18) # 根据需要调整图标大小
            self.topLayout.addWidget(self.iconWidget)
        else:
            self.iconWidget = None # 如果存在图标则进行跟踪

        self.titleLabel = BodyLabel(title, self) 
        self.titleLabel.setTextColor("#606060")
        self.topLayout.addWidget(self.titleLabel, 1) 
        self.mainLayout.addLayout(self.topLayout)
        self.mainLayout.addSpacing(4) # 在数值前的少量间距


        # --- 中间区域：进度环 ---
        self.ring = ProgressRing(self)
        self.ring.setRange(min_value, max_value)
        self.ring.setValue(value)
        self.ring.setTextVisible(text_visible)
        self.ring.setStrokeWidth(stroke_width)
        self.ring.setFixedSize(ring_size[0], ring_size[1])

        # 居中放置进度环
        self.valueLayout = QHBoxLayout()
        self.valueLayout.setContentsMargins(0, 0, 0, 0)
        self.valueLayout.setSpacing(4) 
        self.valueLayout.setAlignment(Qt.AlignCenter) # 水平居中数值和单位
        self.valueLayout.addStretch(1) # 在之前添加伸缩项
        self.valueLayout.addWidget(self.ring)
        self.valueLayout.addStretch(1) # 在之后添加伸缩项


        # 添加进主布局
        self.mainLayout.addLayout(self.valueLayout, 1) 

        # 连接信号
        if clicked:
            self.clicked.connect(clicked)

    def set_value(self, value: int):
        """设置进度环的当前值。"""
        self.ring.setValue(value)

    def set_range(self, min_value: int, max_value: int):
        """设置进度环的范围（最小值和最大值）。"""
        self.ring.setRange(min_value, max_value)

    def set_format(self, format_string: str):
        self.ring.setFormat(format_string)

    def set_text_visible(self, visible: bool):
        """设置进度环中心的文本是否可见。"""
        self.ring.setTextVisible(visible)

    def set_title(self, title: str):
        """设置卡片的标题文本。"""
        self.titleLabel.setText(title)

    def set_icon(self, icon: FluentIcon):
        """设置或更新卡片的图标。"""
        if self.iconWidget:
            self.iconWidget.setIcon(icon)
