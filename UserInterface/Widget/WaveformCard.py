import time
from collections import deque 

from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath, QPolygonF
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, FluentIcon, IconWidget, themeColor, isDarkTheme

class WaveformWidget(QWidget): 

    def __init__(self, parent=None):
        super().__init__(parent)

        self.DEFAULT_COLOR = QColor(0, 120, 215)
        #self.DEFAULT_COLOR = themeColor() # 如果要跟随主题色
        self.BACKGROUND_COLOR_DARK = QColor(32, 32, 32)
        self.BACKGROUND_COLOR_LIGHT = QColor(245, 245, 245)
        self.GRID_COLOR_DARK = QColor(60, 60, 60)
        self.GRID_COLOR_LIGHT = QColor(220, 220, 220)


        self.num_points = 100       # 显示的数据点数（宽度）
        self.history = deque([0.0] * self.num_points, maxlen=self.num_points) # 使用双端队列

        self.refresh_rate = 10      # 刷新频率（Hz）
        self.last_add_value_time = 0

        # --- 外观配置 ---
        self.line_color = self.DEFAULT_COLOR  # 波形线颜色
        self.line_thickness = 2          # 线宽
        self.fill_enabled = True        # 是否填充区域
        self.gradient_enabled = True    # 是否启用渐变填充
        self.draw_grid = True          # 是否绘制背景网格
        self.grid_rows = 4             # 网格行数
        self.grid_cols = 10            # 网格列数

        # 设置最小尺寸以便布局
        self.setMinimumSize(600, 145)

        # 更新定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / self.refresh_rate))

        # 启用样式表背景样式
        self.setAttribute(Qt.WA_StyledBackground, True)
        # self.setStyleSheet("background-color: transparent;") # 或设置特定颜色

    def tick(self):
        """定时器触发的波形更新"""
        # 如果刷新间隔内没有新数据，重复最后值
        if time.time() - self.last_add_value_time >= (1.0 / self.refresh_rate):
            self.repeat()
        # 即使数据未变化也确保重绘（例如主题变更）
        self.update()


    def paintEvent(self, event):
        """处理控件绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # 启用抗锯齿

        width = self.width()
        height = self.height()

        # 1. 绘制背景（可选：或使用样式表）
        bg_color = self.BACKGROUND_COLOR_DARK if isDarkTheme() else self.BACKGROUND_COLOR_LIGHT
        painter.fillRect(self.rect(), bg_color)

        # 2. 绘制网格（可选）
        if self.draw_grid and width > 0 and height > 0:
            grid_color = self.GRID_COLOR_DARK if isDarkTheme() else self.GRID_COLOR_LIGHT
            pen = QPen(grid_color, 0.5, Qt.DotLine) # 细虚线
            painter.setPen(pen)
            # 垂直线
            for i in range(1, self.grid_cols):
                x = width * i / self.grid_cols
                painter.drawLine(QPointF(x, 0), QPointF(x, height))
            # 水平线
            for i in range(1, self.grid_rows):
                y = height * i / self.grid_rows
                painter.drawLine(QPointF(0, y), QPointF(width, y))


        if not self.history or width <= 0 or height <= 1: # 至少需要2像素高度
            return # 无数据或无效尺寸

        # 3. 数据准备和归一化
        # 使用副本避免绘制时数据修改
        history_copy = list(self.history)
        min_val = min(history_copy)
        max_val = max(history_copy)

        # 避免除零和平线情况处理
        data_range = max_val - min_val
        if data_range < 1e-6: # 接近零视为零范围
            # 全零时在底部画平线，非零常数在中线
            norm_factor = 0.0 if abs(max_val) < 1e-6 else 0.5
            normalized_values = [norm_factor] * len(history_copy)
        else:
            # 将值归一化到0.0（底部）到1.0（顶部）
            normalized_values = [(v - min_val) / data_range for v in history_copy]

        # 4. 创建波形多边形/路径
        path = QPainterPath()
        poly = QPolygonF()

        # 计算点间水平步长
        x_step = width / max(1, self.num_points - 1) # 避免除以零

        for i, norm_val in enumerate(normalized_values):
            x = i * x_step
            # 将归一化值映射到控件高度（反转y轴）
            y = height * (1.0 - norm_val)
            # 确保y在绘制范围内
            y = max(0.0, min(height -1.0, y)) # 保持有效区域

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
            poly.append(QPointF(x, y))


        # 5. 绘制填充区域
        if self.fill_enabled and len(poly) > 1:
            fill_path = QPainterPath(path) # 使用线路径作为起点
            # 添加点闭合底部边缘路径
            fill_path.lineTo(poly.last().x(), height) # 右下
            fill_path.lineTo(poly.first().x(), height) # 左下
            fill_path.closeSubpath() # 闭合路径（可选但建议）

            if self.gradient_enabled:
                gradient = QLinearGradient(0, 0, 0, height)
                fill_color_start = QColor(self.line_color)
                fill_color_start.setAlphaF(0.4) # 顶部更透明
                fill_color_end = QColor(self.line_color)
                fill_color_end.setAlphaF(0.1) # 底部更透明
                gradient.setColorAt(0.0, fill_color_start)
                gradient.setColorAt(1.0, fill_color_end)
                brush = QBrush(gradient)
            else:
                fill_color = QColor(self.line_color)
                fill_color.setAlphaF(0.3) # 半透明纯色填充
                brush = QBrush(fill_color)

            painter.setPen(Qt.NoPen) # 填充无边框
            painter.fillPath(fill_path, brush)


        # 6. 绘制波形线
        pen = QPen(self.line_color, self.line_thickness)
        pen.setJoinStyle(Qt.RoundJoin) # 平滑连接
        pen.setCapStyle(Qt.RoundCap)   # 圆角端点
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush) # 不填充线条
        painter.drawPath(path) # 在填充上方绘制线条


    def repeat(self):
        """在历史数据中重复最后值"""
        last_value = self.history[-1] if self.history else 0.0
        self.history.append(last_value)
        self.update() # 请求重绘

    def sizeHint(self):
        return self.minimumSize()
    

class WaveformCard(CardWidget):
    def __init__(self,
                 title: str,
                 icon: FluentIcon = None, 
                 parent: QWidget = None, 
                 clicked = None
                 ):
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

        # --- 底部区域 ---
        self.waveform = WaveformWidget(self) 
        self.set_num_points(100) 


        self.valueLayout = QHBoxLayout()
        self.valueLayout.setContentsMargins(0, 0, 0, 0)
        self.valueLayout.setSpacing(4) 
        self.valueLayout.setAlignment(Qt.AlignCenter) # 水平居中数值和单位
        self.valueLayout.addStretch(1) # 在之前添加伸缩项
        self.valueLayout.addWidget(self.waveform)


        # 添加进主布局
        self.mainLayout.addLayout(self.valueLayout, 1) 


        # 连接信号
        if clicked:
            self.clicked.connect(clicked) # 连接卡片的点击信号


    def add_value(self, value: float): # 接收浮点值便于平滑输入
        """添加新数据到波形历史"""
        self.waveform.history.append(float(value))
        self.waveform.last_add_value_time = time.time()
        self.update() # 请求重绘

    def set_num_points(self, points: int):
        """设置水平方向显示的数据点数"""
        if points > 0:
            self.waveform.num_points = points
            # 重新初始化历史数据（尽可能保留旧数据）
            old_data = list(self.waveform.history)
            self.waveform.history = deque([0.0] * self.waveform.num_points, maxlen=self.waveform.num_points)
            # 如果调整后尺寸更小则从末尾填充旧数据，更大则补零
            start_index = max(0, len(old_data) - self.waveform.num_points)
            for i, val in enumerate(old_data[start_index:]):
                # 调整双端队列索引从右侧填充
                deque_index = self.waveform.num_points - (len(old_data) - start_index) + i
                if deque_index < self.waveform.num_points:
                    self.waveform.history[deque_index] = val

            self.waveform.update() # 触发重绘

    def set_line_color(self, color: QColor):
        """设置波形线/填充颜色"""
        self.waveform.line_color = color
        self.waveform.update()

    def set_fill_enabled(self, enabled: bool):
        """设置是否填充曲线下区域"""
        self.waveform.fill_enabled = enabled
        self.waveform.update()

    def set_gradient_enabled(self, enabled: bool):
        """设置填充是否使用渐变"""
        self.waveform.gradient_enabled = enabled
        self.waveform.update()

    def set_draw_grid(self, enabled: bool):
        """设置是否绘制背景网格"""
        self.waveform.draw_grid = enabled
        self.waveform.update()