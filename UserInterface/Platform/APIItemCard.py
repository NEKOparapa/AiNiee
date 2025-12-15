import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    CardWidget, CaptionLabel, StrongBodyLabel, BodyLabel,
    RoundMenu, Action, FluentIcon,
    IconWidget, DropDownPushButton, themeColor
)

from ModuleFolders.Base.Base import Base

class APIItemCard(CardWidget, Base):
    """接口小卡片组件"""
    
    # 静态缓存字典，防止重复读取IO
    _icon_cache = {} 
    
    testClicked = pyqtSignal(str)
    activateChanged = pyqtSignal(str, str) 
    editClicked = pyqtSignal(str)
    editLimitClicked = pyqtSignal(str)
    editArgsClicked = pyqtSignal(str)
    deleteClicked = pyqtSignal(str)
    
    def __init__(self, api_tag: str, api_data: dict, activate_status: str = None, parent=None):
        super().__init__(parent)
        
        self.api_tag = api_tag
        self.api_data = api_data
        self.activate_status = activate_status
        
        self.setFixedSize(340, 90) 
        self.setBorderRadius(8)
        
        self._build_ui()
        self._update_status_display()
        
    def _build_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 10, 16, 10)
        self.main_layout.setSpacing(12)
        
        # 使用缓存加载图标
        icon_name = self.api_data.get("icon", "custom")
        if icon_name not in self._icon_cache:
            # 如果缓存里没有，才去加载
            file_name = icon_name + ".png"
            icon_path = os.path.join(".", "Resource", "platforms", "Icon", file_name)
            if os.path.exists(icon_path):
                self._icon_cache[icon_name] = QIcon(icon_path)
            else:
                # 默认图标也可以缓存
                self._icon_cache[icon_name] = FluentIcon.ROBOT

        self.icon_widget = IconWidget(self._icon_cache[icon_name], self)
        self.icon_widget.setFixedSize(40, 40)
        self.main_layout.addWidget(self.icon_widget)
        
        # 2. 中间信息
        self.info_container = QWidget()
        self.info_layout = QVBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(2)
        self.info_layout.setAlignment(Qt.AlignVCenter)
        
        self.name_label = StrongBodyLabel(self.api_data.get("name", ""))
        self.info_layout.addWidget(self.name_label)
        
        model_name = self.api_data.get("model", "Unknown")
        if len(model_name) > 18: model_name = model_name[:16] + "..."
        self.model_label = CaptionLabel(model_name)
        self.model_label.setStyleSheet("color: #707070;")
        self.info_layout.addWidget(self.model_label)
        
        self.status_label = BodyLabel()
        font = self.status_label.font()
        font.setBold(True)
        font.setPointSize(9)
        self.status_label.setFont(font)
        self.info_layout.addWidget(self.status_label)
        
        self.main_layout.addWidget(self.info_container, 1)
        
        # 3. 右侧操作区
        self.right_container = QWidget()
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)
        self.right_layout.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        
        # 激活按钮
        self.activate_btn = DropDownPushButton(self.tra("激活"), self)
        self.activate_btn.setFixedWidth(95)
        self.activate_btn.setFixedHeight(30)
        
        activate_menu = RoundMenu(parent=self)
        action_translate = Action(FluentIcon.EXPRESSIVE_INPUT_ENTRY, self.tra("设为翻译接口"), self)
        action_translate.triggered.connect(lambda: self._set_activate_status("translate"))
        activate_menu.addAction(action_translate)
        
        action_polish = Action(FluentIcon.BRUSH, self.tra("设为润色接口"), self)
        action_polish.triggered.connect(lambda: self._set_activate_status("polish"))
        activate_menu.addAction(action_polish)
        
        activate_menu.addSeparator()
        action_deactivate = Action(FluentIcon.CANCEL, self.tra("取消激活接口"), self)
        action_deactivate.triggered.connect(lambda: self._set_activate_status(None))
        activate_menu.addAction(action_deactivate)
        
        self.activate_btn.setMenu(activate_menu)
        self.right_layout.addWidget(self.activate_btn)
        
        # 设置按钮
        self.more_btn = DropDownPushButton(self.tra("设置"), self)
        self.more_btn.setFixedWidth(95)
        self.more_btn.setFixedHeight(30)
        
        more_menu = RoundMenu(parent=self)
        more_menu.addAction(Action(FluentIcon.SEND, self.tra("测试接口"), triggered=lambda: self.testClicked.emit(self.api_tag)))
        more_menu.addSeparator()
        more_menu.addAction(Action(FluentIcon.EDIT, self.tra("编辑接口"), triggered=lambda: self.editClicked.emit(self.api_tag)))
        more_menu.addAction(Action(FluentIcon.SCROLL, self.tra("调整限速"), triggered=lambda: self.editLimitClicked.emit(self.api_tag)))
        more_menu.addAction(Action(FluentIcon.DEVELOPER_TOOLS, self.tra("调整参数"), triggered=lambda: self.editArgsClicked.emit(self.api_tag)))
        more_menu.addSeparator()
        more_menu.addAction(Action(FluentIcon.DELETE, self.tra("删除接口"), triggered=lambda: self.deleteClicked.emit(self.api_tag)))
        
        self.more_btn.setMenu(more_menu)
        self.right_layout.addWidget(self.more_btn)
        
        self.main_layout.addWidget(self.right_container)

    def _set_activate_status(self, status: str):
        if self.activate_status == status:
            return
        self.activate_status = status
        self._update_status_display()
        self.activateChanged.emit(self.api_tag, status if status else "")
        
    def _update_status_display(self):
        t_color = themeColor()
        color_str = t_color.name()
        
        if self.activate_status == "translate":
            self.status_label.setText(self.tra("翻译激活中"))
            self.status_label.setStyleSheet(f"color: {color_str};")
            self.status_label.show()
        elif self.activate_status == "polish":
            self.status_label.setText(self.tra("润色激活中"))
            self.status_label.setStyleSheet(f"color: {color_str};")
            self.status_label.show()
        else:
            self.status_label.setText("")
            self.status_label.hide()

    def update_info(self, api_data: dict):
        self.api_data = api_data
        self.name_label.setText(api_data.get("name", ""))
        model_name = api_data.get("model", "")
        if len(model_name) > 18: model_name = model_name[:16] + "..."
        self.model_label.setText(model_name if model_name else self.tra("未设置"))
        
    def set_activate_status(self, status: str):
        self.activate_status = status
        self._update_status_display()