from qfluentwidgets import MessageBoxBase


class UpdateMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hideCancelButton()
        self.hideYesButton()

        self.viewLayout.setContentsMargins(10, 10, 8, 8)
        self.viewLayout.setSpacing(6)
        self.buttonGroup.hide()
