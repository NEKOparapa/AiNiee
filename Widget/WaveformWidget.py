import time

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QLabel

from qfluentwidgets import isDarkTheme

class WaveformWidget(QLabel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 自动填充背景
        # self.setAutoFillBackground(True)

        # 设置字体
        self.font = QFont("Consolas", 8)

        # 每个字符所占用的空间
        self.point_size = self.font.pointSize()

        # 历史数据
        self.history = [0]

        # 设置矩阵大小
        self.set_matrix_size(50, 20)

        # 刷新率
        self.refresh_rate = 2

        # 最近一次添加数据的时间
        self.last_add_value_time = 0

        # 开始刷新
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / self.refresh_rate))

    # 刷新
    def tick(self):
        if time.time() - self.last_add_value_time >= (1 / self.refresh_rate):
            # 如果周期内数据没有更新，则重复最后一个数据
            self.repeat()

        # 刷新界面
        self.update()

    def paintEvent(self, event):
        # 初始化画笔
        painter = QPainter(self)
        painter.setFont(self.font)
        painter.setPen(Qt.white if isDarkTheme() else Qt.black)

        # 归一化以增大波形起伏
        min_val = min(self.history)
        max_val = max(self.history)
        if max_val - min_val == 0 and self.history[0] == 0:
            values = [0 for i in self.history]
        elif max_val - min_val == 0 and self.history[0] != 0:
            values = [1 for i in self.history]
        else:
            values = [(v - min_val) / (max_val - min_val) for v in self.history]

        # 生成文本
        lines = []
        for value in reversed(values):
            lines.append("▨" * int(value * (self.matrix_height - 1) + 1))

        # 绘制文本
        x = self.max_width - self.point_size
        for line in lines:
            y = self.max_height

            for point in line:
                painter.drawText(x, y, point)
                y = y - self.point_size

            x = x - self.point_size

    # 重复最后的数据
    def repeat(self):
        self.add_value(self.history[-1] if len(self.history) > 0 else 0)

    # 添加数据
    def add_value(self, value: int):
        if len(self.history) >= self.matrix_width:
            self.history.pop(0)

        self.history.append(value)

        # 记录下最后添加数据的时间
        self.last_add_value_time = time.time()

    # 设置矩阵大小
    def set_matrix_size(self, width: int, height: int):
        self.matrix_width = width
        self.matrix_height = height
        self.max_width = self.matrix_width * self.point_size
        self.max_height = self.matrix_height * self.point_size
        self.setFixedSize(self.max_width, self.max_height)
        self.history = [0 for i in range(self.matrix_width)]