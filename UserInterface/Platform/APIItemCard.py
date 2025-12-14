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
        
        # 适当增加卡片宽度以容纳新的按钮文本
        self.setFixedSize(340, 90) 
        self.setBorderRadius(8)
        
        self._build_ui()
        self._update_status_display()
        
    def _build_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 10, 16, 10)
        self.main_layout.setSpacing(12)
        
        # 1. 左侧图标
        icon_name = self.api_data.get("icon", "custom") + ".png"
        icon_path = os.path.join(".", "Resource", "platforms", "Icon", icon_name)
        
        if os.path.exists(icon_path):
            self.icon_widget = IconWidget(QIcon(icon_path), self)
        else:
            self.icon_widget = IconWidget(FluentIcon.ROBOT, self)
        
        self.icon_widget.setFixedSize(40, 40)
        self.main_layout.addWidget(self.icon_widget)
        
        # 2. 中间信息 (名称 + 模型 + 状态文本)
        self.info_container = QWidget()
        self.info_layout = QVBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(2)
        self.info_layout.setAlignment(Qt.AlignVCenter)
        
        # 接口名称
        self.name_label = StrongBodyLabel(self.api_data.get("name", ""))
        self.info_layout.addWidget(self.name_label)
        
        # 模型名称
        model_name = self.api_data.get("model", "Unknown")
        if len(model_name) > 18: model_name = model_name[:16] + "..."
        self.model_label = CaptionLabel(model_name)
        self.model_label.setStyleSheet("color: #707070;")
        self.info_layout.addWidget(self.model_label)
        
        # 新增：状态显示文本 (默认隐藏，激活时显示)
        self.status_label = BodyLabel()
        font = self.status_label.font()
        font.setBold(True)
        font.setPointSize(9) #稍微小一点
        self.status_label.setFont(font)
        self.info_layout.addWidget(self.status_label)
        
        self.main_layout.addWidget(self.info_container, 1)
        
        # 3. 右侧操作区
        self.right_container = QWidget()
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)
        self.right_layout.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        
        # 按钮 1: 激活接口 (下拉菜单)
        self.activate_btn = DropDownPushButton(FluentIcon.POWER_BUTTON, self.tra("激活"), self)
        self.activate_btn.setFixedWidth(100) # 固定宽度保持整齐
        self.activate_btn.setFixedHeight(30)
        
        # 构建激活菜单
        activate_menu = RoundMenu(parent=self)
        
        # 设为翻译接口
        action_translate = Action(FluentIcon.EDIT, self.tra("设为翻译接口"), self)
        action_translate.triggered.connect(lambda: self._set_activate_status("translate"))
        activate_menu.addAction(action_translate)
        
        # 设为润色接口
        action_polish = Action(FluentIcon.EDIT, self.tra("设为润色接口"), self)
        action_polish.triggered.connect(lambda: self._set_activate_status("polish"))
        activate_menu.addAction(action_polish)
        
        # 取消激活 (可选，方便用户关闭)
        activate_menu.addSeparator()
        action_deactivate = Action(FluentIcon.CANCEL, self.tra("取消激活接口"), self)
        action_deactivate.triggered.connect(lambda: self._set_activate_status(None))
        activate_menu.addAction(action_deactivate)
        
        self.activate_btn.setMenu(activate_menu)
        self.right_layout.addWidget(self.activate_btn)
        
        # 按钮 2: 更多设置 (下拉菜单)
        self.more_btn = DropDownPushButton(FluentIcon.MORE, self.tra("设置"), self)
        self.more_btn.setFixedWidth(100)
        self.more_btn.setFixedHeight(30)
        
        # 构建更多菜单
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
        """处理内部状态变更并发送信号"""
        # 如果点击相同的状态，视为取消（可选逻辑，这里按菜单逻辑是明确选择）
        if self.activate_status == status:
            return
            
        self.activate_status = status
        self._update_status_display()
        self.activateChanged.emit(self.api_tag, status if status else "")
        
    def _update_status_display(self):
        """更新UI显示状态"""
        t_color = themeColor()
        color_str = t_color.name() # 获取当前主题色 hex 字符串
        
        if self.activate_status == "translate":
            self.status_label.setText(self.tra("翻译激活中"))
            self.status_label.setStyleSheet(f"color: {color_str};")
            self.status_label.show()
            # 可以选择高亮激活按钮，或者只靠文字提示
        elif self.activate_status == "polish":
            self.status_label.setText(self.tra("润色激活中"))
            self.status_label.setStyleSheet(f"color: {color_str};")
            self.status_label.show()
        else:
            self.status_label.setText("")
            self.status_label.hide()

    def update_info(self, api_data: dict):
        """更新卡片基础信息"""
        self.api_data = api_data
        self.name_label.setText(api_data.get("name", ""))
        model_name = api_data.get("model", "")
        if len(model_name) > 18: model_name = model_name[:16] + "..."
        self.model_label.setText(model_name if model_name else self.tra("未设置"))
        
    def set_activate_status(self, status: str):
        """外部调用设置状态（例如被其他卡片顶掉时）"""
        self.activate_status = status
        self._update_status_display()