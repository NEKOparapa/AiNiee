from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import CardWidget, LargeTitleLabel, StrongBodyLabel, IconWidget, FluentIcon, BodyLabel 

class DashboardCard(CardWidget):
    def __init__(self,
                 title: str,
                 value: str,
                 unit: str,
                 icon: FluentIcon = None, 
                 parent: QWidget = None, 
                 clicked = None
                 ):
        super().__init__(parent)

        # --- 基本设置 ---
        self.setBorderRadius(8) # 稍大的半径以获得更柔和的外观

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

        # --- 中间区域：数值和单位 ---
        self.valueLabel = LargeTitleLabel(value, self)
        self.unitLabel = StrongBodyLabel(unit, self)
        self.unitLabel.setAlignment(Qt.AlignBottom) # 将单位对齐到数值标签行的底部
        self.unitLabel.setTextColor("#404040") 

        self.valueLayout = QHBoxLayout()
        self.valueLayout.setContentsMargins(0, 0, 0, 0)
        self.valueLayout.setSpacing(4) 
        self.valueLayout.setAlignment(Qt.AlignCenter) # 水平居中数值和单位
        self.valueLayout.addStretch(1) # 在之前添加伸缩项
        self.valueLayout.addWidget(self.valueLabel)
        self.valueLayout.addWidget(self.unitLabel)
        self.valueLayout.addStretch(1) # 在之后添加伸缩项

        # 添加进主布局
        self.mainLayout.addLayout(self.topLayout)
        self.mainLayout.addSpacing(4) # 在数值前的少量间距
        self.mainLayout.addLayout(self.valueLayout, 1) 

        # 连接信号
        if clicked:
            self.clicked.connect(clicked) # 连接卡片的点击信号

        # 连接信号示例：带有图标的 CPU 使用率
        #cpu_card = DashboardCard(
        #    title="CPU 使用率",
        #    value="75",
        #    unit="%",
        #    icon=FluentIcon.ACCEPT_MEDIUM,
        #    parent=centralWidget,
        #    clicked=lambda: card_clicked_action("CPU 使用率")
        #)

    def set_value(self, value: str):
        """设置主数值文本。"""
        self.valueLabel.setText(str(value)) # 确保数值是字符串

    def set_unit(self, unit: str):
        """设置单位文本。"""
        self.unitLabel.setText(unit)

    def set_title(self, title: str):
        """设置标题文本。"""
        self.titleLabel.setText(title)

    def set_icon(self, icon: FluentIcon):
        """设置或更新图标。"""
        if self.iconWidget:
            self.iconWidget.setIcon(icon)

    def set_value_color(self, color: str):
        """设置数值标签的颜色（例如，根据状态）。"""
        self.valueLabel.setStyleSheet(f"color: {color};")

        # 设置数值文本颜色
        #cpu_card.set_value_color("orange")
