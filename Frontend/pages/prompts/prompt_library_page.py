"""Shared prompt library and editor for extraction, translation and polishing."""

import re
import uuid

from PyQt5.QtCore import QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QSyntaxHighlighter, QTextBlockFormat, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel, CardWidget, FluentIcon, HorizontalSeparator, LineEdit,
    MessageBoxBase, PrimaryPushButton, ScrollArea, SearchLineEdit,
    StrongBodyLabel, SubtitleLabel, TextEdit,
    TransparentToolButton, getFont, isDarkTheme, qconfig, themeColor,
)

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin


def secondary_label(text, parent):
    label = CaptionLabel(text, parent)
    label.setTextFormat(Qt.PlainText)
    label.setTextColor(QColor("#717784"), QColor("#a6abb5"))
    return label


def format_prompt_text(editor):
    """Increase reading space without modifying the prompt's plain text."""
    cursor = QTextCursor(editor.document())
    cursor.select(QTextCursor.Document)
    block = QTextBlockFormat()
    block.setLineHeight(132, QTextBlockFormat.ProportionalHeight)
    cursor.mergeBlockFormat(block)


class PromptHighlighter(QSyntaxHighlighter):
    """Quiet source highlighting; copying/editing always keeps the original text."""

    def highlightBlock(self, text):
        dark = isDarkTheme()
        heading = re.match(r"^(\s*#{1,6}\s+|【).+", text)
        if heading:
            style = QTextCharFormat()
            style.setFontWeight(QFont.DemiBold)
            style.setForeground(QColor("#edf0f5" if dark else "#242b37"))
            self.setFormat(0, len(text), style)
        for match in re.finditer(r"\{[A-Za-z_]\w*\}|</?[A-Za-z][^>]*>", text):
            style = QTextCharFormat()
            style.setForeground(QColor("#a6c1e4" if dark else "#5b7399"))
            self.setFormat(match.start(), len(match.group()), style)


class PromptWorkspace(QFrame):
    """Transparent workspace with an outline and a divider between the panes."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.setClipPath(path)
        dark = isDarkTheme()
        page = self.parentWidget()
        library = page.library_panel.geometry()
        painter.setPen(QColor("#35373c" if dark else "#e7e9ee"))
        if page._compact:
            painter.drawLine(0, library.bottom(), self.width(), library.bottom())
        else:
            painter.drawLine(library.right(), 0, library.right(), self.height())
        painter.setClipping(False)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)


class PromptNameLabel(SubtitleLabel):
    """Keep long user-defined names from pushing the reading area off-screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.full_text = ""
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setFont(getFont(17, QFont.DemiBold))

    def set_prompt_name(self, text):
        self.full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.setText(self.fontMetrics().elidedText(text, Qt.ElideRight, self.width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, self.width()))


class PromptCard(CardWidget, ConfigMixin):
    prompt_selected = pyqtSignal(dict)

    def __init__(self, prompt_data, parent=None):
        super().__init__(parent)
        self.prompt_data = prompt_data
        self.is_system = prompt_data.get("type") == "system"
        self._selected = False
        self.setFixedHeight(62)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(prompt_data["name"])
        self.setToolTip(prompt_data["name"])
        self.setClickEnabled(True)
        self.setBorderRadius(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 10, 28, 10)
        layout.setSpacing(3)
        self.name_label = StrongBodyLabel(self)
        self.name_label.setTextFormat(Qt.PlainText)
        self.preview_label = secondary_label("", self)
        self._preview = prompt_data.get("summary") or self.tra("{count} 字符").format(
            count=f"{len(prompt_data['content']):,}")
        for label in (self.name_label, self.preview_label):
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(0, self.width() - 68)
        self.name_label.setText(self.name_label.fontMetrics().elidedText(
            self.prompt_data["name"], Qt.ElideRight, width))
        self.preview_label.setText(self.preview_label.fontMetrics().elidedText(
            self._preview, Qt.ElideRight, width))

    def set_selected_style(self):
        self._selected = True
        self.setAccessibleDescription(self.tra("使用中"))
        self.update()

    def set_default_style(self):
        self._selected = False
        self.setAccessibleDescription("")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        accent = themeColor()
        painter.setPen(Qt.NoPen)
        if self._selected:
            fill = QColor(accent)
            fill.setAlpha(38 if isDarkTheme() else 28)
            painter.setBrush(fill)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
            FluentIcon.ACCEPT.render(painter, QRect(self.width() - 24, 24, 12, 12), fill=accent.name())
        elif self.isHover:
            painter.setBrush(QColor(255, 255, 255, 10) if isDarkTheme() else QColor(0, 0, 0, 7))
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
        icon = FluentIcon.DOCUMENT if self.is_system else FluentIcon.EDIT
        icon.render(painter, QRect(13, 22, 16, 16), fill=(accent.name() if self._selected else
                    ("#a5abb6" if isDarkTheme() else "#89919f")))
        if self.hasFocus() and self.window().testAttribute(Qt.WA_KeyboardFocusChange):
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(accent, 1))
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 6, 6)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()) and self.isPressed:
            self.prompt_selected.emit(self.prompt_data)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.prompt_selected.emit(self.prompt_data)
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()


