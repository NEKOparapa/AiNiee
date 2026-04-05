from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    Action,
    CardWidget,
    FluentIcon as FIF,
    MessageBox,
    PrimarySplitPushButton,
    RoundMenu,
    TransparentPushButton,
)
from qframelesswindow import QTimer

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.Toast import ToastMixin


class BottomCommandBar(ConfigMixin, LogMixin, ToastMixin, Base, CardWidget):
    ACTION_CONTINUE = "continue"
    ACTION_STOP = "stop"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setBorderRadius(18)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(18, 12, 18, 12)
        self.layout.setSpacing(12)

        self.current_mode = TaskType.TRANSLATION
        self.has_resumable_task = False
        self.task_action_mode = None

        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.setInterval(1000)
        self.ui_update_timer.timeout.connect(lambda: self.emit(Base.EVENT.TASK_UPDATE, {}))

        self.menu = RoundMenu(parent=self)
        self.translate_action = Action(FIF.PLAY, self.tra("开始翻译"))
        self.polish_action = Action(FIF.ALBUM, self.tra("开始润色"))
        self.menu.addAction(self.translate_action)
        self.menu.addAction(self.polish_action)

        self.start_btn = PrimarySplitPushButton(FIF.PLAY, self.tra("开始翻译"))
        self.start_btn.setFlyout(self.menu)
        self.task_action_btn = TransparentPushButton(FIF.ROTATE, self.tra("继续"))
        self.task_action_btn.setFixedWidth(96)
        self.task_action_btn.setEnabled(False)

        for button in (self.start_btn, self.task_action_btn):
            button.setIconSize(QSize(16, 16))
            button.setFixedHeight(32)

        self.layout.addStretch(1)
        self.layout.addWidget(self.start_btn, 0, Qt.AlignCenter)
        self.layout.addWidget(self.task_action_btn, 0, Qt.AlignCenter)
        self.layout.addStretch(1)

        self.start_btn.clicked.connect(self.command_play)
        self.task_action_btn.clicked.connect(self.command_task_action)

        self.translate_action.triggered.connect(
            lambda checked=False: self._on_mode_selected(TaskType.TRANSLATION, self.translate_action)
        )
        self.polish_action.triggered.connect(
            lambda checked=False: self._on_mode_selected(TaskType.POLISH, self.polish_action)
        )

        self.subscribe(Base.EVENT.TASK_STOP_DONE, self.task_stop_done)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

    def _on_mode_selected(self, mode: str, action: Action) -> None:
        self.current_mode = mode
        self.start_btn.setText(action.text())
        if self.current_mode == TaskType.TRANSLATION:
            self.info_toast(self.tra("模式已切换为"), ": " + self.tra("翻译模式"))
        elif self.current_mode == TaskType.POLISH:
            self.info_toast(self.tra("模式已切换为"), ": " + self.tra("润色模式"))

    def update_task_action_button(self, mode: str | None) -> None:
        self.task_action_mode = mode

        if mode == self.ACTION_CONTINUE:
            self.task_action_btn.setIcon(FIF.ROTATE)
            self.task_action_btn.setText(self.tra("继续"))
            self.task_action_btn.setEnabled(True)
            return

        if mode == self.ACTION_STOP:
            self.task_action_btn.setIcon(FIF.CANCEL_MEDIUM)
            self.task_action_btn.setText(self.tra("停止"))
            self.task_action_btn.setEnabled(True)
            return

        self.task_action_btn.setIcon(FIF.ROTATE)
        self.task_action_btn.setText(self.tra("继续"))
        self.task_action_btn.setEnabled(False)

    def enable_continue_button(self, enable: bool) -> None:
        self.has_resumable_task = enable
        if self.task_action_mode != self.ACTION_STOP:
            self.update_task_action_button(self.ACTION_CONTINUE if enable else None)

    def app_shut_down(self, event: int, data: dict) -> None:
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()

    def task_stop_done(self, event: int, data: dict) -> None:
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()

        self.start_btn.setEnabled(True)
        self.update_task_action_button(None)
        Base.work_status = Base.STATUS.IDLE
        self.emit(Base.EVENT.TASK_CONTINUE_CHECK, {})

    def command_play(self) -> None:
        if not self._has_valid_api_binding():
            return

        if self.has_resumable_task:
            content = self.tra("将重置尚未完成的任务") + "  ... ？"
            message_box = MessageBox("Warning", content, self.window())
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if not message_box.exec():
                return

        self.start_btn.setEnabled(False)
        self.update_task_action_button(self.ACTION_STOP)

        self.emit(
            Base.EVENT.TASK_START,
            {
                "continue_status": False,
                "current_mode": self.current_mode,
            },
        )

        self.ui_update_timer.start()

    def command_stop(self) -> None:
        content = self.tra("是否确定停止任务") + "  ... ？"
        message_box = MessageBox("Warning", content, self.window())
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))

        if message_box.exec():
            self.info("正在停止任务 ... ")
            self.emit(Base.EVENT.TASK_STOP, {})

    def command_task_action(self) -> None:
        if self.task_action_mode == self.ACTION_CONTINUE:
            self.command_continue()
        elif self.task_action_mode == self.ACTION_STOP:
            self.command_stop()

    def command_continue(self) -> None:
        self.start_btn.setEnabled(False)
        self.update_task_action_button(self.ACTION_STOP)

        self.emit(
            Base.EVENT.TASK_START,
            {
                "continue_status": True,
                "current_mode": self.current_mode,
            },
        )

        self.ui_update_timer.start()

    def _has_valid_api_binding(self) -> bool:
        config = self.load_config()
        api_settings = config.get("api_settings", {})
        platforms = config.get("platforms", {})

        translate_tag = api_settings.get("translate")
        polish_tag = api_settings.get("polish")

        selected_tag = translate_tag if translate_tag in platforms else None
        if selected_tag is None and polish_tag in platforms:
            selected_tag = polish_tag

        if not selected_tag:
            self.error_toast(self.tra("错误"), self.tra("未设置当前激活接口，请先到接口管理页面激活接口。"))
            return False

        if selected_tag not in platforms:
            self.error_toast(self.tra("错误"), self.tra("当前激活接口配置不存在，请到接口管理页面重新选择。"))
            return False

        return True
