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
    TransparentToolButton,
)
from qframelesswindow import QTimer

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.Toast import ToastMixin


class BottomCommandBar(ConfigMixin, LogMixin, ToastMixin, Base, CardWidget):
    ACTION_CONTINUE = "continue"
    ACTION_STOP = "stop"

    def __init__(self, cache_manager=None, parent=None):
        super().__init__(parent)
        self.cache_manager = cache_manager
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

        self.reset_menu = RoundMenu(parent=self)
        self.reset_translation_action = Action(FIF.DELETE, self.tra("重置翻译"))
        self.reset_polish_action = Action(FIF.DELETE, self.tra("重置润色"))
        self.reset_menu.addAction(self.reset_translation_action)
        self.reset_menu.addAction(self.reset_polish_action)

        self.start_btn = PrimarySplitPushButton(FIF.PLAY, self.tra("开始翻译"))
        self.start_btn.setFlyout(self.menu)
        self.task_action_btn = TransparentPushButton(FIF.ROTATE, self.tra("继续"))
        self.task_action_btn.setFixedWidth(96)
        self.task_action_btn.setEnabled(False)
        self.reset_btn = TransparentToolButton(FIF.DELETE, self)
        self.reset_btn.setFixedWidth(32)
        self.reset_btn.setToolTip(self.tra("重置"))
        self.reset_btn.setEnabled(False)

        for button in (self.start_btn, self.task_action_btn, self.reset_btn):
            button.setIconSize(QSize(16, 16))
            button.setFixedHeight(32)

        self.layout.addStretch(1)
        self.layout.addWidget(self.start_btn, 0, Qt.AlignCenter)
        self.layout.addWidget(self.task_action_btn, 0, Qt.AlignCenter)
        self.layout.addWidget(self.reset_btn, 0, Qt.AlignCenter)
        self.layout.addStretch(1)

        self.start_btn.clicked.connect(self.command_play)
        self.task_action_btn.clicked.connect(self.command_task_action)
        self.reset_btn.clicked.connect(self.command_reset)

        self.translate_action.triggered.connect(
            lambda checked=False: self._on_mode_selected(TaskType.TRANSLATION, self.translate_action)
        )
        self.polish_action.triggered.connect(
            lambda checked=False: self._on_mode_selected(TaskType.POLISH, self.polish_action)
        )
        self.reset_translation_action.triggered.connect(
            lambda checked=False: self.command_reset_status(TaskType.TRANSLATION)
        )
        self.reset_polish_action.triggered.connect(
            lambda checked=False: self.command_reset_status(TaskType.POLISH)
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
            self._update_reset_button_state()
            return

        if mode == self.ACTION_STOP:
            self.task_action_btn.setIcon(FIF.CANCEL_MEDIUM)
            self.task_action_btn.setText(self.tra("停止"))
            self.task_action_btn.setEnabled(True)
            self.reset_btn.setEnabled(False)
            return

        self.task_action_btn.setIcon(FIF.ROTATE)
        self.task_action_btn.setText(self.tra("继续"))
        self.task_action_btn.setEnabled(False)
        self._update_reset_button_state()

    def enable_continue_button(self, enable: bool) -> None:
        self.has_resumable_task = enable
        if self.task_action_mode != self.ACTION_STOP:
            self.update_task_action_button(self.ACTION_CONTINUE if enable else None)
        else:
            self.reset_btn.setEnabled(False)

    def app_shut_down(self, event: int, data: dict) -> None:
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()
        self.reset_btn.setEnabled(False)

    def task_stop_done(self, event: int, data: dict) -> None:
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()

        self.start_btn.setEnabled(True)
        self.update_task_action_button(None)
        Base.work_status = Base.STATUS.IDLE
        self._update_reset_button_state()
        self.emit(Base.EVENT.TASK_CONTINUE_CHECK, {})

    def command_play(self) -> None:
        if not self._has_valid_api_binding():
            return
        if self.current_mode == TaskType.POLISH and not self._has_sufficient_translated_lines_for_polish():
            return

        if self.has_resumable_task:
            content = self.tra("将重置尚未完成的任务") + " ..."
            message_box = MessageBox("Warning", content, self.window())
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if not message_box.exec():
                return

        self.start_btn.setEnabled(False)
        self.update_task_action_button(self.ACTION_STOP)
        self.reset_btn.setEnabled(False)

        self.emit(
            Base.EVENT.TASK_START,
            {
                "continue_status": False,
                "current_mode": self.current_mode,
            },
        )

        self.ui_update_timer.start()

    def command_stop(self) -> None:
        content = self.tra("是否确定停止任务") + " ..."
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
        self.reset_btn.setEnabled(False)

        self.emit(
            Base.EVENT.TASK_START,
            {
                "continue_status": True,
                "current_mode": self.current_mode,
            },
        )

        self.ui_update_timer.start()

    def command_reset(self) -> None:
        if not self._can_reset_project(show_message=True):
            self._update_reset_button_state()
            return

        self.reset_menu.exec(self.reset_btn.mapToGlobal(self.reset_btn.rect().bottomLeft()))

    def command_reset_status(self, task_mode: int) -> None:
        if not self._can_reset_project(show_message=True):
            self._update_reset_button_state()
            return

        if task_mode == TaskType.TRANSLATION:
            content = self.tra("是否确认重置项目的已翻译状态？")
        elif task_mode == TaskType.POLISH:
            content = self.tra("是否确认重置项目的已润色状态？")
        else:
            return

        message_box = MessageBox(self.tra("警告"), content, self.window())
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        changed_count = self.cache_manager.reset_project_status(task_mode)
        if changed_count <= 0:
            self.info_toast(self.tra("提示"), self.tra("没有可重置的项目状态。"))
            return

        self.has_resumable_task = False
        self.update_task_action_button(None)
        self.success_toast("", self.tra("项目状态已重置。"))
        self.emit(Base.EVENT.TASK_CONTINUE_CHECK, {})

    def _can_reset_project(self, show_message: bool = False) -> bool:
        if Base.work_status != Base.STATUS.IDLE:
            if show_message:
                self.warning_toast(self.tra("操作受限"), self.tra("只有空闲状态才能重置项目状态。"))
            return False

        if not self.cache_manager or not self.cache_manager.project:
            if show_message:
                self.error_toast(self.tra("错误"), self.tra("当前没有可重置的项目缓存。"))
            return False

        return True

    def _update_reset_button_state(self) -> None:
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(self._can_reset_project())

    def _has_valid_api_binding(self) -> bool:
        interface_role = "translate" if self.current_mode == TaskType.TRANSLATION else "polish"
        interface_name = self.tra("翻译接口") if interface_role == "translate" else self.tra("润色接口")

        task_config = TaskConfig()
        task_config.initialize(interface_role)
        selected_tag = task_config.get_active_platform_tag(interface_role)
        platforms = getattr(task_config, "platforms", {}) or {}

        if not selected_tag:
            self.error_toast(self.tra("错误"), f"{interface_name}{self.tra('未设置，请先到接口管理页面进行绑定或激活')}")
            return False

        if selected_tag not in platforms:
            self.error_toast(self.tra("错误"), f"{interface_name}{self.tra('配置不存在，请到接口管理页面重新选择。')}")
            return False

        return True

    def _has_sufficient_translated_lines_for_polish(self) -> bool:
        if not self.cache_manager or not self.cache_manager.project:
            self.error("Polish pre-check failed: cache manager or current project is unavailable.")
            self.error_toast(self.tra("错误"), self.tra("请先执行翻译流程"))
            return False

        project_id = getattr(self.cache_manager.project, "project_id", "")
        translated_line = self.cache_manager.get_item_count_by_status(TranslationStatus.TRANSLATED)
        if translated_line <= 0:
            self.error(f"Polish pre-check failed: no translated lines are available for project {project_id}.")
            self.error_toast(self.tra("错误"), self.tra("请先执行翻译流程"))
            return False

        return True
