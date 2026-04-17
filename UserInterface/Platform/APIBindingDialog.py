from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from qfluentwidgets import CaptionLabel, ComboBox, MessageBoxBase, StrongBodyLabel

from ModuleFolders.Config.Config import ConfigMixin


class APIBindingDialog(MessageBoxBase, ConfigMixin):
    ROLE_ITEMS = (
        ("extract", "提取接口", "分析流程使用的接口平台"),
        ("translate", "翻译接口", "翻译流程使用的接口平台"),
        ("polish", "润色接口", "润色流程使用的接口平台"),
    )

    def __init__(self, window, platform_options: list[tuple[str, str]], api_settings: dict):
        super().__init__(window)

        self.platform_options = list(platform_options or [])
        self.api_settings = dict(api_settings or {})
        self.combo_boxes = {}

        self.widget.setMinimumSize(520, 340)
        self.yesButton.setText(self.tra("保存"))
        self.cancelButton.setText(self.tra("取消"))
        self.yesButton.setEnabled(bool(self.platform_options))

        self._build_ui()

    def _build_ui(self) -> None:
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        self.viewLayout.setSpacing(12)

        title = StrongBodyLabel(self.tra("功能接口绑定"))
        title.setStyleSheet("font-size: 18px;")
        self.viewLayout.addWidget(title)

        description = CaptionLabel(
            self.tra("分别为提取、翻译和润色流程选择接口平台。未单独设置时默认回落到当前激活接口。")
        )
        description.setWordWrap(True)
        self.viewLayout.addWidget(description)

        for role_key, title_text, desc_text in self.ROLE_ITEMS:
            row = QFrame(self.widget)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(16)

            text_layout = QVBoxLayout()
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)

            title_label = StrongBodyLabel(self.tra(title_text), row)
            desc_label = CaptionLabel(self.tra(desc_text), row)
            desc_label.setWordWrap(True)

            text_layout.addWidget(title_label)
            text_layout.addWidget(desc_label)
            layout.addLayout(text_layout, 1)

            combo_box = ComboBox(row)
            combo_box.setMinimumWidth(200)
            for _, platform_name in self.platform_options:
                combo_box.addItem(platform_name)
            combo_box.setCurrentIndex(self._find_current_index(role_key))

            layout.addWidget(combo_box)
            self.combo_boxes[role_key] = combo_box
            self.viewLayout.addWidget(row)

    def _resolve_current_tag(self, role_key: str) -> str | None:
        valid_tags = {tag for tag, _ in self.platform_options}
        role_tag = self.api_settings.get(role_key)
        if role_tag in valid_tags:
            return role_tag

        active_tag = self.api_settings.get("active")
        if active_tag in valid_tags:
            return active_tag

        if self.platform_options:
            return self.platform_options[0][0]

        return None

    def _find_current_index(self, role_key: str) -> int:
        current_tag = self._resolve_current_tag(role_key)
        for index, (tag, _) in enumerate(self.platform_options):
            if tag == current_tag:
                return index
        return 0

    def get_bindings(self) -> dict:
        bindings = {}
        for role_key, combo_box in self.combo_boxes.items():
            index = combo_box.currentIndex()
            bindings[role_key] = self.platform_options[index][0] if 0 <= index < len(self.platform_options) else None
        return bindings
