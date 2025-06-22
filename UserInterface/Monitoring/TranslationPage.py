import time
import threading

from PyQt5.QtGui import QColor
from PyQt5.QtCore import QTimer, QTime
from PyQt5.QtWidgets import QWidget,QLabel
from PyQt5.QtWidgets import QLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import MessageBoxBase, StrongBodyLabel
from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import FlowLayout, TimePicker
from qfluentwidgets import MessageBox
from qfluentwidgets import FluentWindow
from qfluentwidgets import CaptionLabel
from qfluentwidgets import IndeterminateProgressRing

from Base.Base import Base
from Widget.DashboardCard import DashboardCard
from Widget.WaveformCard import WaveformCard
from Widget.ProgressRingCard import ProgressRingCard
from Widget.CommandBarCard import CommandBarCard
from Widget.CombinedLineCard import CombinedLineCard

class ScheduledTranslationDialog(MessageBoxBase, Base):
    """
    定时开始翻译对话框
    """
    def __init__(self, parent=None,title: str = "定时开始翻译", message_box_close = None):
        super().__init__(parent=parent)

        self.message_box_close = message_box_close

        # 设置框体
        self.yesButton.setText(self.tra("确定"))
        self.cancelButton.setText((self.tra("取消")))

        self.viewLayout.setContentsMargins(16, 16, 16, 16)
        self.title_label = StrongBodyLabel(title, self)
        self.viewLayout.addWidget(self.title_label)

        # 添加说明标签
        info_label = QLabel(self.tra("请设置开始翻译的时间："))
        self.viewLayout.addWidget(info_label)

        self.time_picker = TimePicker(self)
        current_time = QTime.currentTime()
        self.time_picker.setTime(current_time)

        self.viewLayout.addWidget(self.time_picker)

        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)


    def get_scheduled_time(self):
        return self.time_picker.getTime()

