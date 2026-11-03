"""Display-only media progress cards, driven by workspace snapshots."""

import math

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QGridLayout, QSizePolicy, QWidget
from qfluentwidgets import FluentIcon

from Frontend.components.cards.combined_line_card import CombinedLineCard
from Frontend.components.cards.dashboard_card import DashboardCard
from Frontend.components.cards.progress_ring_card import ProgressRingCard
from Frontend.core.config import ConfigMixin


class MediaMonitoringPanel(QWidget, ConfigMixin):
    CARD_HEIGHT = 176
    SPACING = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._columns = 0
        self._rows = 2
        self._status_text = ""
        self._stage_text = self.tra("待开始")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(self.SPACING)

        self.progress_card = ProgressRingCard(
            title=self.tra("任务进度"), icon=FluentIcon.PIE_SINGLE,
            min_value=0, max_value=10000, ring_size=(108, 108),
            stroke_width=7, text_visible=True, parent=self,
        )
        self.progress_card.ring.setUseAni(False)
        self.progress_card.ring.ani.stop()
        self._font_size(self.progress_card.ring, 14)
        self.counts_card = CombinedLineCard(
            title=self.tra("条目统计"), icon=FluentIcon.DOCUMENT,
            left_title=self.tra("已完成"), right_title=self.tra("剩余"),
            initial_left_unit=self.tra("项"), initial_right_unit=self.tra("项"),
            parent=self,
        )
        self.files_card = self._dashboard("项目文件数", FluentIcon.FOLDER)
        self.elapsed_card = self._dashboard("本次用时", FluentIcon.STOP_WATCH)
        self.recognized_card = self._dashboard("已识别文件", FluentIcon.COMPLETED)
        self.status_card = DashboardCard(self.tra("任务状态"), "", "", FluentIcon.INFO, self)
        self.status_card.unitLabel.hide()
        while self.status_card.valueLayout.count():
            self.status_card.valueLayout.takeAt(0)
        self.status_card.valueLayout.setAlignment(Qt.Alignment())
        self.status_card.valueLayout.addWidget(self.status_card.valueLabel, 1)
        self.status_card.valueLabel.setAlignment(Qt.AlignCenter)
        self.status_card.valueLabel.setTextFormat(Qt.PlainText)
        self.status_card.valueLabel.setWordWrap(True)
        self.status_card.valueLabel.setMinimumWidth(0)
        self.status_card.valueLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        status_font = self.status_card.valueLabel.font()
        status_font.setPixelSize(15)
        status_font.setBold(False)
        self.status_card.valueLabel.setFont(status_font)
        self._cards = (
            self.progress_card, self.counts_card, self.files_card,
            self.elapsed_card, self.recognized_card, self.status_card,
        )
        for card in self._cards:
            card.setFixedHeight(self.CARD_HEIGHT)
            card.setMinimumWidth(0)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card.mainLayout.setContentsMargins(14, 12, 14, 12)
            card.titleLabel.setTextColor("#606060", "#dedede")
            card.titleLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            card.topLayout.setSpacing(7)
            if card.iconWidget:
                card.iconWidget.setFixedSize(16, 16)
        self.counts_card.bottomLayout.setSpacing(10)
        for label in (self.counts_card.leftUnitLabel, self.counts_card.rightUnitLabel):
            label.setTextColor("#606060", "#dedede")
            self._font_size(label, 12)
        for label in (self.counts_card.leftTitleLabel, self.counts_card.rightTitleLabel):
            label.setTextColor("#707070", "#a6a6a6")
        separator = self.counts_card.bottomLayout.itemAt(1).layout().itemAt(1).widget()
        separator.setStyleSheet("background-color: rgba(128, 128, 128, 0.28);")
        self._reflow(self.width())
        self.set_metrics()

    @staticmethod
    def _font_size(label, pixels):
        font = label.font()
        font.setPixelSize(pixels)
        label.setFont(font)

    def _dashboard(self, title, icon):
        card = DashboardCard(self.tra(title), "0", "", icon, self)
        card.unitLabel.setTextColor("#606060", "#dedede")
        self._font_size(card.valueLabel, 32)
        self._font_size(card.unitLabel, 12)
        return card

    @staticmethod
    def _count(value):
        try:
            return max(0, int(value))
        except (ValueError, TypeError, OverflowError):
            return 0

    def _count_text(self, value, unit):
        if value < 10000:
            return str(value), self.tra(unit)
        scale, suffix = (100000000, "亿") if value >= 100000000 else (10000, "万")
        number = f"{value / scale:.1f}".rstrip("0").rstrip(".")
        return number, self.tra(suffix) + self.tra(unit)

    def _set_count(self, card, value):
        number, unit = self._count_text(value, "个")
        card.set_value(number)
        card.set_unit(unit)
        card.setToolTip(f"{value:,}{self.tra(' 个文件')}")

    def set_metrics(self, *, completed=0, total=0, files=0, recognized=0,
                    elapsed=0, stage="", status="", running=False, generation=False):
        """Apply observed counts and elapsed seconds without starting any work."""
        total = self._count(total)
        completed = min(self._count(completed), total) if total else 0
        remaining = max(0, total - completed)
        unit = "页" if generation else "项"
        self.counts_card.set_main_title(self.tra("页数统计" if generation else "条目统计"))
        self.counts_card.set_left_data(*self._count_text(completed, unit))
        self.counts_card.set_right_data(*self._count_text(remaining, unit))
        self.counts_card.setToolTip(
            f"{self.tra('已完成')} {completed:,} / {total:,} {self.tra(unit)}")
        self._set_count(self.files_card, self._count(files))
        self.recognized_card.titleLabel.setText(self.tra("已生成译图" if generation else "已识别文件"))
        self._set_count(self.recognized_card, completed if generation else self._count(recognized))

        try:
            seconds = float(elapsed)
        except (ValueError, TypeError, OverflowError):
            seconds = 0
        seconds = int(seconds) if math.isfinite(seconds) and seconds >= 0 else 0
        hours, rest = divmod(seconds, 3600)
        minutes, seconds_part = divmod(rest, 60)
        duration = f"{hours}:{minutes:02d}:{seconds_part:02d}" if hours else f"{minutes:02d}:{seconds_part:02d}"
        self.elapsed_card.set_value(duration)
        self.elapsed_card.set_unit("")
        self.elapsed_card.setToolTip(duration)
        self._font_size(self.elapsed_card.valueLabel, 26 if hours else 32)

        if stage:
            stage_text = " ".join(str(stage).split())
        elif not total:
            stage_text = self.tra("待开始")
        elif running:
            stage_text = self.tra("处理中")
        elif completed == total:
            stage_text = self.tra("已完成")
        else:
            stage_text = self.tra("待继续" if completed else "待开始")
        self._stage_text = stage_text or self.tra("待开始")
        if str(status or "").strip():
            self._status_text = str(status).strip()
        self._update_status()
        short_status = self.progress_card.ring.fontMetrics().elidedText(self._stage_text, Qt.ElideRight, 84)
        progress = completed * 10000 // total if total else 0
        self.progress_card.set_value(progress)
        self.progress_card.set_format("%p%\n" + short_status if total else short_status)
        self.progress_card.setToolTip(self._stage_text)

    def set_status(self, text):
        """Keep detailed status across metric refreshes; empty text restores the stage."""
        self._status_text = str(text or "").strip()
        self._update_status()

    def _update_status(self):
        text = self._status_text or self._stage_text or self.tra("待开始")
        self.status_card.set_value(text)
        self.status_card.setToolTip(text)
        self.status_card.valueLabel.setToolTip(text)

    @staticmethod
    def _column_count(width):
        return 4 if width >= 760 else 3 if width >= 600 else 2

    def _reflow(self, width):
        columns = self._column_count(width)
        if columns == self._columns:
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(4):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
            self.grid.setColumnMinimumWidth(column, 0)
        if columns == 4:
            positions = (
                (self.progress_card, 0, 0, 1), (self.counts_card, 0, 1, 2),
                (self.files_card, 0, 3, 1), (self.elapsed_card, 1, 0, 1),
                (self.recognized_card, 1, 1, 1), (self.status_card, 1, 2, 2),
            )
            self._rows = 2
        else:
            positions = tuple((card, index // columns, index % columns, 1)
                              for index, card in enumerate(self._cards))
            self._rows = 2 if columns == 3 else 3
        for card, row, column, span in positions:
            self.grid.addWidget(card, row, column, 1, span)
        for label in (self.counts_card.leftValueLabel, self.counts_card.rightValueLabel):
            self._font_size(label, 32 if columns == 4 else 26)
        self.setFixedHeight(self._rows * self.CARD_HEIGHT + (self._rows - 1) * self.SPACING)
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow(event.size().width())

    def sizeHint(self):
        return QSize(840, self._rows * self.CARD_HEIGHT + (self._rows - 1) * self.SPACING)

    def minimumSizeHint(self):
        return QSize(340, self.sizeHint().height())
