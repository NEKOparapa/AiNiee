# Widget/APIItemCard.py
import os


from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from qfluentwidgets import (
    CardWidget, CaptionLabel, StrongBodyLabel,
    TransparentDropDownPushButton, RoundMenu, Action, FluentIcon,
    IconWidget,  PillPushButton, DropDownToolButton
)

from Base.Base import Base

class APIItemCard(CardWidget, Base):
    """接口卡片组件"""
    
    # 信号
    testClicked = pyqtSignal(str)  # 测试按钮点击，传递 api_tag
    activateChanged = pyqtSignal(str, str)  # 激活状态改变
    editClicked = pyqtSignal(str)  # 编辑接口
    editLimitClicked = pyqtSignal(str)  # 编辑限速
    editArgsClicked = pyqtSignal(str)  # 编辑参数
    deleteClicked = pyqtSignal(str)  # 删除接口
    
    def __init__(self, api_tag: str, api_data: dict, activate_status: str = None, parent=None):
        super().__init__(parent)
        
        self.api_tag = api_tag
        self.api_data = api_data
        self.activate_status = activate_status  # "translate", "polish", or None
        
        self.setBorderRadius(8)
        self.setFixedHeight(72)
        
        self._build_ui()
        self._update_activate_button()
        
    def _build_ui(self):
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 12, 16, 12)
        self.hbox.setSpacing(12)
        
        # 左侧：图标
        icon_name = self.api_data.get("icon", "LocalLLM") + ".png"
        icon_path = os.path.join(".", "Resource", "platforms", "Icon", icon_name)
        
        if os.path.exists(icon_path):
            self.icon_widget = IconWidget(QIcon(icon_path), self)
        else:
            self.icon_widget = IconWidget(FluentIcon.ROBOT, self)
        self.icon_widget.setFixedSize(36, 36)
        self.hbox.addWidget(self.icon_widget)
        
        # 中间左侧：名称和接口地址
        self.info_container = QFrame()
        self.info_layout = QVBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(2)
        
        # 名称
        self.name_label = StrongBodyLabel(self.api_data.get("name", ""))
        self.info_layout.addWidget(self.name_label)
        
        # 接口地址（替代原来的限速信息）
        api_url = self.api_data.get("api_url", "")
        display_url = api_url if api_url else self.tra("无接口地址")
        self.info_label = CaptionLabel(display_url)
        self.info_label.setStyleSheet("color: #888;")
        self.info_layout.addWidget(self.info_label)
        
        self.hbox.addWidget(self.info_container, 1)
        
        # 中间：激活状态标签
        self.status_badge = PillPushButton()
        self.status_badge.setCheckable(False)
        self.status_badge.setFixedHeight(26)
        self.status_badge.setMinimumWidth(60)
        self.status_badge.setVisible(False)  # 默认隐藏
        self.hbox.addWidget(self.status_badge, 0, Qt.AlignCenter)
        
        # 右侧：操作按钮
        self.btn_container = QFrame()
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(8)
        
        # 激活状态按钮（下拉菜单）
        self.activate_btn = TransparentDropDownPushButton(self.tra("激活"))
        
        activate_menu = RoundMenu(parent=self)
        activate_menu.addAction(Action(
            FluentIcon.LANGUAGE, 
            self.tra("翻译任务"),
            triggered=lambda: self._set_activate_status("translate")
        ))
        activate_menu.addAction(Action(
            FluentIcon.EDIT, 
            self.tra("润色任务"),
            triggered=lambda: self._set_activate_status("polish")
        ))
        activate_menu.addSeparator()
        activate_menu.addAction(Action(
            FluentIcon.CLOSE, 
            self.tra("取消激活"),
            triggered=lambda: self._set_activate_status(None)
        ))
        self.activate_btn.setMenu(activate_menu)
        self.btn_layout.addWidget(self.activate_btn)
        
        # 更多按钮
        self.more_btn = DropDownToolButton()
        self.more_btn.setIcon(FluentIcon.MORE)
        
        more_menu = RoundMenu(parent=self)
        
        # 测试接口放在最上面
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
        self.btn_layout.addWidget(self.more_btn)
        
        self.hbox.addWidget(self.btn_container)
        
    def _set_activate_status(self, status: str):
        """设置激活状态"""
        self.activate_status = status
        self._update_activate_button()
        self.activateChanged.emit(self.api_tag, status if status else "")
        
    def _update_activate_button(self):
        """更新激活状态标签显示"""
        if self.activate_status == "translate":
            self.status_badge.setText(self.tra("翻译"))
            self.status_badge.setStyleSheet("""
                PillPushButton {
                    background-color: rgba(39, 174, 96, 0.2);
                    color: #27ae60;
                    border: 1px solid rgba(39, 174, 96, 0.4);
                    border-radius: 13px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                PillPushButton:hover {
                    background-color: rgba(39, 174, 96, 0.25);
                }
            """)
            self.status_badge.setVisible(True)
        elif self.activate_status == "polish":
            self.status_badge.setText(self.tra("润色"))
            self.status_badge.setStyleSheet("""
                PillPushButton {
                    background-color: rgba(52, 152, 219, 0.2);
                    color: #3498db;
                    border: 1px solid rgba(52, 152, 219, 0.4);
                    border-radius: 13px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                PillPushButton:hover {
                    background-color: rgba(52, 152, 219, 0.25);
                }
            """)
            self.status_badge.setVisible(True)
        else:
            self.status_badge.setVisible(False)
            
    def update_info(self, api_data: dict):
        """更新卡片信息"""
        self.api_data = api_data
        self.name_label.setText(api_data.get("name", ""))
        
        # 更新接口地址显示
        api_url = api_data.get("api_url", "")
        display_url = api_url if api_url else self.tra("未设置接口地址")
        self.info_label.setText(display_url)
        
    def set_activate_status(self, status: str):
        """外部设置激活状态（不触发信号）"""
        self.activate_status = status
        self._update_activate_button()