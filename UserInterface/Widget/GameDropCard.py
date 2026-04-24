import os
import random
from PyQt5.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
)

from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPainterPath
from PyQt5.QtCore import QRectF, Qt, QPoint, QRect, QTimer, pyqtSignal

from qfluentwidgets import BodyLabel, CardWidget, CaptionLabel, FlowLayout, FluentIcon, PrimaryPushButton

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.Platform.PlatformPaths import monospace_font_family, ui_font_family
from UserInterface.Native.MacOSUI import choose_input_folder_title, get_existing_directory, input_folder_button_text

class InfoBlockWidget(ConfigMixin, Base, QWidget):
    """信息块组件 (圆角+折角+透明)"""
    def __init__(self, text, color=QColor("#E0E0E0"), parent=None):
        super().__init__(parent)
        self.text = text # 要显示的文本内容
        self.base_color = QColor(color) # 存储原始基础颜色，用于计算高亮和边框色
        self.display_mode = "text" # 显示模式
        self.fold_size = 15 # 右上角折角的大小
        self.corner_radius = 10.0 # 圆角的半径
        self.alpha_level = 170 # 透明度级别 (0-255, 越低越透明)

        self.setMinimumSize(95, 120) # 设置最小尺寸
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # 水平扩展，垂直固定

        # 设置中心文本显示字体
        self.default_font = QFont(ui_font_family(), 10)

        # 为准心创建一个稍大、等宽的字体
        self.reticle_font = QFont(monospace_font_family(), 14)
        self.reticle_font.setBold(True) # 加粗更明显

    def set_display_mode(self, mode):
        """设置显示模式 (文本或准心)"""
        if mode == "aim":
            self.display_mode = "aim"
        else:
            self.display_mode = "text"
        self.update() # 请求重新绘制控件以应用更改

    def paintEvent(self, event):
        """自定义绘制事件，用于绘制带圆角、折角和透明度的背景及内容"""
        painter = QPainter(self) # 创建 QPainter 对象用于绘制
        painter.setRenderHint(QPainter.Antialiasing) # 启用抗锯齿，使绘制更平滑

        rect = self.rect() # 获取控件的矩形区域
        # 内容区域宽度，减去折角占用的宽度
        content_width = rect.width() - self.fold_size

        # --- 定义带透明度的颜色 ---
        # 主背景色，带透明度
        bg_color = QColor(self.base_color)
        bg_color.setAlpha(self.alpha_level)

        # 折角高亮颜色 (更亮)，带透明度 
        fold_highlight_color = self.base_color.lighter(120)
        fold_highlight_color.setAlpha(min(255, self.alpha_level + 15)) # 让折角稍微不那么透明

        # 边框/线条颜色 (更暗)，带透明度
        border_color = self.base_color.darker(130)
        border_color.setAlpha(self.alpha_level)

        # --- 绘制带圆角和折角的主背景路径 ---
        path = QPainterPath() # 创建绘制路径

        # 移动到左上角圆弧之后开始
        path.moveTo(self.corner_radius, 0)
        # 绘制直线到折角开始处
        path.lineTo(content_width, 0)
        # 绘制折角部分 (锐角)
        path.lineTo(content_width, self.fold_size)
        path.lineTo(rect.width(), self.fold_size)
        # 绘制直线到右下角圆弧之前
        path.lineTo(rect.width(), rect.height() - self.corner_radius)
        # 绘制右下角圆弧 (使用 arcTo: 目标矩形, 起始角度(度), 扫描角度(度))
        br_corner_rect = QRectF(rect.width() - 2 * self.corner_radius, rect.height() - 2 * self.corner_radius, 2 * self.corner_radius, 2 * self.corner_radius)
        path.arcTo(br_corner_rect, 0, -90) # 从 3 点钟方向逆时针扫 90 度到 12 点钟方向
        # 绘制直线到左下角圆弧之后
        path.lineTo(self.corner_radius, rect.height())
        # 绘制左下角圆弧
        bl_corner_rect = QRectF(0, rect.height() - 2 * self.corner_radius, 2 * self.corner_radius, 2 * self.corner_radius)
        path.arcTo(bl_corner_rect, 270, -90) # 从 6 点钟方向逆时针扫 90 度到 3 点钟方向
        # 绘制直线到左上角圆弧之前
        path.lineTo(0, self.corner_radius)
        # 绘制左上角圆弧
        tl_corner_rect = QRectF(0, 0, 2 * self.corner_radius, 2 * self.corner_radius)
        path.arcTo(tl_corner_rect, 180, -90) # 从 9 点钟方向逆时针扫 90 度到 6 点钟方向
        # 闭合路径 (连接回起点)
        path.closeSubpath()

        # 使用透明背景色填充主形状
        painter.fillPath(path, QBrush(bg_color))

        # --- 绘制折角高亮区域 ---
        fold_path = QPainterPath() # 创建折角部分的路径
        fold_path.moveTo(content_width, 0)          # 折角内顶点
        fold_path.lineTo(rect.width(), self.fold_size) # 折角外顶点
        fold_path.lineTo(content_width, self.fold_size) # 折角下顶点
        fold_path.closeSubpath() # 闭合三角形
        painter.fillPath(fold_path, QBrush(fold_highlight_color)) # 使用高亮色填充

        # --- 绘制边框和折角线 ---
        painter.setPen(QPen(border_color, 1)) # 设置边框画笔
        painter.drawPath(path) # 绘制整个形状的边框

        # 单独绘制折角的两条分界线
        painter.drawLine(content_width, self.fold_size, rect.width(), self.fold_size) # 折角水平线
        painter.drawLine(content_width, 0, content_width, self.fold_size)         # 折角垂直线

        # --- 绘制内容 (文本或准心) ---
        # 计算内边距
        h_padding = 5 + int(self.corner_radius / 2)
        v_padding = 5 + int(self.corner_radius / 2)

        # 定义内容绘制区域 (在主背景内，避开折角，并考虑内边距)
        content_rect = QRect(0, 0, content_width, rect.height()) # 排除折角区域
        draw_rect = content_rect.adjusted(h_padding, v_padding, 0, -v_padding) # 应用内边距

        painter.setPen(Qt.black) # 设置文本/准心颜色

        if self.display_mode == "aim":
            # --- 绘制文本准心 ---
            # 方案一：简单十字
            # reticle_text = "    \n--+--\n    "
            # 方案二：带边框感觉
            reticle_text = "┌─|─┐\n──+──\n└─|─┘"

            painter.setFont(self.reticle_font) # 使用准心专用字体
            # 在绘制区域内居中绘制多行文本
            painter.drawText(draw_rect, Qt.AlignCenter, reticle_text)
            # --- 结束绘制准心 ---

        elif self.display_mode == "text":
            # --- 绘制普通文本 ---
            painter.setFont(self.default_font) # 使用默认字体
            # 在绘制区域内居中对齐并自动换行绘制文本
            painter.drawText(draw_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)
        # --- 结束绘制内容 ---


