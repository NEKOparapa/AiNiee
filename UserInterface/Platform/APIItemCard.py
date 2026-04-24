import os

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QStackedLayout, QWidget

from qfluentwidgets import (
    Action,
    DropDownPushButton,
    FluentIcon,
    PrimaryDropDownPushButton,
    RoundMenu,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class APIItemCard(QWidget, ConfigMixin, Base):
    """
    接口按钮组件
    """

    _icon_cache = {}

    testClicked = pyqtSignal(str)
    activateClicked = pyqtSignal(str)
    editClicked = pyqtSignal(str)
    editArgsClicked = pyqtSignal(str)
    deleteClicked = pyqtSignal(str)

    def __init__(self, api_tag: str, api_data: dict, parent=None):
        super().__init__(parent)

        self.api_tag = api_tag
        self.api_data = api_data
        self._is_active = False
        self._activate_actions = []

        self.normal_button = DropDownPushButton(parent=self)
        self.active_button = PrimaryDropDownPushButton(parent=self)

        self.stack_layout = QStackedLayout(self)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        self.stack_layout.setSpacing(0)
        self.stack_layout.addWidget(self.normal_button)
        self.stack_layout.addWidget(self.active_button)

        self.setFixedWidth(180)
        self.normal_button.setFixedWidth(180)
        self.active_button.setFixedWidth(180)

        self._build_menu(self.normal_button)
        self._build_menu(self.active_button)
        self._apply_info()
        self.set_active(False)

    def _apply_info(self):
        name = self.api_data.get("name", "None")
        icon = self._get_icon()

        for button in (self.normal_button, self.active_button):
            button.setText(name)
            button.setIcon(icon)

        self.setFixedHeight(self.normal_button.sizeHint().height())

    def _get_icon(self):
        icon_name = self.api_data.get("icon", "custom")
        if icon_name not in self._icon_cache:
            file_name = icon_name + ".png"
            icon_path = os.path.join(".", "Resource", "platforms", "Icon", file_name)
            if os.path.exists(icon_path):
                self._icon_cache[icon_name] = QIcon(icon_path)
            else:
                self._icon_cache[icon_name] = FluentIcon.ROBOT

        return self._icon_cache[icon_name]

    def _build_menu(self, button):
        menu = RoundMenu(parent=button)

        activate_action = Action(
            FluentIcon.ACCEPT_MEDIUM,
            self.tra("激活接口"),
            triggered=lambda checked=False: self.activateClicked.emit(self.api_tag),
        )
        self._activate_actions.append(activate_action)
        menu.addAction(activate_action)
        menu.addSeparator()

        menu.addAction(
            Action(
                FluentIcon.SEND,
                self.tra("测试接口"),
                triggered=lambda checked=False: self.testClicked.emit(self.api_tag),
            )
        )
        menu.addSeparator()

        menu.addAction(
            Action(
                FluentIcon.EDIT,
                self.tra("编辑接口"),
                triggered=lambda checked=False: self.editClicked.emit(self.api_tag),
            )
        )
        menu.addAction(
            Action(
                FluentIcon.DEVELOPER_TOOLS,
                self.tra("调整参数"),
                triggered=lambda checked=False: self.editArgsClicked.emit(self.api_tag),
            )
        )
        menu.addSeparator()
        menu.addAction(
            Action(
                FluentIcon.DELETE,
                self.tra("删除接口"),
                triggered=lambda checked=False: self.deleteClicked.emit(self.api_tag),
            )
        )

        button.setMenu(menu)

    def update_info(self, api_data: dict):
        """更新显示信息"""
        self.api_data = api_data
        self._apply_info()
        self._refresh_activate_actions()

    def _refresh_activate_actions(self):
        for action in self._activate_actions:
            action.setEnabled(not self._is_active)

    def set_active(self, active: bool):
        """更新激活状态"""
        self._is_active = active
        self._refresh_activate_actions()
        self.stack_layout.setCurrentWidget(self.active_button if active else self.normal_button)
