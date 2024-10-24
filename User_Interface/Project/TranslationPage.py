import random

from PyQt5.Qt import QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import FlowLayout
from qfluentwidgets import ProgressRing

from Base.AiNieeBase import AiNieeBase
from Widget.Separator import Separator
from Widget.DashboardCard import DashboardCard
from Widget.WaveformWidget import WaveformWidget
from Widget.CommandBarCard import CommandBarCard

class TranslationPage(QWidget, AiNieeBase):

    DEFAULT = {}

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

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
        self.ring.setValue(2222)
        self.ring.setTextVisible(True)
        self.ring.setStrokeWidth(12)
        self.ring.setFixedSize(140, 140)
        self.ring.setFormat("正在翻译\n66.66%")

        ring_vbox_container = QWidget()
        ring_vbox = QVBoxLayout(ring_vbox_container)
        ring_vbox.addStretch(1)
        ring_vbox.addWidget(self.ring)

        # 添加控件
        self.head_hbox.addWidget(ring_vbox_container)
        self.head_hbox.addSpacing(8)
        self.head_hbox.addWidget(waveform_vbox_container)

        def tick():
            self.ring.setValue(self.ring.value() + 50)
            self.ring.setFormat(f"正在翻译\n{self.ring.value() * 0.01:.2f}%")
            self.waveform.add_value(random.randint(9900, 10000))

        self.timer = QTimer(self)
        self.timer.timeout.connect(tick)
        self.timer.start(666)
        
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
        self.add_command_bar_action_play(self.command_bar_card)
        self.add_command_bar_action_pause(self.command_bar_card)
        self.add_command_bar_action_continue(self.command_bar_card)
        self.add_command_bar_action_cancel(self.command_bar_card)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_export(self.command_bar_card)

    # 累计时间
    def add_time_card(self, parent):
        w = DashboardCard(
            title = "累计时间",
            value = "1.25",
            unit = "H",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)

    # 剩余时间
    def add_remaining_time_card(self, parent):
        w = DashboardCard(
            title = "剩余时间",
            value = "42.14",
            unit = "M",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)

    # 总计行数
    def add_line_card(self, parent):
        w = DashboardCard(
            title = "总计行数",
            value = "26.13",
            unit = "KLine",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)

    # 剩余行数
    def add_remaining_line_card(self, parent):
        w = DashboardCard(
            title = "剩余行数",
            value = "986",
            unit = "Line",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)

    # 平均速度
    def add_speed_card(self, parent):
        w = DashboardCard(
            title = "平均速度",
            value = "256",
            unit = "KT/S",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)
        
    # 累计消耗
    def add_token_card(self, parent):
        w = DashboardCard(
            title = "累计消耗",
            value = "894",
            unit = "KToken",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)

    # 并行任务
    def add_task_card(self, parent):
        w = DashboardCard(
            title = "并行任务",
            value = "16",
            unit = "Task",
        )
        w.setFixedSize(204, 204)

        parent.addWidget(w)

    # 开始
    def add_command_bar_action_play(self, parent):
        def triggered():
            self.action_play.setEnabled(False)
            self.action_pause.setEnabled(True)
            self.action_continue.setEnabled(False)
            self.action_cancel.setEnabled(True)

        self.action_play = parent.add_action(
            Action(FluentIcon.PLAY, "开始", parent, triggered = triggered)
        )
        
    # 暂停
    def add_command_bar_action_pause(self, parent):
        def triggered():
            self.action_play.setEnabled(False)
            self.action_pause.setEnabled(False)
            self.action_continue.setEnabled(True)
            self.action_cancel.setEnabled(True)

        self.action_pause = parent.add_action(
            Action(FluentIcon.PAUSE, "暂停", parent, triggered = triggered),
        )
        self.action_pause.setEnabled(False)

    # 继续
    def add_command_bar_action_continue(self, parent):
        def triggered():
            self.action_play.setEnabled(False)
            self.action_pause.setEnabled(True)
            self.action_continue.setEnabled(False)
            self.action_cancel.setEnabled(True)

        self.action_continue = parent.add_action(
            Action(FluentIcon.PLAY, "继续", parent, triggered = triggered),
        )
        self.action_continue.setEnabled(False)

    # 取消
    def add_command_bar_action_cancel(self, parent):
        def triggered():
            self.action_play.setEnabled(True)
            self.action_pause.setEnabled(False)
            self.action_continue.setEnabled(False)
            self.action_cancel.setEnabled(False)

        self.action_cancel = parent.add_action(
            Action(FluentIcon.CANCEL, "取消", parent, triggered = triggered),
        )
        self.action_cancel.setEnabled(False)

    # 导出已完成的任务和缓存
    def add_command_bar_action_export(self, parent):
        def triggered():
            pass

        parent.addAction(
            Action(FluentIcon.SHARE, "导出已完成的任务和缓存", parent, triggered = triggered),
        )