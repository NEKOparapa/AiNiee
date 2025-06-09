import threading
import time
from PyQt5.QtWidgets import QLayout, QWidget, QVBoxLayout
from qfluentwidgets import (FlowLayout,FluentIcon as FIF)

from Base.Base import Base
from Widget.DashboardCard import DashboardCard
from Widget.WaveformCard import WaveformCard
from Widget.ProgressRingCard import ProgressRingCard
from Widget.CombinedLineCard import CombinedLineCard

# 监控页面
class MonitoringPage(Base,QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)  # 左、上、右、下

        # 添加控件
        self.head_hbox_container = QWidget(self)
        self.head_hbox = FlowLayout(self.head_hbox_container, needAni=False)
        self.head_hbox.setSpacing(8)
        self.head_hbox.setContentsMargins(0, 0, 0, 0)

        # 添加卡片控件
        self.add_combined_line_card(self.head_hbox)
        self.add_token_card(self.head_hbox)
        self.add_task_card(self.head_hbox)
        self.add_time_card(self.head_hbox)
        self.add_remaining_time_card(self.head_hbox)
        self.add_ring_card(self.head_hbox)
        self.add_waveform_card(self.head_hbox)
        self.add_speed_card(self.head_hbox)
        self.add_stability_card(self.head_hbox)

        # 添加到主容器
        self.container.addWidget(self.head_hbox_container, 1)

        # 注册事件
        self.subscribe(Base.EVENT.TRANSLATION_UPDATE, self.translation_update)

        # 监控页面数据存储
        self.data = {}


    # 进度环
    def add_ring_card(self, parent: QLayout) -> None:
        self.ring = ProgressRingCard(title="任务进度",
                                    icon=FIF.PIE_SINGLE,
                                    min_value=0,
                                    max_value=10000,
                                    ring_size=(140, 140),
                                    text_visible=True)
        self.ring.setFixedSize(204, 204)
        self.ring.set_format("无任务")
        parent.addWidget(self.ring)

    # 波形图
    def add_waveform_card(self, parent: QLayout) -> None:
        self.waveform = WaveformCard("波形图",
                                    icon=FIF.MARKET
                                    )
        self.waveform.set_draw_grid(False)  # 关闭网格线
        self.waveform.setFixedSize(633, 204)
        parent.addWidget(self.waveform)

    # 累计时间
    def add_time_card(self, parent: QLayout) -> None:
        self.time = DashboardCard(
                title="累计时间",
                value="Time",
                unit="",
                icon=FIF.STOP_WATCH,
            )
        self.time.setFixedSize(204, 204)
        parent.addWidget(self.time)

    # 剩余时间
    def add_remaining_time_card(self, parent: QLayout) -> None:
        self.remaining_time = DashboardCard(
                title="剩余时间",
                value="Time",
                unit="",
                icon=FIF.FRIGID,
            )
        self.remaining_time.setFixedSize(204, 204)
        parent.addWidget(self.remaining_time)

    # 行数统计
    def add_combined_line_card(self, parent: QLayout) -> None:

        self.combined_line_card = CombinedLineCard(
            title="行数统计",
            icon=FIF.PRINT,
            left_title="已完成",
            right_title="剩余",
            initial_left_value="0",
            initial_left_unit="Line",
            initial_right_value="0",
            initial_right_unit="Line",
            parent=self
        )

        self.combined_line_card.setFixedSize(416, 204)
        parent.addWidget(self.combined_line_card)

    # 平均速度
    def add_speed_card(self, parent: QLayout) -> None:
        self.speed = DashboardCard(
                title="平均速度",
                value="T/S",
                unit="",
                icon=FIF.SPEED_HIGH,
            )
        self.speed.setFixedSize(204, 204)
        parent.addWidget(self.speed)

    # 累计消耗
    def add_token_card(self, parent: QLayout) -> None:
        self.token = DashboardCard(
                title="累计消耗",
                value="Token",
                unit="",
                icon=FIF.CALORIES,
            )
        self.token.setFixedSize(204, 204)
        parent.addWidget(self.token)

    # 并行任务
    def add_task_card(self, parent: QLayout) -> None:
        self.task = DashboardCard(
                title="实时任务数",
                value="0",
                unit="",
                icon=FIF.SCROLL,
            )
        self.task.setFixedSize(204, 204)
        parent.addWidget(self.task)

    # 稳定性
    def add_stability_card(self, parent: QLayout) -> None:
        self.stability = DashboardCard(
                title="任务稳定性",
                value="%",
                unit="",
                icon=FIF.TRAIN,
            )
        self.stability.setFixedSize(204, 204)
        parent.addWidget(self.stability)


    # 监控页面更新事件
    def translation_update(self, event: int, data: dict) -> None:
        if Base.work_status in (Base.STATUS.STOPING, Base.STATUS.TRANSLATING):
            self.update_time(event, data)
            self.update_line(event, data)
            self.update_token(event, data)
            self.update_stability(event, data)

        self.update_task(event, data)
        self.update_status(event, data)

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

