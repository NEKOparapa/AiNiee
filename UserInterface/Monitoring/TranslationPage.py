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

    STATUS_TEXT = {
        Base.STATUS.IDLE: "No Task",
        Base.STATUS.API_TEST: "Testing",
        Base.STATUS.TRANSLATING: "Translating",
        Base.STATUS.STOPING: "Stopping",
    }

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

    # 更新时间
    def update_time(self, event: int, data: dict) -> None:
        if data.get("start_time", None) is not None:
            self.data["start_time"] = data.get("start_time")

        if self.data.get("start_time", 0) == 0:
            total_time = 0
        else:
            total_time = int(time.time() - self.data.get("start_time", 0))

        if total_time < 60:
            self.time.set_unit("S")
            self.time.set_value(f"{total_time}")
        elif total_time < 60 * 60:
            self.time.set_unit("M")
            self.time.set_value(f"{(total_time / 60):.2f}")
        else:
            self.time.set_unit("H")
            self.time.set_value(f"{(total_time / 60 / 60):.2f}")

        remaining_time = int(total_time / max(1, self.data.get("line", 0)) * (self.data.get("total_line", 0) - self.data.get("line", 0)))
        if remaining_time < 60:
            self.remaining_time.set_unit("S")
            self.remaining_time.set_value(f"{remaining_time}")
        elif remaining_time < 60 * 60:
            self.remaining_time.set_unit("M")
            self.remaining_time.set_value(f"{(remaining_time / 60):.2f}")
        else:
            self.remaining_time.set_unit("H")
            self.remaining_time.set_value(f"{(remaining_time / 60 / 60):.2f}")

    # 更新行数
    def update_line(self, event: int, data: dict) -> None:
        if data.get("line", None) is not None and data.get("total_line", None) is not None:
            self.data["line"] = data.get("line")
            self.data["total_line"] = data.get("total_line")

        translated_line = self.data.get("line", 0)
        total_line = self.data.get("total_line", 0)
        remaining_line = max(0, total_line - translated_line)

        t_value_str: str
        t_unit_str: str
        if translated_line < 1000:
            t_unit_str = "Line"
            t_value_str = f"{translated_line}"
        elif translated_line < 1000 * 1000:
            t_unit_str = "KLine"
            t_value_str = f"{(translated_line / 1000):.2f}"
        else:
            t_unit_str = "MLine"
            t_value_str = f"{(translated_line / 1000 / 1000):.2f}"

        r_value_str: str
        r_unit_str: str
        if remaining_line < 1000:
            r_unit_str = "Line"
            r_value_str = f"{remaining_line}"
        elif remaining_line < 1000 * 1000:
            r_unit_str = "KLine"
            r_value_str = f"{(remaining_line / 1000):.2f}"
        else:
            r_unit_str = "MLine"
            r_value_str = f"{(remaining_line / 1000 / 1000):.2f}"

        if hasattr(self, 'combined_line_card') and self.combined_line_card:
            self.combined_line_card.set_left_data(value=t_value_str, unit=t_unit_str)
            self.combined_line_card.set_right_data(value=r_value_str, unit=r_unit_str)

    # 更新实时任务数
    def update_task(self, event: int, data: dict) -> None:
        task = len([t for t in threading.enumerate() if "translator" in t.name])
        if task < 1000:
            self.task.set_unit("Task")
            self.task.set_value(f"{task}")
        else:
            self.task.set_unit("KTask")
            self.task.set_value(f"{(task / 1000):.2f}")

    # 更新 Token 数据
    def update_token(self, event: int, data: dict) -> None:
        if data.get("token", None) is not None and data.get("total_completion_tokens", None) is not None:
            self.data["token"] = data.get("token")
            self.data["total_completion_tokens"] = data.get("total_completion_tokens")

        token = self.data.get("token", 0)
        if token < 1000:
            self.token.set_unit("Token")
            self.token.set_value(f"{token}")
        elif token < 1000 * 1000:
            self.token.set_unit("KToken")
            self.token.set_value(f"{(token / 1000):.2f}")
        else:
            self.token.set_unit("MToken")
            self.token.set_value(f"{(token / 1000 / 1000):.2f}")

        speed = self.data.get("total_completion_tokens", 0) / max(1, time.time() - self.data.get("start_time", 0))
        self.waveform.add_value(speed)
        if speed < 1000:
            self.speed.set_unit("T/S")
            self.speed.set_value(f"{speed:.2f}")
        else:
            self.speed.set_unit("KT/S")
            self.speed.set_value(f"{(speed / 1000):.2f}")

    # 更新稳定性
    def update_stability(self, event: int, data: dict) -> None:
        # 如果传入数据中包含新的请求统计，则更新数据
        if data.get("total_requests") is not None and data.get("error_requests") is not None:
            self.data["total_requests"] = data["total_requests"]
            self.data["error_requests"] = data["error_requests"]

        # 获取总请求数和错误请求数（默认值为0）
        total_requests = self.data.get("total_requests", 0)
        error_requests = self.data.get("error_requests", 0)  # 修正变量名错误

        # 计算稳定性百分比（成功率）
        if total_requests == 0:
            stability_percent = 0.0
        else:
            stability_percent = ((total_requests - error_requests) / total_requests) * 100  # 成功率计算

        # 设置单位和格式化百分比值（保留两位小数）
        self.stability.set_unit("%")
        self.stability.set_value(f"{stability_percent:.2f}")

    # 更新进度环
    def update_status(self, event: int, data: dict) -> None:
        if Base.work_status == Base.STATUS.STOPING:
            percent = self.data.get("line", 0) / max(1, self.data.get("total_line", 0))
            self.ring.set_value(int(percent * 10000))
            info_cont = self.tra("停止中") + "\n" + f"{percent * 100:.2f}%"
            self.ring.set_format(info_cont)
        elif Base.work_status == Base.STATUS.TRANSLATING:
            percent = self.data.get("line", 0) / max(1, self.data.get("total_line", 0))
            self.ring.set_value(int(percent * 10000))
            info_cont = self.tra("翻译中") + "\n" + f"{percent * 100:.2f}%"
            self.ring.set_format(info_cont)
        else:
            self.ring.set_value(0)
            info_cont = self.tra("无任务")
            self.ring.set_format(info_cont)

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

        self.add_ring_card(self.head_hbox, config, window)
        self.add_waveform_card(self.head_hbox, config, window)

        self.add_token_card(self.head_hbox, config, window)
        self.add_task_card(self.head_hbox, config, window)
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

    # 进度环
    def add_ring_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        self.ring = ProgressRingCard(title=self.tra("翻译进度"),
                                     icon=FluentIcon.PIE_SINGLE,
                                     min_value= 0,
                                     max_value= 10000,
                                     ring_size=(140, 140),
                                     text_visible=True)
        self.ring.setFixedSize(204, 204)
        info_cont = self.tra("无任务")
        self.ring.set_format(info_cont)
        parent.addWidget(self.ring)

    # 波形图
    def add_waveform_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        self.waveform = WaveformCard(self.tra("波形图"),
                                     icon=FluentIcon.MARKET
                                    )
        self.waveform.set_draw_grid(False)  # 关闭网格线
        self.waveform.setFixedSize(633, 204)
        parent.addWidget(self.waveform)


    # 累计时间
    def add_time_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        info_cont = self.tra("累计时间")
        self.time = DashboardCard(
                title = info_cont,
                value = "Time",
                unit = "",
                icon=FluentIcon.STOP_WATCH,
            )
        self.time.setFixedSize(204, 204)
        parent.addWidget(self.time)

    # 剩余时间
    def add_remaining_time_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        info_cont = self.tra("剩余时间")
        self.remaining_time = DashboardCard(
                title = info_cont,
                value = "Time",
                unit = "",
                icon=FluentIcon.FRIGID,
            )
        self.remaining_time.setFixedSize(204, 204)
        parent.addWidget(self.remaining_time)

    # 行数统计
    def add_combined_line_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        """Adds the combined line count card to the parent layout."""
        main_title = self.tra("行数统计")
        left_title = self.tra("已翻译")
        right_title = self.tra("剩余")

        self.combined_line_card = CombinedLineCard(
            title=main_title,
            icon=FluentIcon.PRINT,
            left_title=left_title,
            right_title=right_title,
            initial_left_value="0",
            initial_left_unit="Line",
            initial_right_value="0",
            initial_right_unit="Line",
            parent=window
        )

        self.combined_line_card.setFixedSize(416, 204)

        parent.addWidget(self.combined_line_card)

    # 平均速度
    def add_speed_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        info_cont = self.tra("平均速度")
        self.speed = DashboardCard(
                title = info_cont,
                value = "T/S",
                unit = "",
                icon=FluentIcon.SPEED_HIGH,
            )
        self.speed.setFixedSize(204, 204)
        parent.addWidget(self.speed)

    # 累计消耗
    def add_token_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        info_cont = self.tra("累计消耗")
        self.token = DashboardCard(
                title =  info_cont,
                value = "Token",
                unit = "",
                icon=FluentIcon.CALORIES,
            )
        self.token.setFixedSize(204, 204)
        parent.addWidget(self.token)

    # 并行任务
    def add_task_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        info_cont = self.tra("实时任务数")
        self.task = DashboardCard(
                title = info_cont,
                value = "T",
                unit = "",
                icon=FluentIcon.SCROLL,
            )
        self.task.setFixedSize(204, 204)
        parent.addWidget(self.task)

    # 稳定性
    def add_stability_card(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        info_cont = self.tra("任务稳定性")
        self.stability = DashboardCard(
                title = info_cont,
                value = "%",
                unit = "",
                icon=FluentIcon.TRAIN,
            )
        self.stability.setFixedSize(204, 204)
        #self.stability.set_value_color("orange")
        parent.addWidget(self.stability)

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