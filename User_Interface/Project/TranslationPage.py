from PyQt5.QtGui import QColor
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import FlowLayout
from qfluentwidgets import MessageBox
from qfluentwidgets import ProgressRing
from qfluentwidgets import CaptionLabel
from qfluentwidgets import IndeterminateProgressRing

from Base.AiNieeBase import AiNieeBase
from Widget.DashboardCard import DashboardCard
from Widget.WaveformWidget import WaveformWidget
from Widget.CommandBarCard import CommandBarCard

class TranslationPage(QWidget, AiNieeBase):

    DEFAULT = {}

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 初始化
        self.window = window

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_head(self.container, config, window)
        self.add_widget_body(self.container, config, window)
        self.add_widget_foot(self.container, config, window)

        # 注册事件
        self.subscribe(self.EVENT.TRANSLATION_UPDATE, self.translation_update)
        self.subscribe(self.EVENT.TRANSLATION_STOP_DONE, self.translation_stop_done)
        self.subscribe(self.EVENT.TRANSLATION_CONTINUE_CHECK_DONE, self.translation_continue_check_done)
        self.subscribe(self.EVENT.CACHE_FILE_AUTO_SAVE, self.cache_file_auto_save)

    # 页面显示事件
    def showEvent(self, event):
        super().showEvent(event)
        self.emit(self.EVENT.TRANSLATION_CONTINUE_CHECK, {})

    # 翻译更新事件
    def translation_update(self, event: int, data: dict):
        if data.get("time", None) != None:
            time = int(data.get("time"))

            if time < 60:
                self.time.set_unit("S")
                self.time.set_value(f"{time}")
            elif time < 60 * 60:
                self.time.set_unit("M")
                self.time.set_value(f"{(time / 60):.2f}")
            else:
                self.time.set_unit("H")
                self.time.set_value(f"{(time / 60 / 60):.2f}")

        if data.get("remaining_time", None) != None:
            remaining_time = int(data.get("remaining_time"))

            if remaining_time < 60:
                self.remaining_time.set_unit("S")
                self.remaining_time.set_value(f"{remaining_time}")
            elif remaining_time < 60 * 60:
                self.remaining_time.set_unit("M")
                self.remaining_time.set_value(f"{(remaining_time / 60):.2f}")
            else:
                self.remaining_time.set_unit("H")
                self.remaining_time.set_value(f"{(remaining_time / 60 / 60):.2f}")

        if data.get("line", None) != None:
            line = data.get("line")

            if line < 1000:
                self.line_card.set_unit("Line")
                self.line_card.set_value(f"{line}")
            else:
                self.line_card.set_unit("KLine")
                self.line_card.set_value(f"{(line / 1000):.2f}")

        if data.get("remaining_line", None) != None:
            remaining_line = data.get("remaining_line")

            if remaining_line < 1000:
                self.remaining_line.set_unit("Line")
                self.remaining_line.set_value(f"{remaining_line}")
            else:
                self.remaining_line.set_unit("KLine")
                self.remaining_line.set_value(f"{(remaining_line / 1000):.2f}")

        if data.get("token", None) != None:
            token = data.get("token")

            if token < 1000:
                self.token.set_unit("Token")
                self.token.set_value(f"{token}")
            else:
                self.token.set_unit("KToken")
                self.token.set_value(f"{(token / 1000):.2f}")

        if data.get("speed", None) != None:
            speed = data.get("speed")
            self.waveform.add_value(speed)

            if speed < 1000:
                self.speed.set_unit("T/S")
                self.speed.set_value(f"{speed:.2f}")
            else:
                self.speed.set_unit("KT/S")
                self.speed.set_value(f"{(speed / 1000):.2f}")

        if data.get("task", None) != None:
            task = data.get("task")

            if task < 1000:
                self.task.set_unit("Task")
                self.task.set_value(f"{task}")
            else:
                self.task.set_unit("KTask")
                self.task.set_value(f"{(task / 1000):.2f}")

        if data.get("status", None) != None:
            ring = data.get("status")

            if data.get("line", None) != None and data.get("line", None) != 0:
                percent = data.get("line") / data.get("total_line")

                ring = ring + f"\n{(percent * 100):.2f}%"
                self.ring.setValue(int(percent * 10000))

            self.ring.setFormat(ring)

    # 翻译停止完成事件
    def translation_stop_done(self, event: int, data: dict):
        self.indeterminate_hide()

        self.ring.setValue(0)
        self.ring.setFormat("无任务")
        self.action_play.setEnabled(True)

        # 更新继续翻译按钮状态
        self.emit(self.EVENT.TRANSLATION_CONTINUE_CHECK, {})

    # 翻译状态检查完成事件
    def translation_continue_check_done(self, event: int, data: dict):
        self.action_continue.setEnabled(
            data.get("translation_continue", False)
            and self.action_play.isEnabled()
        )

    # 缓存文件自动保存时间
    def cache_file_auto_save(self, event: int, data: dict):
        if self.indeterminate.isHidden():
            self.indeterminate_show("缓存文件保存中 ...")

            # 延迟关闭
            QTimer.singleShot(1000, lambda: self.indeterminate_hide())

    # 头部
    def add_widget_head(self, parent, config, window):
        self.head_hbox_container = QWidget(self)
        self.head_hbox = QHBoxLayout(self.head_hbox_container)
        parent.addWidget(self.head_hbox_container)

        # 波形图
        self.waveform = WaveformWidget()
        self.waveform.set_matrix_size(100, 20)

        waveform_vbox_container = QWidget()
        waveform_vbox = QVBoxLayout(waveform_vbox_container)
        waveform_vbox.addStretch(1)
        waveform_vbox.addWidget(self.waveform)

        # 进度环
        self.ring = ProgressRing()
        self.ring.setRange(0, 10000)
        self.ring.setValue(0)
        self.ring.setTextVisible(True)
        self.ring.setStrokeWidth(12)
        self.ring.setFixedSize(140, 140)
        self.ring.setFormat("无任务")

        ring_vbox_container = QWidget()
        ring_vbox = QVBoxLayout(ring_vbox_container)
        ring_vbox.addStretch(1)
        ring_vbox.addWidget(self.ring)

        # 添加控件
        self.head_hbox.addWidget(ring_vbox_container)
        self.head_hbox.addSpacing(8)
        self.head_hbox.addWidget(waveform_vbox_container)

    # 中部
    def add_widget_body(self, parent, config, window):
        self.flow_container = QWidget(self)
        self.flow_layout = FlowLayout(self.flow_container, needAni = False)
        self.flow_layout.setSpacing(8)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)

        self.add_time_card(self.flow_layout)
        self.add_remaining_time_card(self.flow_layout)
        self.add_line_card(self.flow_layout)
        self.add_remaining_line_card(self.flow_layout)
        self.add_speed_card(self.flow_layout)
        self.add_token_card(self.flow_layout)
        self.add_task_card(self.flow_layout)

        self.container.addWidget(self.flow_container, 1)

    # 底部
    def add_widget_foot(self, parent, config, window):
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        # 添加命令
        self.command_bar_card.set_minimum_width(512)
        self.add_command_bar_action_play(self.command_bar_card)
        self.add_command_bar_action_stop(self.command_bar_card, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_continue(self.command_bar_card, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_export(self.command_bar_card)

        # 添加信息条
        self.indeterminate = IndeterminateProgressRing()
        self.indeterminate.setFixedSize(16, 16)
        self.indeterminate.setStrokeWidth(3)
        self.indeterminate.hide()
        self.info_label = CaptionLabel("缓存文件保存中 ...", self)
        self.info_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.info_label.hide()

        self.command_bar_card.add_stretch(1)
        self.command_bar_card.add_widget(self.info_label)
        self.command_bar_card.add_spacing(4)
        self.command_bar_card.add_widget(self.indeterminate)

    # 累计时间
    def add_time_card(self, parent):
        self.time = DashboardCard(
                title = "累计时间",
                value = "未知",
                unit = "",
            )
        self.time.setFixedSize(204, 204)
        parent.addWidget(self.time)

    # 剩余时间
    def add_remaining_time_card(self, parent):
        self.remaining_time = DashboardCard(
                title = "剩余时间",
                value = "未知",
                unit = "",
            )
        self.remaining_time.setFixedSize(204, 204)
        parent.addWidget(self.remaining_time)

    # 翻译行数
    def add_line_card(self, parent):
        self.line_card = DashboardCard(
                title = "翻译行数",
                value = "未知",
                unit = "",
            )
        self.line_card.setFixedSize(204, 204)
        parent.addWidget(self.line_card)

    # 剩余行数
    def add_remaining_line_card(self, parent):
        self.remaining_line = DashboardCard(
                title = "剩余行数",
                value = "未知",
                unit = "",
            )
        self.remaining_line.setFixedSize(204, 204)
        parent.addWidget(self.remaining_line)

    # 平均速度
    def add_speed_card(self, parent):
        self.speed = DashboardCard(
                title = "平均速度",
                value = "未知",
                unit = "",
            )
        self.speed.setFixedSize(204, 204)
        parent.addWidget(self.speed)

    # 累计消耗
    def add_token_card(self, parent):
        self.token = DashboardCard(
                title = "累计消耗",
                value = "未知",
                unit = "",
            )
        self.token.setFixedSize(204, 204)
        parent.addWidget(self.token)

    # 并行任务
    def add_task_card(self, parent):
        self.task = DashboardCard(
                title = "实时任务数",
                value = "未知",
                unit = "",
            )
        self.task.setFixedSize(204, 204)
        parent.addWidget(self.task)

    # 开始
    def add_command_bar_action_play(self, parent):
        def triggered():
            self.action_play.setEnabled(False)
            self.action_stop.setEnabled(True)
            self.action_continue.setEnabled(False)
            self.emit(self.EVENT.TRANSLATION_START, {
                "translation_continue": False,
            })

        self.action_play = parent.add_action(
            Action(FluentIcon.PLAY, "开始", parent, triggered = triggered)
        )

    # 停止
    def add_command_bar_action_stop(self, parent, window):
        def triggered():
            message_box = MessageBox("警告", "停止的翻译任务可以随时继续翻译，是否确定停止任务 ... ？", window)
            message_box.yesButton.setText("确认")
            message_box.cancelButton.setText("取消")

            # 确认则触发停止翻译事件
            if message_box.exec():
                self.indeterminate_show("正在停止翻译任务 ...")

                self.action_stop.setEnabled(False)
                self.emit(self.EVENT.TRANSLATION_STOP, {})

        self.action_stop = parent.add_action(
            Action(
                FluentIcon.CANCEL_MEDIUM,
                "停止",
                parent,
                triggered = triggered,
            ),
        )
        self.action_stop.setEnabled(False)

    # 继续翻译
    def add_command_bar_action_continue(self, parent, window):
        def triggered():
            self.action_play.setEnabled(False)
            self.action_stop.setEnabled(True)
            self.action_continue.setEnabled(False)
            self.emit(self.EVENT.TRANSLATION_START, {
                "translation_continue": True,
            })

        self.action_continue = parent.add_action(
            Action(
                FluentIcon.ROTATE,
                "继续翻译",
                parent,
                triggered = triggered,
            ),
        )
        self.action_continue.setEnabled(False)

    # 导出已完成的内容
    def add_command_bar_action_export(self, parent):
        def triggered():
            pass

        parent.add_action(
            Action(FluentIcon.SHARE, "导出已完成的内容", parent, triggered = triggered),
        )

    # 显示信息条
    def indeterminate_show(self, msg: str):
        self.indeterminate.show()
        self.info_label.show()
        self.info_label.setText(msg)

    # 隐藏信息条
    def indeterminate_hide(self):
        self.indeterminate.hide()
        self.info_label.hide()
        self.info_label.setText("")