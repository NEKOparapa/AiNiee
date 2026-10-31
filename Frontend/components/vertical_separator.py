from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout


class VerticalSeparator(QWidget):

    def __init__(self):
        super().__init__(None)
        
        # 使用 QVBoxLayout + QWidget + addStretch 来创建短垂直线
        separatorLayout = QVBoxLayout()
        separatorLayout.setContentsMargins(0, 0, 0, 0) # 内部边距为0
        separatorLayout.setSpacing(0) # 内部间距为0

        separatorLayout.addStretch(1) # 在线上方添加伸缩

        # 创建实际的线
        line = QWidget(self)
        line.setFixedWidth(1)  # 宽度为1像素，使其成为垂直线
        line.setFixedHeight(35) # 设置线的固定高度，使其变短 
        line.setStyleSheet("QWidget { background-color: #C0C0C0; }")

        separatorLayout.addWidget(line, 0, Qt.AlignCenter) # 将线添加到布局中，水平居中

        separatorLayout.addStretch(1) # 在线下方添加伸缩