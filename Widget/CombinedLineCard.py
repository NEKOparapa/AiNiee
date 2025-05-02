from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import CardWidget, LargeTitleLabel, StrongBodyLabel, IconWidget, FluentIcon, BodyLabel, CaptionLabel

class CombinedLineCard(CardWidget):
    def __init__(self,
                 title: str,
                 icon: FluentIcon = None,
                 left_title: str = "Metric 1",
                 right_title: str = "Metric 2",
                 initial_left_value: str = "0",
                 initial_left_unit: str = "",
                 initial_right_value: str = "0",
                 initial_right_unit: str = "",
                 parent: QWidget = None,
                 clicked=None
                 ):
        super().__init__(parent)

        # --- 基本卡片设置 ---
        self.setBorderRadius(8)

        # --- 主布局 ---
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(16, 12, 16, 12)
        self.mainLayout.setSpacing(8)

        # --- 顶部区域：图标（可选）和标题 ---
        self.topLayout = QHBoxLayout()
        self.topLayout.setContentsMargins(0, 0, 0, 0)
        self.topLayout.setSpacing(8)

        if icon:
            self.iconWidget = IconWidget(icon, self)
            self.iconWidget.setFixedSize(18, 18)
            self.topLayout.addWidget(self.iconWidget)
        else:
            self.iconWidget = None

        self.titleLabel = BodyLabel(title, self)
        self.titleLabel.setTextColor("#606060")
        self.topLayout.addWidget(self.titleLabel, 1)

        # --- 底部区域：左右数据和分割线 ---
        self.bottomLayout = QHBoxLayout()
        self.bottomLayout.setContentsMargins(0, 5, 0, 0)
        self.bottomLayout.setSpacing(15) # 左右数据区域和分割线区域的总间距

        # --- 左侧数据 ---
        self.leftDataLayout = QVBoxLayout()
        self.leftDataLayout.setContentsMargins(0, 0, 0, 0)
        self.leftDataLayout.setSpacing(4)
        self.leftDataLayout.setAlignment(Qt.AlignCenter)

        self.leftTitleLabel = CaptionLabel(left_title, self)
        self.leftTitleLabel.setAlignment(Qt.AlignCenter)
        self.leftDataLayout.addWidget(self.leftTitleLabel)

        self.leftValueLayout = QHBoxLayout()
        self.leftValueLayout.setContentsMargins(0, 0, 0, 0)
        self.leftValueLayout.setSpacing(4)
        self.leftValueLayout.setAlignment(Qt.AlignCenter)

        self.leftValueLabel = LargeTitleLabel(initial_left_value, self)
        self.leftUnitLabel = StrongBodyLabel(initial_left_unit, self)
        self.leftUnitLabel.setAlignment(Qt.AlignBottom)
        self.leftUnitLabel.setTextColor("#404040")

        self.leftValueLayout.addStretch(1)
        self.leftValueLayout.addWidget(self.leftValueLabel)
        self.leftValueLayout.addWidget(self.leftUnitLabel)
        self.leftValueLayout.addStretch(1)
        self.leftDataLayout.addLayout(self.leftValueLayout)

        self.bottomLayout.addLayout(self.leftDataLayout, 1)

        # ---分割线 ---
        separatorLayout = QVBoxLayout()
        separatorLayout.setContentsMargins(0, 0, 0, 0) # 内部边距为0
        separatorLayout.setSpacing(0) # 内部间距为0

        separatorLayout.addStretch(1) # 在线上方添加伸缩

        # 创建实际的线 (QWidget)
        line = QWidget(self)
        line.setFixedWidth(1)  # 宽度为1像素，使其成为垂直线
        line.setFixedHeight(35) # 设置线的固定高度，使其变短 
        line.setStyleSheet("QWidget { background-color: #C0C0C0; }")

        separatorLayout.addWidget(line, 0, Qt.AlignCenter) # 将线添加到布局中，水平居中

        separatorLayout.addStretch(1) # 在线下方添加伸缩

        # 将包含线的布局添加到主底部布局中
        self.bottomLayout.addLayout(separatorLayout) # 不设置拉伸因子，让它只占用必要的宽度

        # --- 右侧数据 ---
        self.rightDataLayout = QVBoxLayout()
        self.rightDataLayout.setContentsMargins(0, 0, 0, 0)
        self.rightDataLayout.setSpacing(4)
        self.rightDataLayout.setAlignment(Qt.AlignCenter)

        self.rightTitleLabel = CaptionLabel(right_title, self)
        self.rightTitleLabel.setAlignment(Qt.AlignCenter)
        self.rightDataLayout.addWidget(self.rightTitleLabel)

        self.rightValueLayout = QHBoxLayout()
        self.rightValueLayout.setContentsMargins(0, 0, 0, 0)
        self.rightValueLayout.setSpacing(4)
        self.rightValueLayout.setAlignment(Qt.AlignCenter)

        self.rightValueLabel = LargeTitleLabel(initial_right_value, self)
        self.rightUnitLabel = StrongBodyLabel(initial_right_unit, self)
        self.rightUnitLabel.setAlignment(Qt.AlignBottom)
        self.rightUnitLabel.setTextColor("#404040")

        self.rightValueLayout.addStretch(1)
        self.rightValueLayout.addWidget(self.rightValueLabel)
        self.rightValueLayout.addWidget(self.rightUnitLabel)
        self.rightValueLayout.addStretch(1)
        self.rightDataLayout.addLayout(self.rightValueLayout)

        self.bottomLayout.addLayout(self.rightDataLayout, 1)

        # --- 添加到主容器 ---
        self.mainLayout.addLayout(self.topLayout)
        self.mainLayout.addSpacing(4)
        self.mainLayout.addLayout(self.bottomLayout, 1)

        # --- 添加点击信号 ---
        if clicked:
            self.clicked.connect(clicked)

    # --- 后续方法保持不变 ---
    def set_left_data(self, value: str, unit: str):
        self.leftValueLabel.setText(str(value))
        self.leftUnitLabel.setText(unit)

    def set_right_data(self, value: str, unit: str):
        self.rightValueLabel.setText(str(value))
        self.rightUnitLabel.setText(unit)

    def set_left_title(self, title: str):
        self.leftTitleLabel.setText(title)

    def set_right_title(self, title: str):
        self.rightTitleLabel.setText(title)

    def set_main_title(self, title: str):
        self.titleLabel.setText(title)

    def set_icon(self, icon: FluentIcon):
        if self.iconWidget:
            self.iconWidget.setIcon(icon)

    def set_left_value_color(self, color: str):
        self.leftValueLabel.setStyleSheet(f"color: {color};")

    def set_right_value_color(self, color: str):
        self.rightValueLabel.setStyleSheet(f"color: {color};")

# --- 示例用法 (如果需要测试) ---
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
    from qfluentwidgets import FluentIcon

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("CombinedLineCard Example")
    layout = QVBoxLayout(window)

    card1 = CombinedLineCard(
        title="System Status",
        icon=FluentIcon.SPEED_HIGH,
        left_title="CPU Usage",
        right_title="Memory Usage",
        initial_left_value="45",
        initial_left_unit="%",
        initial_right_value="6.8",
        initial_right_unit="GB"
    )

    card2 = CombinedLineCard(
        title="Network Activity",
        icon=FluentIcon.WIFI,
        left_title="Download",
        right_title="Upload",
        initial_left_value="12.5",
        initial_left_unit="MB/s",
        initial_right_value="2.1",
        initial_right_unit="MB/s"
    )
    card2.set_left_value_color("green")
    card2.set_right_value_color("orange")


    layout.addWidget(card1)
    layout.addWidget(card2)
    layout.addStretch(1)
    window.resize(350, 300)
    window.show()
    sys.exit(app.exec_())