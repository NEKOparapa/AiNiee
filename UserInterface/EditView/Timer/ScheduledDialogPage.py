from PyQt5.QtCore import QTime
from qfluentwidgets import BodyLabel, MessageBoxBase, TimePicker, StrongBodyLabel

from Base.Base import Base

class ScheduledDialogPage(MessageBoxBase, Base):
    """
    定时开始任务对话框
    """
    def __init__(self, parent=None,title: str = "定时开始任务", message_box_close = None):
        super().__init__(parent=parent)

        self.message_box_close = message_box_close

        # 设置框体
        self.yesButton.setText(self.tra("确定"))
        self.cancelButton.setText((self.tra("取消")))

        self.viewLayout.setContentsMargins(16, 16, 16, 16)
        self.title_label = StrongBodyLabel(title, self)
        self.viewLayout.addWidget(self.title_label)

        # 添加说明标签
        info_label = BodyLabel(self.tra("请设置开始任务的时间"))
        self.viewLayout.addWidget(info_label)

        self.time_picker = TimePicker(self)
        current_time = QTime.currentTime()
        self.time_picker.setTime(current_time)

        self.viewLayout.addWidget(self.time_picker)

        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    def get_scheduled_time(self):
        return self.time_picker.getTime()