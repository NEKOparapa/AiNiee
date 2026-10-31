from qfluentwidgets import CaptionLabel, ComboBox, LineEdit, MessageBoxBase, StrongBodyLabel

from Frontend.core.config import ConfigMixin


class PublicTableSelectDialog(ConfigMixin, MessageBoxBase):
    """Choose an explicit destination before adding project analysis rows."""

    def __init__(self, tables: list[dict], active_table_id: str | None = None, parent=None):
        super().__init__(parent)
        self._table_ids = [table["id"] for table in tables]
        self.viewLayout.addWidget(StrongBodyLabel(self.tra("选择目标表"), self))
        note = CaptionLabel(self.tra("新增条目只写入所选表，不改变该表的启用状态。"), self)
        note.setWordWrap(True)
        self.viewLayout.addWidget(note)

        self.table_combo = ComboBox(self)
        self.table_combo.setMinimumWidth(360)
        for table in tables:
            suffix = "" if table.get("enabled") else f" ({self.tra('已停用')})"
            self.table_combo.addItem(table["name"] + suffix)
        self.table_combo.addItem(self.tra("新建表…"))
        self.viewLayout.addWidget(self.table_combo)

        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText(self.tra("新表名称"))
        self.name_edit.setText(self.tra("项目提取表"))
        self.viewLayout.addWidget(self.name_edit)
        self.table_combo.currentIndexChanged.connect(self._update_name_visibility)
        self.name_edit.textChanged.connect(self._update_name_visibility)
        index = self._table_ids.index(active_table_id) if active_table_id in self._table_ids else 0
        self.table_combo.setCurrentIndex(index)
        self._update_name_visibility()
        self.yesButton.setText(self.tra("确认"))
        self.cancelButton.setText(self.tra("取消"))

    @property
    def table_id(self) -> str | None:
        index = self.table_combo.currentIndex()
        return self._table_ids[index] if 0 <= index < len(self._table_ids) else None

    @property
    def new_table_name(self) -> str:
        return self.name_edit.text().strip() if self.table_id is None else ""

    def _update_name_visibility(self, *_args) -> None:
        creating = self.table_id is None
        self.name_edit.setVisible(creating)
        self.yesButton.setEnabled(not creating or bool(self.name_edit.text().strip()))

    def validate(self) -> bool:
        return self.table_id is not None or bool(self.new_table_name)
