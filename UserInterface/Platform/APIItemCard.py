import os

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    CardWidget, CaptionLabel, StrongBodyLabel,
    RoundMenu, Action, FluentIcon,
    IconWidget, PillPushButton, DropDownToolButton
)

from ModuleFolders.Base.Base import Base

class APIItemCard(CardWidget, Base):
    """接口卡片组件"""
    
    # 信号
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
        self.activate_status = activate_status  # "translate", "polish", or None
        
        self.setBorderRadius(8)
        self.setFixedHeight(80)
        
        self._build_ui()
        self._update_activate_buttons()
        
    def _build_ui(self):
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 12, 16, 12)
        self.hbox.setSpacing(12)
        
        # 左侧：图标
        icon_name = self.api_data.get("icon", "custom") + ".png"
        icon_path = os.path.join(".", "Resource", "platforms", "Icon", icon_name)
        
        if os.path.exists(icon_path):
            self.icon_widget = IconWidget(QIcon(icon_path), self)
        else:
            self.icon_widget = IconWidget(FluentIcon.ROBOT, self)
        self.icon_widget.setFixedSize(40, 40)
        self.hbox.addWidget(self.icon_widget)
        
        # 中间：名称和接口地址+模型信息
        self.info_container = QFrame()
        self.info_layout = QVBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(4)
        
        self.name_label = StrongBodyLabel(self.api_data.get("name", ""))
        self.info_layout.addWidget(self.name_label)
        
        # 拼接 URL 和 模型信息
        api_url = self.api_data.get("api_url", "")
        display_url = api_url if api_url else self.tra("无接口地址")
        
        model_name = self.api_data.get("model", "")
        if model_name:
            display_text = f"URL: {display_url}  ||  Model:  {model_name}"
        else:
            display_text = display_url
            
        self.info_label = CaptionLabel(display_text)
        
        self.info_label.setStyleSheet("color: #888;")
        self.info_layout.addWidget(self.info_label)
        
        self.hbox.addWidget(self.info_container, 1)
        
        # 激活按钮区域
        self.activate_container = QWidget()
        self.activate_layout = QHBoxLayout(self.activate_container)
        self.activate_layout.setContentsMargins(0, 0, 0, 0)
        self.activate_layout.setSpacing(8)
        
        # 翻译激活按钮
        self.translate_btn = PillPushButton(self.tra("翻译"))
        self.translate_btn.setCheckable(True)
        self.translate_btn.setFixedHeight(32)
        self.translate_btn.setIcon(FluentIcon.EXPRESSIVE_INPUT_ENTRY)
        self.translate_btn.setIconSize(QSize(14, 14))
        self.translate_btn.setToolTip(self.tra("点击激活/取消翻译任务"))
        self.translate_btn.clicked.connect(self._on_translate_clicked)
        self.activate_layout.addWidget(self.translate_btn)
        
        # 润色激活按钮
        self.polish_btn = PillPushButton(self.tra("润色"))
        self.polish_btn.setCheckable(True)
        self.polish_btn.setFixedHeight(32)
        self.polish_btn.setIcon(FluentIcon.BRUSH)
        self.polish_btn.setIconSize(QSize(14, 14))
        self.polish_btn.setToolTip(self.tra("点击激活/取消润色任务"))
        self.polish_btn.clicked.connect(self._on_polish_clicked)
        self.activate_layout.addWidget(self.polish_btn)
        
        self.hbox.addWidget(self.activate_container)
        
        # 更多按钮
        self.more_btn = DropDownToolButton()
        self.more_btn.setIcon(FluentIcon.MORE)
        
        more_menu = RoundMenu(parent=self)
        more_menu.addAction(Action(
            FluentIcon.SEND, 
            self.tra("测试接口"),
            triggered=lambda: self.testClicked.emit(self.api_tag)
        ))
        more_menu.addSeparator()
        more_menu.addAction(Action(
            FluentIcon.EDIT, 
            self.tra("编辑接口"),
            triggered=lambda: self.editClicked.emit(self.api_tag)
        ))
        more_menu.addAction(Action(
            FluentIcon.SCROLL, 
            self.tra("编辑限速"),
            triggered=lambda: self.editLimitClicked.emit(self.api_tag)
        ))
        more_menu.addAction(Action(
            FluentIcon.DEVELOPER_TOOLS, 
            self.tra("编辑参数"),
            triggered=lambda: self.editArgsClicked.emit(self.api_tag)
        ))
        more_menu.addSeparator()
        more_menu.addAction(Action(
            FluentIcon.DELETE, 
            self.tra("删除接口"),
            triggered=lambda: self.deleteClicked.emit(self.api_tag)
        ))
        self.more_btn.setMenu(more_menu)
        self.hbox.addWidget(self.more_btn)
    
    def _on_translate_clicked(self):
        """处理翻译按钮点击"""
        # 如果当前是翻译激活状态，则取消；否则激活翻译
        if self.activate_status == "translate":
            self._set_activate_status(None)
        else:
            self._set_activate_status("translate")
    
    def _on_polish_clicked(self):
        """处理润色按钮点击"""
        # 如果当前是润色激活状态，则取消；否则激活润色
        if self.activate_status == "polish":
            self._set_activate_status(None)
        else:
            self._set_activate_status("polish")
        
    def _set_activate_status(self, status: str):
        """设置激活状态并发出信号"""
        self.activate_status = status
        self._update_activate_buttons()
        self.activateChanged.emit(self.api_tag, status if status else "")
        
    def _update_activate_buttons(self):
        """更新激活按钮的选中状态"""
        # 阻止信号避免循环触发
        self.translate_btn.blockSignals(True)
        self.polish_btn.blockSignals(True)
        
        self.translate_btn.setChecked(self.activate_status == "translate")
        self.polish_btn.setChecked(self.activate_status == "polish")
        
        self.translate_btn.blockSignals(False)
        self.polish_btn.blockSignals(False)
        
    def update_info(self, api_data: dict):
        """更新卡片信息"""
        self.api_data = api_data
        self.name_label.setText(api_data.get("name", ""))
        
        api_url = api_data.get("api_url", "")
        display_url = api_url if api_url else self.tra("未设置接口地址")
        
        model_name = api_data.get("model", "")
        if model_name:
            display_text = f"URL: {display_url}  ||  Model:  {model_name}"
        else:
            display_text = display_url
            
        self.info_label.setText(display_text)
        
    def set_activate_status(self, status: str):
        """外部设置激活状态（不触发信号）"""
        self.activate_status = status
        self._update_activate_buttons()