class AddEditPromptDialog(MessageBoxBase, ConfigMixin):
    def __init__(self, prompt_data=None, parent=None):
        super().__init__(parent)
        self.prompt_data = prompt_data
        self.is_edit_mode = prompt_data is not None
        self.yesButton.setText(self.tra("保存"))
        self.cancelButton.setText(self.tra("取消"))
        self.viewLayout.setSpacing(12)
        self.viewLayout.setContentsMargins(28, 26, 28, 24)
        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.buttonLayout.addStretch(1)
        self.buttonLayout.addWidget(self.cancelButton)
        self.buttonLayout.addWidget(self.yesButton)
        self.yesButton.setMinimumWidth(100)
        self.cancelButton.setMinimumWidth(88)
        self.buttonGroup.setFixedHeight(76)

        title = self.tra("编辑提示词") if self.is_edit_mode else self.tra("新建提示词")
        self.viewLayout.addWidget(SubtitleLabel(title, self))
        hint = secondary_label(self.tra("为提示词命名，填写你希望模型遵循的指令。"), self)
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(StrongBodyLabel(self.tra("提示词名称"), self))
        self.name_edit = LineEdit(self)
        self.name_edit.setObjectName("promptNameInput")
        self.name_edit.setPlaceholderText(self.tra("输入便于识别的名称"))
        self.name_edit.setAccessibleName(self.tra("提示词名称"))
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addSpacing(4)

        content_header = QHBoxLayout()
        content_header.addWidget(StrongBodyLabel(self.tra("提示词内容"), self))
        content_header.addStretch(1)
        self.character_count_label = secondary_label("", self)
        content_header.addWidget(self.character_count_label)
        self.viewLayout.addLayout(content_header)
        self.content_edit = TextEdit(self)
        self.content_edit.setObjectName("promptContentInput")
        self.content_edit.setAcceptRichText(False)
        self.content_edit.setPlaceholderText(self.tra("在此输入提示词…"))
        self.content_edit.setAccessibleName(self.tra("提示词内容"))
        self.content_edit.document().setDocumentMargin(12)
        self.content_edit.setMinimumHeight(100)
        self.highlighter = PromptHighlighter(self.content_edit.document())
        self.viewLayout.addWidget(self.content_edit, 1)

        if self.is_edit_mode:
            self.name_edit.setText(prompt_data["name"])
            self.content_edit.setPlainText(prompt_data["content"])
        format_prompt_text(self.content_edit)
        self.name_edit.textChanged.connect(self.update_form_state)
        self.content_edit.textChanged.connect(self.update_form_state)
        self.update_form_state()
        self.fit_to_parent()
        self.update_theme()
        qconfig.themeChangedFinished.connect(self.update_theme)

    def update_theme(self):
        dark = isDarkTheme()
        border = "#40434a" if dark else "#e2e5eb"
        text = "#e3e5e9" if dark else "#303642"
        self.name_edit.setStyleSheet(
            f"LineEdit#promptNameInput {{ border: 1px solid {border}; border-radius: 6px; "
            f"background: {'#2b2d32' if dark else '#ffffff'}; color: {text}; padding: 0 10px; }}")
        self.content_edit.setStyleSheet(
            f"TextEdit#promptContentInput {{ border: 1px solid {border}; border-radius: 6px; "
            f"background: {'#232529' if dark else '#fafbfc'}; color: {text}; padding: 4px; }}")
        self.highlighter.rehighlight()

    def fit_to_parent(self):
        parent = self.parentWidget()
        if parent:
            self.widget.setFixedSize(min(800, max(1, parent.width() - 48)),
                                     min(700, max(1, parent.height() - 48)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_to_parent()

    def update_form_state(self):
        content = self.content_edit.toPlainText()
        self.character_count_label.setText(self.tra("{count} 字符").format(count=f"{len(content):,}"))
        self.yesButton.setEnabled(bool(self.name_edit.text().strip() and content.strip()))

    def validate(self):
        return bool(self.name_edit.text().strip() and self.content_edit.toPlainText().strip())

    def get_data(self):
        if not self.validate():
            return None
        return {
            "id": self.prompt_data["id"] if self.is_edit_mode else str(uuid.uuid4()),
            "name": self.name_edit.text().strip(),
            "content": self.content_edit.toPlainText().strip(),
            "type": "user",
        }


class PromptLibraryPage(QFrame, ConfigMixin, Base):
    """One selection/CRUD flow; each page supplies its own presets and config keys."""

    def __init__(self, text, window, *, title, description, presets, user_prompts,
                 selected_id, selection_key, user_data_key, guidance=""):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))
        self.default_prompt = presets
        self.user_prompts = user_prompts
        self.selection_key = selection_key
        self.user_data_key = user_data_key
        self.selected_prompt_id = selected_id
        self.selected_prompt_card = None
        self.cards = []
        self.groups = []
        self._compact = None
        self.init_ui(title, description, guidance)
        self.update_prompt_cards(selected_id)
        qconfig.themeChangedFinished.connect(self.update_theme)
        qconfig.themeColorChanged.connect(self.update_theme)
        self.update_theme()

    def init_ui(self, title, description, guidance):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 26, 28, 24)
        main_layout.setSpacing(22)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(6)
        title_label = SubtitleLabel(title, self)
        title_label.setFont(getFont(22, QFont.DemiBold))
        title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        heading.addWidget(title_label)
        self.description_label = secondary_label(description, self)
        self.description_label.setWordWrap(True)
        heading.addWidget(self.description_label)
        header.addLayout(heading, 1)
        header.addSpacing(16)
        self.add_new_prompt_button = PrimaryPushButton(FluentIcon.ADD, self.tra("新建提示词"), self)
        self.add_new_prompt_button.setFixedHeight(34)
        self.add_new_prompt_button.clicked.connect(self.open_add_prompt_dialog)
        header.addWidget(self.add_new_prompt_button, 0, Qt.AlignVCenter)
        main_layout.addLayout(header)

        self.workspace = PromptWorkspace(self)
        self.workspace_layout = QHBoxLayout(self.workspace)
        self.workspace_layout.setContentsMargins(1, 1, 1, 1)
        self.workspace_layout.setSpacing(0)
        main_layout.addWidget(self.workspace, 1)

        self.library_panel = QWidget(self.workspace)
        self.library_layout = QVBoxLayout(self.library_panel)
        self.library_layout.setContentsMargins(14, 20, 14, 16)
        self.library_layout.setSpacing(14)
        self.library_header_layout = QHBoxLayout()
        self.library_header_layout.setContentsMargins(4, 0, 4, 0)
        self.library_header_layout.addWidget(StrongBodyLabel(self.tra("提示词库"), self.library_panel), 1)
        self.library_count_label = secondary_label("", self.library_panel)
        self.library_header_layout.addWidget(self.library_count_label)
        self.library_layout.addLayout(self.library_header_layout)
        self.search_edit = SearchLineEdit(self.library_panel)
        self.search_edit.setObjectName("promptSearch")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setPlaceholderText(self.tra("搜索名称或内容"))
        self.search_edit.setAccessibleName(self.tra("搜索名称或内容"))
        self.search_edit.textChanged.connect(self.filter_cards)
        self.library_layout.addWidget(self.search_edit)

        self.scroll_area = ScrollArea(self.library_panel)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll_area.viewport().setStyleSheet("background: transparent;")
        self.card_container_widget = QWidget()
        self.card_container_widget.setObjectName("promptCardContainer")
        self.card_container_widget.setStyleSheet("QWidget#promptCardContainer { background: transparent; }")
        self.card_list_layout = QVBoxLayout(self.card_container_widget)
        self.card_list_layout.setContentsMargins(0, 0, 4, 0)
        self.card_list_layout.setSpacing(3)
        self.scroll_area.setWidget(self.card_container_widget)
        self.library_layout.addWidget(self.scroll_area, 1)
        self.selection_hint = secondary_label(self.tra("选择后自动应用"), self.library_panel)
        self.selection_hint.setContentsMargins(4, 0, 0, 0)
        self.library_layout.addWidget(self.selection_hint)
        self.workspace_layout.addWidget(self.library_panel)

        self.preview_panel = QWidget(self.workspace)
        self.preview_panel.setMinimumWidth(0)
        preview_layout = QVBoxLayout(self.preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self.preview_toolbar = QWidget(self.preview_panel)
        self.preview_toolbar.setFixedHeight(68)
        toolbar = QHBoxLayout(self.preview_toolbar)
        toolbar.setContentsMargins(28, 0, 22, 0)
        toolbar.setSpacing(12)
        self.selected_prompt_name_label = PromptNameLabel(self.preview_toolbar)
        toolbar.addWidget(self.selected_prompt_name_label, 1, Qt.AlignVCenter)
        self.selected_prompt_type_label = secondary_label("", self.preview_toolbar)
        self.selected_prompt_type_label.setContentsMargins(7, 3, 7, 3)
        toolbar.addWidget(self.selected_prompt_type_label, 0, Qt.AlignVCenter)
        self.edit_prompt_button = TransparentToolButton(FluentIcon.EDIT, self.preview_toolbar)
        self.edit_prompt_button.setToolTip(self.tra("编辑"))
        self.edit_prompt_button.setAccessibleName(self.tra("编辑"))
        self.edit_prompt_button.clicked.connect(self.edit_current_prompt)
        toolbar.addWidget(self.edit_prompt_button)
        self.delete_prompt_button = TransparentToolButton(FluentIcon.DELETE, self.preview_toolbar)
        self.delete_prompt_button.setToolTip(self.tra("删除"))
        self.delete_prompt_button.setAccessibleName(self.tra("删除"))
        self.delete_prompt_button.clicked.connect(self.delete_current_prompt)
        toolbar.addWidget(self.delete_prompt_button)
        preview_layout.addWidget(self.preview_toolbar)
        preview_layout.addWidget(HorizontalSeparator(self.preview_panel))

        self.document_layout = QHBoxLayout()
        self.document_layout.setContentsMargins(28, 24, 24, 16)
        self.selected_prompt_content_text = TextEdit(self.preview_panel)
        self.selected_prompt_content_text.setObjectName("promptPreview")
        self.selected_prompt_content_text.setReadOnly(True)
        self.selected_prompt_content_text.setAcceptRichText(False)
        self.selected_prompt_content_text.setAccessibleName(self.tra("提示词内容"))
        self.selected_prompt_content_text.setMinimumHeight(100)
        self.selected_prompt_content_text.setMaximumWidth(960)
        self.selected_prompt_content_text.document().setDocumentMargin(0)
        self.preview_highlighter = PromptHighlighter(self.selected_prompt_content_text.document())
        self.document_layout.addWidget(self.selected_prompt_content_text, 1)
        preview_layout.addLayout(self.document_layout, 1)
        if guidance:
            guidance_label = secondary_label(guidance, self.preview_panel)
            guidance_label.setWordWrap(True)
            guidance_label.setContentsMargins(28, 0, 28, 12)
            preview_layout.addWidget(guidance_label)

        self.status_bar = QWidget(self.preview_panel)
        self.status_bar.setFixedHeight(42)
        footer = QHBoxLayout(self.status_bar)
        footer.setContentsMargins(28, 0, 24, 0)
        footer.setSpacing(7)
        self.status_dot = CaptionLabel("●", self.status_bar)
        self.status_dot.setFixedWidth(10)
        self.status_dot.setFont(getFont(9))
        footer.addWidget(self.status_dot)
        self.active_label = secondary_label(self.tra("使用中"), self.status_bar)
        footer.addWidget(self.active_label)
        footer.addSpacing(10)
        footer.addWidget(secondary_label(self.tra("只读预览"), self.status_bar))
        footer.addStretch(1)
        self.character_count_label = secondary_label("", self.status_bar)
        footer.addWidget(self.character_count_label)
        preview_layout.addWidget(self.status_bar)
        self.workspace_layout.addWidget(self.preview_panel, 1)
        self.update_layout()

    def update_theme(self):
        dark = isDarkTheme()
        self.status_dot.setTextColor(QColor("#60917c"), QColor("#86b9a0"))
        muted = "#a7aeba" if dark else "#828a98"
        self.selected_prompt_type_label.setStyleSheet(
            f"color: {muted}; background: {'#303238' if dark else '#f3f4f6'}; border-radius: 4px;")
        self.selected_prompt_content_text.setStyleSheet(
            "TextEdit#promptPreview { background: transparent; border: none; "
            f"border-radius: 0; padding: 0 8px 0 0; color: {'#d9dde5' if dark else '#424b5a'}; }}")
        self.search_edit.setStyleSheet(
            "SearchLineEdit#promptSearch { "
            f"background: {'#2b2d32' if dark else '#ffffff'}; "
            f"color: {'#e3e5e9' if dark else '#303642'}; "
            f"border: 1px solid {'#3a3d43' if dark else '#e5e8ed'}; border-radius: 6px; padding: 0 8px; }}")
        self.preview_highlighter.rehighlight()
        self.workspace.update()
        for card in self.cards:
            card.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "preview_panel"):
            self.update_layout()

    def update_layout(self):
        compact = self.width() < 800
        if compact == self._compact:
            return
        self._compact = compact
        self.workspace_layout.setDirection(QHBoxLayout.TopToBottom if compact else QHBoxLayout.LeftToRight)
        self.library_panel.setMinimumWidth(0 if compact else 256)
        self.library_panel.setMaximumWidth(16777215 if compact else 256)
        self.library_panel.setMinimumHeight(150 if compact else 0)
        self.library_panel.setMaximumHeight(200 if compact else 16777215)
        self.selection_hint.setVisible(not compact)
        if compact:
            self.library_layout.removeWidget(self.search_edit)
            self.library_header_layout.setStretch(0, 0)
            self.library_header_layout.insertWidget(1, self.search_edit, 1)
        else:
            self.library_header_layout.removeWidget(self.search_edit)
            self.library_header_layout.setStretch(0, 1)
            self.library_layout.insertWidget(1, self.search_edit)
        self.workspace.update()

    def update_prompt_cards(self, selected_id=None):
        if selected_id is None:
            selected_id = self.selected_prompt_id
        self.selected_prompt_card = None
        self.cards = []
        self.groups = []
        while self.card_list_layout.count():
            item = self.card_list_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.all_prompts = self.default_prompt + self.user_prompts
        self.library_count_label.setText(str(len(self.all_prompts)))

        for index, (title, prompts) in enumerate(((self.tra("系统预设"), self.default_prompt),
                                                  (self.tra("自定义"), self.user_prompts))):
            label = secondary_label(f"{title}  ·  {len(prompts)}", self.card_container_widget)
            label.setContentsMargins(12, 16 if index else 2, 0, 6)
            self.card_list_layout.addWidget(label)
            group_cards = []
            for prompt in prompts:
                card = PromptCard(prompt, self.card_container_widget)
                card.prompt_selected.connect(self.display_prompt_details)
                self.card_list_layout.addWidget(card)
                self.cards.append(card)
                group_cards.append(card)
            self.groups.append((label, group_cards, title))

        self.no_results_label = secondary_label(self.tra("没有匹配的提示词"), self.card_container_widget)
        self.no_results_label.setAlignment(Qt.AlignCenter)
        self.no_results_label.setContentsMargins(0, 24, 0, 24)
        self.card_list_layout.addWidget(self.no_results_label)
        self.card_list_layout.addStretch(1)
        self.filter_cards()
        selected = next((p for p in self.all_prompts if p["id"] == selected_id), self.default_prompt[0])
        self.display_prompt_details(selected)

    def filter_cards(self):
        query = self.search_edit.text().strip().casefold()
        visible_count = 0
        for label, cards, title in self.groups:
            matches = 0
            for card in cards:
                data = card.prompt_data
                visible = not query or query in (data["name"] + "\n" + data["content"]).casefold()
                card.setVisible(visible)
                matches += int(visible)
            label.setVisible(bool(matches) or not query)
            label.setText(f"{title}  ·  {matches}")
            visible_count += matches
        if hasattr(self, "no_results_label"):
            self.no_results_label.setVisible(visible_count == 0)

    def find_card_widget(self, prompt_id):
        return next((card for card in self.cards if card.prompt_data["id"] == prompt_id), None)

    def display_prompt_details(self, prompt_data):
        card = self.find_card_widget(prompt_data["id"])
        if card is None:
            return
        if self.selected_prompt_card is not None:
            self.selected_prompt_card.set_default_style()
        card.set_selected_style()
        self.selected_prompt_card = card
        self.selected_prompt_id = prompt_data["id"]
        self.selected_prompt_name_label.set_prompt_name(prompt_data["name"])
        self.selected_prompt_content_text.setPlainText(prompt_data["content"])
        format_prompt_text(self.selected_prompt_content_text)
        self.selected_prompt_content_text.verticalScrollBar().setValue(0)
        is_user = prompt_data.get("type") == "user"
        self.selected_prompt_type_label.setText(self.tra("自定义") if is_user else self.tra("系统预设"))
        self.edit_prompt_button.setVisible(is_user)
        self.delete_prompt_button.setVisible(is_user)
        self.character_count_label.setText(self.tra("{count} 字符").format(count=f"{len(prompt_data['content']):,}"))
        self.save_config({
            self.selection_key: {"last_selected_id": prompt_data["id"], "prompt_content": prompt_data["content"]},
            self.user_data_key: self.user_prompts,
        })

    def edit_current_prompt(self):
        if self.selected_prompt_card:
            self.open_add_prompt_dialog(self.selected_prompt_card.prompt_data)

    def delete_current_prompt(self):
        self.delete_user_prompt(self.selected_prompt_id)

    def open_add_prompt_dialog(self, prompt_to_edit=None):
        if isinstance(prompt_to_edit, bool):
            prompt_to_edit = None
        if prompt_to_edit is not None and prompt_to_edit.get("type") != "user":
            return
        dialog = AddEditPromptDialog(prompt_to_edit, self)
        accepted = dialog.exec_()
        data = dialog.get_data() if accepted else None
        dialog.deleteLater()
        if not data:
            return
        for index, prompt in enumerate(self.user_prompts):
            if prompt["id"] == data["id"]:
                self.user_prompts[index] = data
                break
        else:
            self.user_prompts.append(data)
        self.search_edit.clear()
        self.update_prompt_cards(data["id"])
        self.scroll_area.ensureWidgetVisible(self.selected_prompt_card)

    def delete_user_prompt(self, prompt_id):
        if not any(prompt["id"] == prompt_id for prompt in self.user_prompts):
            return
        self.user_prompts = [prompt for prompt in self.user_prompts if prompt["id"] != prompt_id]
        self.update_prompt_cards(self.selected_prompt_id)
