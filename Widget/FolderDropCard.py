import os

from PyQt5.QtWidgets import (QSizePolicy, QVBoxLayout,  QHBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QObject, QTimer
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent

from qfluentwidgets import (CardWidget, StrongBodyLabel, BodyLabel)


# 改进点：亮暗主题颜色区别不大，需要两套和UI风格更加和谐的颜色方案
# 改进点：初始化展示软件支持的各种文件类型
# 改进点：当打开自动设置输出文件夹时，自动显示输出文件夹的路径，但会耦合
# 改进点：中间加一个按钮，点击后可以打开文件夹，并且一样可以设置输出路径
# 改进点：监听主题变化，自动更新颜色
class FolderDropLabel(BodyLabel):
    """
    一个自定义QLabel，用于接收拖放的文件夹。
    - 显示圆角虚线边框（根据主题调整颜色）。
    - 垂直居中文本。
    - 接收文件夹或文件拖放，提取文件夹路径并显示。
    - 发射包含文件夹路径的信号。
    """
    pathDropped = pyqtSignal(str)
    pathChanged = pyqtSignal(str)

    def __init__(self, prompt_text="将文件夹拖拽到此处", parent=None):
        super().__init__(parent)
        self._prompt_text = prompt_text
        self._current_path = ""
        self.setText(self._prompt_text)
        self.setWordWrap(True) # 允许换行
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 设置自动填充
        self.setAlignment(Qt.AlignCenter) # 垂直居中
        self.setMinimumHeight(290)# 设置最小高度
        self.setAcceptDrops(True) # 允许拖放
        self._update_style() # 初始设置样式

    def _update_style(self):
        """ 根据当前状态和路径更新样式 (考虑主题) """
        if self._current_path:
            self._set_style_state("success", self._current_path)
        else:
             self._set_style_state("idle")

    def _set_style_state(self, state="idle", path=""):
        """根据状态设置拖拽框的样式，但不再显示背景色和边框"""
        # 不再设置背景色和边框，只处理文本

        # --- 设置文本 ---
        if state == "success":
            # 不再显示路径，只保持原始提示文本
            self.setText(self._prompt_text)
            self.setToolTip(path)  # 仍然保留工具提示
        else:
            self.setText(self._prompt_text)
            self.setToolTip("")

    # 不再需要 _set_elided_text 方法，因为我们不再显示路径


    def reset(self):
        """恢复到初始提示文本和样式"""
        self._current_path = ""
        self._set_style_state("idle")
        self.pathChanged.emit("") # 发射路径改变信号

    def set_path(self, path: str):
        """外部设置路径并更新显示"""
        valid_path = path and os.path.exists(path) and os.path.isdir(path)
        if valid_path:
            self._current_path = path
            self._set_style_state("success", path)
            self.pathChanged.emit(path)
        else:
            # 如果设置的路径无效或为空，则重置
            # 只有在当前路径确实改变时才重置
            if self._current_path or not valid_path:
                 self.reset()


    def get_path(self) -> str:
        """获取当前设置的有效路径"""
        return self._current_path

    def dragEnterEvent(self, event: QDragEnterEvent):
        """处理拖放进入事件，检查是否为本地文件系统 URL"""
        if event.mimeData().hasUrls():
             # 检查是否至少有一个是本地文件系统 URL
            has_local_file = any(url.isLocalFile() for url in event.mimeData().urls())
            if has_local_file:
                event.acceptProposedAction()
                self._set_style_state("dragging")
                return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """处理拖动移动事件，更新样式"""
        event.acceptProposedAction() # 通常接受移动

    def dragLeaveEvent(self, event):
        """处理拖放离开事件，恢复到之前的状态"""
        # 恢复到之前的状态（idle 或 success）
        self._update_style()
        super().dragLeaveEvent(event)  # 调用父类方法以确保正常处理

    def dropEvent(self, event: QDropEvent):
        """处理拖放事件，提取文件夹路径并发射信号"""
        mime_data = event.mimeData()
        folder_path_to_emit = ""
        processed = False # 标记是否成功处理

        if mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                url: QUrl = urls[0] # 只处理第一个项
                if url.isLocalFile():
                    path = url.toLocalFile()
                    target_path = ""

                    if os.path.isdir(path):
                        target_path = path
                    elif os.path.isfile(path):
                        target_path = os.path.dirname(path)

                    if target_path and os.path.exists(target_path): # 再次确认目标路径存在
                        self._current_path = target_path
                        self._set_style_state("success", target_path) # 先设置样式再发射信号
                        folder_path_to_emit = target_path
                        event.acceptProposedAction()
                        # 延迟发射信号，确保UI先更新
                        QTimer.singleShot(0, lambda p=folder_path_to_emit: self.pathDropped.emit(p))
                        QTimer.singleShot(0, lambda p=folder_path_to_emit: self.pathChanged.emit(p))
                        processed = True

        if not processed:
            event.ignore()
            self._update_style() # 恢复到之前的状态

    def enterEvent(self, event):
        """处理鼠标进入事件，更新样式"""
        if self.acceptDrops() and not self._current_path: # 仅在 idle 状态下 hover
            self._set_style_state("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        """处理鼠标离开事件，恢复到之前的状态"""
        if self.acceptDrops():
            # 恢复到之前的状态
            self._update_style() # 恢复到 idle 或 success 状态
        super().leaveEvent(event)


class FolderDropCard(CardWidget):
    """
    一个包含标题、描述和文件夹拖放区域的卡片控件。
    """
    # 信号：当文件夹路径通过拖放成功设置时发出
    pathDropped = pyqtSignal(QObject, str)

    # 信号：当路径通过拖放或 set_path 改变时发出
    pathChanged = pyqtSignal(QObject, str)

    def __init__(self,title: str,prompt_text: str = "none",initial_path: str = None,path_dropped_callback=None, parent=None):
        super().__init__(parent)

        self.setBorderRadius(4)
        self.container = QHBoxLayout(self) #
        self.container.setContentsMargins(16, 16, 16, 16)

        self.vbox = QVBoxLayout()
        self.vbox.setAlignment(Qt.AlignCenter)  # 垂直居中

        # 标题标签
        self.title_label = StrongBodyLabel(title, self)
        self.title_label.setAlignment(Qt.AlignCenter)

        # 文件夹拖放标签
        self.folder_drop_label = FolderDropLabel(prompt_text, self)
        self.folder_drop_label.pathDropped.connect(
            lambda path: self.pathDropped.emit(self, path)
        )
        self.folder_drop_label.pathChanged.connect(
            lambda path: self.pathChanged.emit(self, path)
        )

        # 将标签添加到布局
        self.vbox.addWidget(self.title_label)
        self.vbox.addWidget(self.folder_drop_label)

        self.container.addLayout(self.vbox)

        # 使用 QTimer 延迟设置初始路径，确保 label 大小已确定
        if initial_path:
            QTimer.singleShot(0, lambda p=initial_path: self.set_path(p))

        if path_dropped_callback:
            # 这里连接的是 FolderDropCard 的 pathDropped 信号
            self.pathDropped.connect(path_dropped_callback) # 直接连接回调

    def set_path(self, path: str):
        self.folder_drop_label.set_path(path)

    def get_path(self) -> str:
        return self.folder_drop_label.get_path()

    def reset(self):
        self.folder_drop_label.reset()