class TranslationPage(QWidget, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 初始化
        self.data = {}
        self.scheduled_timer = None

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_head(self.container, config, window)
        self.add_widget_foot(self.container, config, window)
        # 注册事件
        self.subscribe(Base.EVENT.TRANSLATION_UPDATE, self.translation_update)
        self.subscribe(Base.EVENT.TRANSLATION_STOP_DONE, self.translation_stop_done)
        self.subscribe(Base.EVENT.TRANSLATION_CONTINUE_CHECK_DONE, self.translation_continue_check_done)
        self.subscribe(Base.EVENT.CACHE_FILE_AUTO_SAVE, self.cache_file_auto_save)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

        # 定时器
        threading.Thread(target = self.update_ui_tick).start()

    # 页面显示事件
    def showEvent(self, event) -> None:
        super().showEvent(event)

        # 重置 UI 状态
        self.action_continue.setEnabled(False)

        # 触发事件
        self.emit(Base.EVENT.TRANSLATION_CONTINUE_CHECK, {})

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        self.update_ui_tick_stop_flag = True
        # 取消定时翻译任务
        if self.scheduled_timer is not None:
            self.scheduled_timer.stop()
            self.scheduled_timer = None

    # 更新 UI 定时器
    def update_ui_tick(self) -> None:
        while True:
            time.sleep(1)

            # 接收到退出信号则停止
            if hasattr(self, "update_ui_tick_stop_flag") and self.update_ui_tick_stop_flag:
                break

            # 触发翻译更新事件来更新 UI
            self.emit(Base.EVENT.TRANSLATION_UPDATE, {})

    # 翻译更新事件
    def translation_update(self, event: int, data: dict) -> None:
        if Base.work_status in (Base.STATUS.STOPING, Base.STATUS.TRANSLATING):
            self.update_time(event, data)
            self.update_line(event, data)
            self.update_token(event, data)
            self.update_stability(event, data)

        self.update_task(event, data)
        self.update_status(event, data)

    # 翻译停止完成事件
    def translation_stop_done(self, event: int, data: dict) -> None:
        self.indeterminate_hide()
        self.action_play.setEnabled(True)
        self.action_stop.setEnabled(False)
        self.action_export.setEnabled(False)

        # 设置翻译状态为无任务
        Base.work_status = Base.STATUS.IDLE

        # 更新继续翻译按钮状态
        self.emit(Base.EVENT.TRANSLATION_CONTINUE_CHECK, {})

    # 翻译状态检查完成事件
    def translation_continue_check_done(self, event: int, data: dict) -> None:
        self.action_continue.setEnabled(
            data.get("continue_status", False) and self.action_play.isEnabled()
        )

    # 缓存文件自动保存时间
    def cache_file_auto_save(self, event: int, data: dict) -> None:
        if self.indeterminate.isHidden():
            info_cont = self.tra("缓存文件保存中") + " ..."
            self.indeterminate_show(info_cont)

            # 延迟关闭
            QTimer.singleShot(1500, lambda: self.indeterminate_hide())

    # 头部
    def add_widget_head(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        self.head_hbox_container = QWidget(self)
        self.head_hbox = FlowLayout(self.head_hbox_container, needAni = False)
        self.head_hbox.setSpacing(8)
        self.head_hbox.setContentsMargins(0, 0, 0, 0)

        # 添加两个控件
        self.add_combined_line_card(self.head_hbox, config, window)
        self.add_time_card(self.head_hbox, config, window)
        self.add_remaining_time_card(self.head_hbox, config, window)
        self.add_token_card(self.head_hbox, config, window)
        self.add_task_card(self.head_hbox, config, window)

        self.add_ring_card(self.head_hbox, config, window)
        self.add_waveform_card(self.head_hbox, config, window)

        self.add_speed_card(self.head_hbox, config, window)
        self.add_stability_card(self.head_hbox, config, window)


        # 添加到主容器
        self.container.addWidget(self.head_hbox_container, 1)

    # 底部
    def add_widget_foot(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        # 添加命令
        self.command_bar_card.set_minimum_width(512)
        self.add_command_bar_action_play(self.command_bar_card, config, window)
        self.add_command_bar_action_stop(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_continue(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_export(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_schedule(self.command_bar_card, config, window)
        # 添加信息条
        self.indeterminate = IndeterminateProgressRing()
        self.indeterminate.setFixedSize(16, 16)
        self.indeterminate.setStrokeWidth(3)
        self.indeterminate.hide()
        info_cont = self.tra("缓存文件保存中") + " ..."
        self.info_label = CaptionLabel(info_cont, self)
        self.info_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.info_label.hide()

        self.command_bar_card.add_stretch(1)
        self.command_bar_card.add_widget(self.info_label)
        self.command_bar_card.add_spacing(4)
        self.command_bar_card.add_widget(self.indeterminate)

    # 开始
    def add_command_bar_action_play(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def triggered() -> None:
            # 如果有定时任务，先取消
            if self.scheduled_timer is not None:
                self.scheduled_timer.stop()
                self.scheduled_timer = None
                self.action_schedule.setText(self.tra("定时开始"))

            if self.action_continue.isEnabled():
                info_cont1 = self.tra("将重置尚未完成的翻译任务，是否确认开始新的翻译任务") + "  ... ？"
                message_box = MessageBox("Warning", info_cont1, window)
                info_cont2 = self.tra("确认")
                message_box.yesButton.setText(info_cont2)
                info_cont3 = self.tra("取消")
                message_box.cancelButton.setText(info_cont3)

                # 点击取消，则不触发开始翻译事件
                if not message_box.exec():
                    return

            self.action_play.setEnabled(False)
            self.action_stop.setEnabled(True)
            self.action_export.setEnabled(True)
            self.action_continue.setEnabled(False)
            self.emit(Base.EVENT.TRANSLATION_START, {
                "continue_status": False,
            })

        info_cont4 = self.tra("开始")
        self.action_play = parent.add_action(
            Action(FluentIcon.PLAY, info_cont4, parent, triggered = triggered)
        )

    # 停止
    def add_command_bar_action_stop(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def triggered() -> None:
            # 如果有定时任务，先取消
            if self.scheduled_timer is not None:
                self.scheduled_timer.stop()
                self.scheduled_timer = None
                self.action_schedule.setText(self.tra("定时开始"))

            info_cont1 = self.tra("停止的翻译任务可以随时继续翻译，是否确定停止任务") + "  ... ？"
            message_box = MessageBox("Warning", info_cont1, window)
            info_cont2 = self.tra("确认")
            message_box.yesButton.setText(info_cont2)
            info_cont3 = self.tra("取消")
            message_box.cancelButton.setText(info_cont3)

            # 确认则触发停止翻译事件
            if message_box.exec():
                info_cont4 = self.tra("正在停止翻译任务") + "  ... "
                self.indeterminate_show(info_cont4)

                self.action_stop.setEnabled(False)
                self.action_export.setEnabled(False)
                self.emit(Base.EVENT.TRANSLATION_STOP, {})

        info_cont5 = self.tra("停止")
        self.action_stop = parent.add_action(
            Action(FluentIcon.CANCEL_MEDIUM, info_cont5, parent,  triggered = triggered),
        )
        self.action_stop.setEnabled(False)

    # 定时开始翻译
    def add_command_bar_action_schedule(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def triggered() -> None:
            # 如果已经有定时任务，则取消
            if self.scheduled_timer is not None:
                self.scheduled_timer.stop()
                self.scheduled_timer = None
                self.action_schedule.setText(self.tra("定时开始"))
                info_cont = self.tra("定时翻译任务已取消") + "  ... "
                window.success_toast("", info_cont)
                return

            # 创建定时对话框
            dialog = ScheduledTranslationDialog(parent=window,title=self.tra("定时翻译"))
            if dialog.exec_():
                scheduled_time = dialog.get_scheduled_time()
                current_time = QTime.currentTime()

                # 计算当前时间到设定时间的毫秒数
                current_seconds = current_time.hour() * 3600 + current_time.minute() * 60 + current_time.second()
                scheduled_seconds = scheduled_time.hour() * 3600 + scheduled_time.minute() * 60 + scheduled_time.second()

                # 如果设定时间小于当前时间，则认为是明天的时间
                if scheduled_seconds < current_seconds:
                    scheduled_seconds += 24 * 3600  # 添加一天的秒数

                # 计算时间差异（毫秒）
                msec_diff = (scheduled_seconds - current_seconds) * 1000

                # 检查时间间隔是否有效（50s）
                if msec_diff < 50000:
                    warning_box = MessageBox(self.tra("无效时间"), self.tra("与当前时间间隔过短"), window)
                    warning_box.yesButton.setText(self.tra("知道了"))
                    warning_box.cancelButton.hide()
                    warning_box.exec()
                    return # 不设置定时任务

                # 创建定时器
                self.scheduled_timer = QTimer(self)
                self.scheduled_timer.setSingleShot(True)
                self.scheduled_timer.timeout.connect(self.start_scheduled_translation)
                self.scheduled_timer.start(msec_diff)

                # 更新按钮文本
                time_str = scheduled_time.toString("HH:mm:ss")
                self.action_schedule.setText(f"{time_str}")

                # 显示提示
                info_cont =  f" {time_str} " + self.tra("定时开始翻译") + "  ... "
                window.success_toast(self.tra("已设置定时翻译任务，将在"), info_cont)

        info_cont = self.tra("定时开始")
        self.action_schedule = parent.add_action(
            Action(FluentIcon.DATE_TIME, info_cont, parent, triggered = triggered),
        )

    # 开始定时翻译
    def start_scheduled_translation(self) -> None:
        # 重置定时器
        self.scheduled_timer = None
        self.action_schedule.setText(self.tra("定时开始"))

        # 开始翻译
        self.info("定时翻译任务已开始 ...")
        self.action_play.setEnabled(False)
        self.action_stop.setEnabled(True)
        self.action_export.setEnabled(True)
        self.action_continue.setEnabled(False)
        self.emit(Base.EVENT.TRANSLATION_START, {
            "continue_status": False,
        })

        # # 显示提示
        # info_cont = self.tra("定时翻译任务已开始") + "  ... "
        # self.success_toast("", info_cont)

    # 继续翻译
    def add_command_bar_action_continue(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def triggered() -> None:
            self.action_play.setEnabled(False)
            self.action_stop.setEnabled(True)
            self.action_export.setEnabled(True)
            self.action_continue.setEnabled(False)
            self.emit(Base.EVENT.TRANSLATION_START, {
                "continue_status": True,
            })

        info_cont = self.tra("继续翻译")
        self.action_continue = parent.add_action(
            Action(FluentIcon.ROTATE, info_cont, parent, triggered = triggered),
        )

    # 导出已完成的内容
    def add_command_bar_action_export(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def triggered() -> None:
            self.emit(Base.EVENT.TRANSLATION_MANUAL_EXPORT, {})
            info_cont = self.tra("已根据当前的翻译数据在输出文件夹下生成翻译文件") + "  ... "
            self.success_toast("", info_cont)

        info_cont2 = self.tra("导出翻译数据")
        self.action_export = parent.add_action(
            Action(FluentIcon.SHARE, info_cont2, parent, triggered = triggered),
        )
        self.action_export.setEnabled(False)

    # 显示信息条
    def indeterminate_show(self, msg: str) -> None:
        self.indeterminate.show()
        self.info_label.show()
        self.info_label.setText(msg)

    # 隐藏信息条
    def indeterminate_hide(self) -> None:
        self.indeterminate.hide()
        self.info_label.hide()
        self.info_label.setText("")