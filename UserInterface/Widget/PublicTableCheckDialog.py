from PyQt5.QtWidgets import QFrame, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, CheckBox, HorizontalSeparator, MessageBoxBase, ScrollArea, StrongBodyLabel


class PublicTableCheckDialog(MessageBoxBase):
    """Select existing subtables for a file import or export."""

    def __init__(self, tables, title, note, translate, parent, selected_ids=None):
        super().__init__(parent)
        self._checkboxes = []
        self.viewLayout.addWidget(StrongBodyLabel(title, self))
        description = CaptionLabel(note, self)
        description.setWordWrap(True)
        self.viewLayout.addWidget(description)
        self.widget.setMinimumWidth(440)

        self.viewLayout.addWidget(HorizontalSeparator(self))

        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setObjectName("publicTableCheckViewport")
        scroll.viewport().setStyleSheet("QWidget#publicTableCheckViewport { background: transparent; }")
        contents = QWidget(scroll)
        contents.setObjectName("publicTableCheckContents")
        contents.setStyleSheet("QWidget#publicTableCheckContents { background: transparent; }")
        layout = QVBoxLayout(contents)
        layout.setContentsMargins(4, 4, 12, 4)
        layout.setSpacing(8)
        selected = {table["id"] for table in tables} if selected_ids is None else set(selected_ids)
        for table in tables:
            status = translate("已启用") if table["enabled"] else translate("已停用")
            count = translate("{0} 条").format(len(table["rows"]))
            checkbox = CheckBox(f"{table['name']} · {count} · {status}", contents)
            checkbox.setMinimumHeight(32)
            checkbox.setToolTip(table["name"])
            checkbox.setChecked(table["id"] in selected)
            checkbox.stateChanged.connect(self._update_selection)
            self._checkboxes.append((table["id"], checkbox))
            layout.addWidget(checkbox)
        layout.addStretch(1)
        scroll.setWidget(contents)
        content_height = layout.sizeHint().expandedTo(layout.minimumSize()).height()
        scroll.setFixedHeight(min(300, max(44, content_height)))
        self.viewLayout.addWidget(scroll)

        self.yesButton.setText(translate("确认"))
        self.cancelButton.setText(translate("取消"))
        self._update_selection()

    @property
    def selected_ids(self):
        return [table_id for table_id, checkbox in self._checkboxes if checkbox.isChecked()]

    def _update_selection(self, *_args):
        self.yesButton.setEnabled(bool(self.selected_ids))

    def validate(self):
        return bool(self.selected_ids)
