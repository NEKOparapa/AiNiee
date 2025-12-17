import os
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDrag, QIcon

from qfluentwidgets import (
    DropDownPushButton, RoundMenu, Action, FluentIcon
)

from ModuleFolders.Base.Base import Base

class APIItemCard(DropDownPushButton, Base):
    """
    可拖拽的接口按钮组件
    """
    
    # 静态缓存字典
    _icon_cache = {} 
    
    # 信号定义
    testClicked = pyqtSignal(str)
    editClicked = pyqtSignal(str)
    editLimitClicked = pyqtSignal(str)
    editArgsClicked = pyqtSignal(str)
    deleteClicked = pyqtSignal(str)

    def __init__(self, api_tag: str, api_data: dict, parent=None):
        super().__init__(parent=parent)
        self.api_tag = api_tag
        self.api_data = api_data
        
        # 1. 设置文本 (只显示接口名称)
        name = api_data.get("name", "None")
        self.setText(name) # 仅显示接口名称
        
        # 2. 设置图标
        self._setup_icon()
        
        # 3. 构建菜单
        self._build_menu()
        
        # 4. 样式调整
        self.setFixedWidth(180) # 根据文本长度调整宽度，可以适当缩小
        
    def _setup_icon(self):
        icon_name = self.api_data.get("icon", "custom")
        if icon_name not in self._icon_cache:
            file_name = icon_name + ".png"
            icon_path = os.path.join(".", "Resource", "platforms", "Icon", file_name)
            if os.path.exists(icon_path):
                self._icon_cache[icon_name] = QIcon(icon_path)
            else:
                self._icon_cache[icon_name] = FluentIcon.ROBOT
        
        self.setIcon(self._icon_cache[icon_name])

    def _build_menu(self):
        menu = RoundMenu(parent=self)
        
        menu.addAction(Action(FluentIcon.SEND, self.tra("测试接口"), 
                            triggered=lambda: self.testClicked.emit(self.api_tag)))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.EDIT, self.tra("编辑接口"), 
                            triggered=lambda: self.editClicked.emit(self.api_tag)))
        menu.addAction(Action(FluentIcon.SCROLL, self.tra("调整限速"), 
                            triggered=lambda: self.editLimitClicked.emit(self.api_tag)))
        menu.addAction(Action(FluentIcon.DEVELOPER_TOOLS, self.tra("调整参数"), 
                            triggered=lambda: self.editArgsClicked.emit(self.api_tag)))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, self.tra("删除接口"), 
                            triggered=lambda: self.deleteClicked.emit(self.api_tag)))
        
        self.setMenu(menu)

    def update_info(self, api_data: dict):
        """更新显示信息"""
        self.api_data = api_data
        name = api_data.get("name", "None")
        self.setText(name) # 仅显示接口名称

    def mouseMoveEvent(self, e):
        """实现拖拽逻辑"""
        # 只有按住左键移动才触发拖拽
        if e.buttons() != Qt.LeftButton:
            return

        # 只要移动了一点距离，就开始拖拽
        drag = QDrag(self)
        mime = QMimeData()
        # 将 api_tag 作为传递的数据
        mime.setText(self.api_tag)
        drag.setMimeData(mime)
        
        # 设置拖拽时的视觉反馈（使用按钮的截图）
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(e.pos())
        
        # 执行拖拽
        drag.exec_(Qt.MoveAction)
        
        super().mouseMoveEvent(e)
