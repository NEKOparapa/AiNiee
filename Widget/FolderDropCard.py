import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QSizePolicy
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QPainterPath
from PyQt5.QtCore import QRect, Qt, pyqtSignal
from qfluentwidgets import BodyLabel, CardWidget,  FluentIcon, PrimaryPushButton

from Base.Base import Base

class InfoBlockWidget(QWidget):
    def __init__(self, text, color=QColor("#E0E0E0"), parent=None):
        super().__init__(parent)
        self.text = text
        self.base_color = QColor(color)
        self.fold_size = 15
        self.corner_radius = 10.0
        self.alpha_level = 170
        self.setMinimumSize(95, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.default_font = QFont("Microsoft YaHei", 9)
        if QFont(self.default_font).family() != "Microsoft YaHei":
             self.default_font = QFont() # Use system default
             self.default_font.setPointSize(9)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        content_width = rect.width() - self.fold_size

        # 设置颜色
        bg_color = QColor(self.base_color)
        bg_color.setAlpha(self.alpha_level)
        fold_highlight = self.base_color.lighter(120)
        fold_highlight.setAlpha(min(255, self.alpha_level + 15))
        border_color = self.base_color.darker(130)
        border_color.setAlpha(self.alpha_level)

        # 绘制主路径
        path = QPainterPath()
        path.moveTo(self.corner_radius, 0)
        path.lineTo(content_width, 0)
        path.lineTo(content_width, self.fold_size)
        path.lineTo(rect.width(), self.fold_size)
        path.lineTo(rect.width(), rect.height() - self.corner_radius)
        path.arcTo(rect.width() - 2*self.corner_radius, rect.height() - 2*self.corner_radius, 
                  2*self.corner_radius, 2*self.corner_radius, 0, -90)
        path.lineTo(self.corner_radius, rect.height())
        path.arcTo(0, rect.height() - 2*self.corner_radius, 
                  2*self.corner_radius, 2*self.corner_radius, 270, -90)
        path.lineTo(0, self.corner_radius)
        path.arcTo(0, 0, 2*self.corner_radius, 2*self.corner_radius, 180, -90)
        path.closeSubpath()
        painter.fillPath(path, bg_color)

        # 绘制折角
        fold_path = QPainterPath()
        fold_path.moveTo(content_width, 0)
        fold_path.lineTo(rect.width(), self.fold_size)
        fold_path.lineTo(content_width, self.fold_size)
        fold_path.closeSubpath()
        painter.fillPath(fold_path, fold_highlight)

        # 绘制边框
        painter.setPen(QPen(border_color, 1))
        painter.drawPath(path)
        painter.drawLine(content_width, self.fold_size, rect.width(), self.fold_size)
        painter.drawLine(content_width, 0, content_width, self.fold_size)

        # 绘制文本
        h_padding = 5 + int(self.corner_radius / 2)
        v_padding = 5 + int(self.corner_radius / 2)
        content_rect = QRect(0, 0, content_width, rect.height())
        draw_rect = content_rect.adjusted(h_padding, v_padding, 0, -v_padding)
        painter.setPen(Qt.black)
        painter.setFont(self.default_font)
        painter.drawText(draw_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)

class DragDropArea(Base,QWidget):
    pathDropped = pyqtSignal(str) # 文件路径改变信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.current_path = ""
        self.is_dragging = False
        self.border_color = QColor("#AAAAAA")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # 信息块区域
        flow_container = QWidget()
        info_layout = QHBoxLayout(flow_container)
        #info_layout.setHorizontalSpacing(15)
        #info_layout.setVerticalSpacing(15)

        info_1 = self.tra("书籍")
        info_2 = self.tra("文档")
        info_3 = self.tra("字幕")
        info_5 = self.tra("游戏")
        info_6 = self.tra("数据文件")
        info_7 = self.tra("复杂文档")
        info_8 = self.tra("工程文件")

        # 简化信息块创建
        block_info = [
            (f"{info_1}\n Epub\n TXT", "#AED6F1"),
            (f"{info_2}\n Docx\n MD", "#A9DFBF"),
            (f"{info_3}\n Srt\n Ass\n Vtt\n Lrc", "#FAD7A0"),
            (f"{info_5}\n Renpy\n VNText \n RPGmaker", "#AFEEEE"),
            (f"{info_6}\n Po \n I18Next \n ParaTranz", "#F08080"),
            (f"{info_7}\n PDF\n DOC", "#E6E6FA"),
            (f"{info_8}\n .trans", "#FFFACD"),
        ]

        # 添加弹簧
        info_layout.addStretch(1)
        # 创建信息块
        self.info_blocks = [InfoBlockWidget(text, color) for text, color in block_info]
        for block in self.info_blocks:
            info_layout.addWidget(block)
        # 添加弹簧
        info_layout.addStretch(1)

        # 底部按钮区域
        bottom_layout = QHBoxLayout()
        self.satr_button = PrimaryPushButton(FluentIcon.PLAY, self.tra("直接读取"), self)
        self.satr_button.clicked.connect(self._get_folder)
        self.selectButton = PrimaryPushButton(FluentIcon.FOLDER_ADD, self.tra("拖拽/选择输入文件夹"), self)
        self.selectButton.clicked.connect(self._select_folder)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.satr_button)
        bottom_layout.addWidget(self.selectButton)
        bottom_layout.addStretch(1)

        # 路径显示区域
        path_layout = QHBoxLayout()
        self.pathLabel = BodyLabel("NO PATH", self)
        self.pathLabel.setAlignment(Qt.AlignCenter)
        path_layout.addStretch(1)
        path_layout.addWidget(self.pathLabel)
        path_layout.addStretch(1)

        # 组装布局
        layout.addWidget(flow_container)
        layout.addStretch(1)
        layout.addLayout(path_layout)
        layout.addLayout(bottom_layout)

    def _get_folder(self):
        folder_path = self.current_path
        if folder_path:
            self.update_path(folder_path)

    def _select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, self.tra("选择文件夹"))
        if folder_path:
            self.update_path(folder_path)

    def update_path(self, path: str, emit_signal: bool = True): 
        self.current_path = path
        display_path = path if len(path) < 50 else f"...{path[-47:]}"
        info = self.tra("当前路径")
        self.pathLabel.setText(f"{info}: {display_path}")
        self.pathLabel.setToolTip(path)
        if emit_signal: # 只有在需要时才发射信号
            self.pathDropped.emit(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        pen = QPen(self.border_color, 2)
        if self.is_dragging:
            pen.setStyle(Qt.SolidLine)
            pen.setColor(QColor("#aaaaff"))
        else:
            pen.setStyle(Qt.DashLine)
        
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 15, 15)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and os.path.exists(url.toLocalFile()):
                    event.acceptProposedAction()
                    self.is_dragging = True
                    self.update()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.is_dragging = False
        self.update()

    def dropEvent(self, event):
        self.is_dragging = False
        self.update()
        
        if not event.mimeData().hasUrls():
            return

        # 获取所有有效本地路径
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile() and os.path.exists(url.toLocalFile())]

        if not paths:
            return

        # 根据路径数量进行判断
        if len(paths) == 1:
            # 拖入的是单个文件或文件夹
            single_path = paths[0]

            # 如果是文件夹，则直接使用文件路径
            if os.path.isdir(single_path):
                path_to_use = single_path

            # 如果是文件，获取其所在的父目录
            else:
                path_to_use = single_path # 给单文件夹拖拽功能支持用
                #path_to_use =  os.path.dirname(single_path)

            # 更新路径并发射信号
            self.update_path(path_to_use)
        else:
            # 拖入的是多个文件/文件夹,获取它们共同的父目录
            first_path = paths[0]
            if os.path.isdir(first_path):
                 # 如果用户拖动多个项，其中第一个是文件夹，
                 parent_dir = os.path.dirname(first_path)
            else: # 是文件
                 parent_dir = os.path.dirname(first_path)
            
            self.update_path(parent_dir)

class FolderDropCard(Base,CardWidget):
    pathChanged = pyqtSignal(str)

    def __init__(self, init=None, path_changed=None, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(350)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        self.dragDropArea = DragDropArea(self)
        self.dragDropArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.dragDropArea)
        
        # 连接信号
        self.dragDropArea.pathDropped.connect(self.pathChanged)
        if path_changed:
            self.pathChanged.connect(path_changed)
        
        # 初始化时设置路径
        if init:
            self.setPath(init)

    def setPath(self, path: str):
        # 初始化设置路径时，不发射信号
        self.dragDropArea.update_path(path, emit_signal=False)

    def getPath(self) -> str:
        return self.dragDropArea.current_path