class DragDropArea(ConfigMixin, Base, QWidget):
    """实现拖拽功能的区域，包含信息块、按钮、路径显示和命中计数"""
    folderDropped = pyqtSignal(str) # 当有文件夹被成功拖入或选择时发射此信号，传递文件夹路径
    # hitCountChanged = pyqtSignal(int) # (可选) 如果需要在命中时立即通知外部，可以添加此信号

    # 修改构造函数，接收初始命中次数
    def __init__(self, parent=None, initial_hit_count: int = 0):
        super().__init__(parent)
        self.setAcceptDrops(True) # 启用接受拖放事件
        self.current_path = "" # 当前选择或拖入的文件夹路径
        self.is_dragging = False # 标记当前是否有文件正在拖拽进入区域
        self.border_color = QColor("#AAAAAA") # 默认边框颜色
        self.target_info_block = None  # 拖拽时随机选中的目标信息块
        self.fireworks_label = None   # 用于显示拖放完成后的 "烟花" (反馈) 效果的标签
        self.hit_count = initial_hit_count # 初始化命中计数器
        self.NON_SUCCESS_ICONS = ["✔️", "💔", "💋", "👀", "🙋", "🐱", "🌺", "🍔", "🍩", "🥂", "⭐", "🎈", "🧧", "💩", "🦄", "🍉", "☕"]

        # 初始化UI
        self._setup_ui()

    def _setup_ui(self):
        """初始化界面布局和组件"""
        layout = QVBoxLayout(self) # 主垂直布局
        layout.setContentsMargins(20, 20, 20, 20) # 设置外边距

        # ===== 信息块区域为流式布局 =====
        flow_container = QWidget() # 创建一个容器控件来容纳流式布局
        info_layout = FlowLayout(flow_container, needAni=False) # 使用 qfluentwidgets 的流式布局，不运行动画
        info_layout.setHorizontalSpacing(15) # 设置信息块之间的水平间距
        info_layout.setVerticalSpacing(15) # 增加垂直间距

        # 文本翻译
        info1 = self.tra("书籍")
        info2 = self.tra("文档")
        info3 = self.tra("字幕")
        info4 = self.tra("游戏挂载")
        info5 = self.tra("游戏内嵌")
        info6 = self.tra("数据文件")
        info7 = self.tra("特别文档")    
        info8 = self.tra("工程文件")

        # 创建多个信息块实例
        self.info_blocks = [
            InfoBlockWidget(f"{info1}\n Epub\n TXT", QColor("#AED6F1")),
            InfoBlockWidget(f"{info2}\n Docx\n MD",QColor("#A9DFBF")),
            InfoBlockWidget(f"{info3}\n Srt\n Vtt\n Lrc", QColor("#FAD7A0")),
            InfoBlockWidget(f"{info4}\n Mtool", QColor("#D8BFD8")),
            InfoBlockWidget(f"{info5}\n Renpy\n VNText \n SExtractor", QColor("#AFEEEE")),
            InfoBlockWidget(f"{info6}\n I18Next \n ParaTranz", QColor("#F08080")),
            InfoBlockWidget(f"{info7}\n PDF\n DOC", QColor("#E6E6FA")),
            InfoBlockWidget(f"{info8}\n .trans", QColor("#FFFACD")),
        ]
        # 将信息块添加到流式布局
        for block in self.info_blocks:
            info_layout.addWidget(block)

        # 水平布局，包含按钮和计数标签
        bottom_bar_layout = QHBoxLayout() 

        # 占位标签
        self.NoneLabel2 = CaptionLabel(f"       ", self)
        self.NoneLabel2.setAlignment(Qt.AlignVCenter) # 垂直居中        

        info = input_folder_button_text(self.tra)
        self.selectButton = PrimaryPushButton(FluentIcon.FOLDER_ADD,info,self) # 创建主操作按钮
        self.selectButton.clicked.connect(self._select_folder) # 连接按钮点击事件到选择文件夹方法

        # 命中计数标签
        self.hitCountLabel = CaptionLabel(f"Hits: {self.hit_count}", self)
        self.hitCountLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter) # 右对齐，垂直居中

        # 使用 Stretch 来实现按钮居中和标签靠右
        bottom_bar_layout.addWidget(self.NoneLabel2)
        bottom_bar_layout.addStretch(1) # 左侧弹性空间
        bottom_bar_layout.addWidget(self.selectButton) # 中间按钮
        bottom_bar_layout.addStretch(1) # 右侧弹性空间
        bottom_bar_layout.addWidget(self.hitCountLabel) # 靠右的标签


        # 水平布局,包含路径与占位标签
        path_bar_layout = QHBoxLayout() # 水平布局，包含显示标签和占位标签

        # 占位标签
        self.NoneLabel2 = CaptionLabel(f"       ", self)
        self.NoneLabel2.setAlignment(Qt.AlignVCenter) # 垂直居中       

        # 路径标签
        self.pathLabel = BodyLabel("NO PATH", self) 
        self.pathLabel.setAlignment(Qt.AlignCenter) # 文本居中对齐

        # 占位标签
        self.NoneLabel3 = CaptionLabel(f"       ", self)
        self.NoneLabel3.setAlignment(Qt.AlignRight | Qt.AlignVCenter) # 右对齐，垂直居中

        path_bar_layout.addWidget(self.NoneLabel2) 
        path_bar_layout.addStretch(1) # 左侧弹性空间
        path_bar_layout.addWidget(self.pathLabel) 
        path_bar_layout.addStretch(1) # 右侧弹性空间
        path_bar_layout.addWidget(self.NoneLabel3) # 靠右的标签

        # ===== 组装布局 =====
        layout.addWidget(flow_container)  # 添加包含信息块的流式布局容器
        layout.addStretch(1) # 添加弹性空间，将下方元素推到底部
        layout.addLayout(path_bar_layout)  # 添加路径显示标签
        layout.addLayout(bottom_bar_layout) # 添加包含按钮和计数标签的水平布局

    def _select_folder(self):
        """处理点击选择文件夹按钮的事件"""
        info = choose_input_folder_title(self.tra)
        folder_path = get_existing_directory(self, info, self.current_path)
        if folder_path:
            self.update_path(folder_path)
            button_center_global = self.selectButton.mapToGlobal(self.selectButton.rect().center())
            button_center_local = self.mapFromGlobal(button_center_global)

            self.show_fireworks(button_center_local, success=False, text_override=" Yes!") # 提供不同的文本

    def update_path(self, path: str):
        """更新当前路径，并更新界面显示"""
        self.current_path = path
        display_path = path if len(path) < 50 else f"...{path[-47:]}"
        info = self.tra("当前路径") + ": "
        self.pathLabel.setText(f"{info}{display_path}")
        self.pathLabel.setToolTip(path)
        self.folderDropped.emit(path)

    def get_hit_count(self) -> int:
        """返回当前的命中次数"""
        return self.hit_count

    def paintEvent(self, event):
        """自定义绘制事件，用于绘制拖拽区域的虚线/实线边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1) # 获取控件区域，并向内调整1像素，避免边框被边缘切割
        radius = 15.0 # 圆角半径

        pen = QPen(self.border_color, 2) # 创建画笔，线宽为2
        if self.is_dragging: # 如果当前正有文件拖拽进入区域
            pen.setStyle(Qt.SolidLine) # 设置为实线样式
            pen.setColor(QColor("#aaaaff")) # 设置边框颜色为浅蓝色 (表示可接收)
            #pen.setColor(QColor("#5CBE88")) # 备选绿色
        else: # 如果没有拖拽操作
            pen.setStyle(Qt.DashLine) # 设置为虚线样式
            pen.setColor(QColor("#AAAAAA")) # 设置边框颜色为灰色
        painter.setPen(pen) # 应用画笔设置
        painter.setBrush(Qt.NoBrush) # 不填充背景

        path = QPainterPath() # 创建绘制路径
        path.addRoundedRect(QRectF(rect), radius, radius) # 添加带圆角的矩形到路径
        painter.drawPath(path) # 绘制路径 (即边框)

    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        mime_data = event.mimeData() # 获取拖拽数据
        if mime_data.hasUrls(): # 检查是否包含 URL (通常是文件/文件夹路径)
            valid_drop = False # 标记是否有有效的可拖放项
            for url in mime_data.urls():
                if url.isLocalFile(): # 检查是否是本地文件 URL
                    local_path = url.toLocalFile() # 转换为本地路径字符串
                    if os.path.exists(local_path): # 确保路径实际存在
                         valid_drop = True # 找到至少一个有效路径
                         break # 只要有一个有效路径即可接受拖拽

            if valid_drop: # 如果存在有效路径
                event.acceptProposedAction() # 接受拖拽操作 (鼠标指针会改变)
                self.is_dragging = True # 标记进入拖拽状态

                # 随机选择一个目标信息块并显示准心
                if self.info_blocks : # 确保有信息块存在
                    # --- 先重置之前的目标块（如果有的话），防止同时显示多个准心 ---
                    if self.target_info_block:
                        self.target_info_block.set_display_mode("text") # 恢复为文本模式
                        self.target_info_block = None # 清除引用

                    # 随机选择一个新的目标信息块
                    self.target_info_block = random.choice(self.info_blocks)
                    # 将选中的目标块设置为 'aim' 模式
                    self.target_info_block.set_display_mode("aim") # <-- 这里触发准心显示

                self.update() # 请求重新绘制整个区域（边框变为实线，目标块显示准心）
            else:
                event.ignore() # 如果拖拽内容无效（例如，网页链接），则忽略
        else:
            event.ignore() # 如果拖拽数据不含 URL，忽略

    def dragLeaveEvent(self, event):
        """处理拖拽离开事件"""
        self.is_dragging = False # 标记拖拽离开状态

        # 重置目标信息块为文本模式
        if self.target_info_block:
            self.target_info_block.set_display_mode("text") # <-- 恢复文本显示
            self.target_info_block = None # 清除目标块引用
        self.update() # 请求重新绘制整个区域

    def dropEvent(self, event):
        """处理放下事件"""
        mime_data = event.mimeData()
        dropped_path = None
        hit_target = False # 重置命中标记

        if mime_data.hasUrls():
            folder_path = None
            first_valid_path = None
            for url in mime_data.urls():
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    if os.path.exists(local_path):
                        if first_valid_path is None:
                            first_valid_path = local_path
                        if os.path.isdir(local_path):
                            folder_path = local_path
                            break

            if folder_path:
                dropped_path = folder_path
            elif first_valid_path:
                if os.path.isfile(first_valid_path):
                    dropped_path = os.path.dirname(first_valid_path)
                else:
                    dropped_path = first_valid_path

            self.is_dragging = False # 拖拽结束

            if dropped_path and os.path.exists(dropped_path):
                event.acceptProposedAction()

                if self.target_info_block:
                    drop_pos = event.pos()
                    target_rect = self.target_info_block.geometry()
                    if target_rect.contains(drop_pos):
                        hit_target = True

                        self.hit_count += 1
                        self.hitCountLabel.setText(f"Hits: {self.hit_count}")

                if self.target_info_block:
                    self.target_info_block.set_display_mode("text")
                    self.target_info_block = None

                self.update_path(dropped_path)
                self.show_fireworks(event.pos(), success=hit_target) # 使用 hit_target 决定烟花效果

            else:
                event.ignore()
                if self.target_info_block:
                    self.target_info_block.set_display_mode("text")
                    self.target_info_block = None

            self.update() # 确保界面重绘

    def show_fireworks(self, position, success=False, text_override=None):
        """在指定位置显示一个短暂的反馈标签（"烟花"效果）"""
        if self.fireworks_label:
            self.fireworks_label.deleteLater()

        if text_override:
            effect_text = random.choice(self.NON_SUCCESS_ICONS) + text_override
        elif success:
            effect_text = "💥 Hit!"
        else:
            effect_text = random.choice(self.NON_SUCCESS_ICONS) + " OK"

        self.fireworks_label = CaptionLabel(effect_text, self)
        self.fireworks_label.setStyleSheet(f"""
            QWidget {{
                font-size: 24px;
                font-weight: bold;
                background-color: rgba(255, 255, 255, 190); /* 半透明白色背景 */
                border: 1px solid {'#4CAF50' if success else '#AAAAAA'}; /* 边框颜色 */
                border-radius: 8px;
                padding: 8px 12px;
                qproperty-alignment: 'AlignCenter';
            }}""")
        self.fireworks_label.adjustSize()

        label_pos = QPoint(position.x() - self.fireworks_label.width() // 2,
                           position.y() - self.fireworks_label.height() // 2)
        label_pos.setX(max(0, min(label_pos.x(), self.width() - self.fireworks_label.width())))
        label_pos.setY(max(0, min(label_pos.y(), self.height() - self.fireworks_label.height())))

        self.fireworks_label.move(label_pos)
        self.fireworks_label.show()
        self.fireworks_label.raise_()

        QTimer.singleShot(1200, self.hide_fireworks)


    def hide_fireworks(self):
        """隐藏并准备删除反馈标签"""
        if self.fireworks_label:
            self.fireworks_label.hide() # 隐藏标签
            self.fireworks_label.deleteLater() # 标记以便稍后安全删除
            self.fireworks_label = None # 清除引用


class GameDropCard(CardWidget): 
    """一个通用的卡片式组件，内部包含 DragDropArea，用于提供拖拽功能和命中计数"""

    pathChanged = pyqtSignal(str) # 当内部拖拽区域路径变化时，转发该信号

    # 修改构造函数，接收并传递 initial_hit_count
    def __init__(self, init=None, path_changed=None, initial_hit_count: int = 0, parent=None):
        super().__init__(parent) # 调用父类 CardWidget 的构造函数

        self.setMinimumHeight(350)# 设置最小高度

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(16, 16, 16, 16) # 设置卡片内边距
        self.mainLayout.setSpacing(10) # 设置布局内控件间距

        # 创建核心的拖拽区域，传递 initial_hit_count
        self.dragDropArea = DragDropArea(self, initial_hit_count=initial_hit_count)
        self.dragDropArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.mainLayout.addWidget(self.dragDropArea)

        self.dragDropArea.folderDropped.connect(self._handle_path_change)
        if path_changed:
            self.pathChanged.connect(lambda path: path_changed(self, path))

        if init:
            self.setPath(init)

    def setPath(self, path: str):
        """设置卡片内拖拽区域显示的路径的标准方法"""
        self.dragDropArea.update_path(path)

    def getPath(self) -> str:
        """获取卡片内拖拽区域当前设置的路径"""
        return self.dragDropArea.current_path

    def getHitCount(self) -> int:
        """获取当前的命中次数"""
        return self.dragDropArea.get_hit_count()

    def _handle_path_change(self, path: str):
        """内部处理函数，当中拖拽区域路径变化时，发射本控件的 pathChanged 信号"""
        self.pathChanged.emit(path) # 发射 pathChanged 信号，将路径传递出去
