"""Translation guidance with compact section buttons and editor toolbars."""

import copy

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import (
    QAbstractItemDelegate, QAbstractItemView, QApplication, QFrame,
    QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    Action, CaptionLabel, DropDownToolButton, FluentIcon as FI, MessageBox,
    PillPushButton, PushButton, RoundMenu, SwitchButton, TitleLabel,
)

from Frontend.components.tables.table_helper import TableHelper
from Frontend.core.config import ConfigMixin
from Frontend.services.editor import CharacterHelper
from Frontend.pages.prompts.translation.characterization_prompt_page import CharacterizationPromptPage
from Frontend.pages.prompts.translation.translation_example_prompt_page import TranslationExamplePromptPage
from Frontend.pages.prompts.translation.world_building_prompt_page import WorldBuildingPromptPage
from Frontend.pages.prompts.translation.writing_style_prompt_page import WritingStylePromptPage


class GuidanceEditorMixin:
    """Save only this editor's fields, and never reload a draft on show."""

    ROW_ACTIONS_IN_TOOLBAR = True

    def __init__(self, text, parent):
        self._guidance_ready = False
        self._baseline = None
        super().__init__(text, parent)
        self.container.setContentsMargins(0, 0, 0, 0)
        self.container.setSpacing(14)
        if hasattr(self, "table"):
            self.container.setStretchFactor(self.table, 1)
            self.table.setAlternatingRowColors(False)
            self.table.verticalHeader().setDefaultSectionSize(46)
            self.table.itemChanged.connect(self._update_dirty_status)
            self.table.model().rowsInserted.connect(self._update_dirty_status)
            self.table.model().rowsRemoved.connect(self._update_dirty_status)
            if self.ROW_ACTIONS_IN_TOOLBAR:
                self.remove_action.setEnabled(False)
                self.table.selectionModel().selectionChanged.connect(
                    lambda: self.remove_action.setEnabled(bool(self.table.selectionModel().selectedRows()))
                )
        else:
            self.container.setStretchFactor(self.plain_text_edit, 1)
            self.plain_text_edit.textChanged.connect(self._update_dirty_status)
        self.enabled_switch.checkedChanged.connect(self._update_dirty_status)
        self._apply_guidance(self.load_config())
        self._guidance_ready = True
        self._update_dirty_status()

    def add_widget_head(self, parent, config):
        # The legacy pages call this before building the editor body. Keep the
        # independent switch, but place it in the toolbar instead of a card.
        self.enabled_switch = SwitchButton(self)
        self.enabled_switch.setOnText(self.tra("已启用"))
        self.enabled_switch.setOffText(self.tra("已停用"))
        self.enabled_switch.setToolTip(self.tra("启用此指导"))
        self.enabled_switch.setAccessibleName(self.tra(self.TITLE) + " · " + self.tra("启用此指导"))
        self.enabled_switch.setChecked(bool(config.get(self.SWITCH_KEY)))

    add_widget_header = add_widget_head

    def _create_action_toolbar(self):
        bar = QWidget(self)
        self.toolbar = bar
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.save_status = CaptionLabel(self.tra("返回或切换时保存"), bar)
        self.save_status.setTextColor("#68717d", "#a5abb4")
        layout.addWidget(self.save_status)
        layout.addStretch(1)
        layout.addWidget(self.enabled_switch)
        self.save_button = PushButton(FI.SAVE, self.tra("保存"), bar)
        self.save_button.clicked.connect(self.save_data)
        layout.addWidget(self.save_button)
        buttons = [self.save_button]
        if hasattr(self, "KEYS"):
            self.import_button = PushButton(FI.DOWNLOAD, self.tra("导入"), bar)
            self.import_button.clicked.connect(self.import_data)
            layout.addWidget(self.import_button)
            buttons.append(self.import_button)

        self.tools_button = DropDownToolButton(FI.SETTING, bar)
        title = self.tra("表设置") if hasattr(self, "KEYS") else self.tra("更多操作")
        self.tools_button.setToolTip(title)
        self.tools_button.setAccessibleName(title)
        self.tools_menu = RoundMenu(parent=self.tools_button)
        if hasattr(self, "KEYS"):
            if self.ROW_ACTIONS_IN_TOOLBAR:
                self.insert_action = Action(FI.ADD_TO, self.tra("插入行"), triggered=self._handle_insert_row)
                self.remove_action = Action(FI.REMOVE_FROM, self.tra("删除行"), triggered=self._handle_remove_selected_rows)
                self.tools_menu.addAction(self.insert_action)
                self.tools_menu.addAction(self.remove_action)
                self.tools_menu.addSeparator()
            self.export_action = Action(FI.SHARE, self.tra("导出"), triggered=self.export_data)
            self.tools_menu.addAction(self.export_action)
            self.tools_menu.addSeparator()
        self.reset_action = Action(FI.DELETE, self.tra("重置"), triggered=self.reset_data)
        self.tools_menu.addAction(self.reset_action)
        self.tools_button.setMenu(self.tools_menu)
        layout.addWidget(self.tools_button)
        buttons.append(self.tools_button)
        # Match the public table toolbar's button height and icon size.
        for button in buttons:
            button.setFixedHeight(32)
            button.setIconSize(QSize(16, 16))
        return bar

    def _commit_cell_editor(self):
        if not hasattr(self, "table") or self.table.state() != QAbstractItemView.EditingState:
            return
        editor = QApplication.focusWidget()
        if editor is not None and self.table.isAncestorOf(editor) and editor is not self.table.viewport():
            self.table.commitData(editor)
            self.table.closeEditor(editor, QAbstractItemDelegate.NoHint)

    def _snapshot(self):
        if hasattr(self, "table"):
            # Include incomplete rows in dirty detection, even when the source is blank.
            content = [tuple(self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount())) for r in range(self.table.rowCount())]
            content = [row for row in content if any(cell for cell in row)]
        else:
            content = self.plain_text_edit.toPlainText()
        return self.enabled_switch.isChecked(), content

    def _is_dirty(self):
        return self._baseline is not None and self._snapshot() != self._baseline

    def _update_dirty_status(self, *_):
        if not self._guidance_ready:
            return
        dirty = self._is_dirty()
        self.save_status.setText(self.tra("待保存") if dirty else self.tra("返回或切换时保存"))
        # Keep Save clickable while a cell editor still holds uncommitted text.
        # save_data() commits that editor before checking whether anything changed.

    def _apply_guidance(self, config):
        self.enabled_switch.setChecked(bool(config.get(self.SWITCH_KEY)))
        data = config.get(self.DATA_KEY, self.default.get(self.DATA_KEY, [] if hasattr(self, "table") else ""))
        if hasattr(self, "table"):
            if self.DATA_KEY == "characterization_data":
                self._update_table_rows(CharacterHelper.normalize_rows(data))
            else:
                TableHelper.update_to_table(self.table, data, self.KEYS)
                self.table.resizeRowsToContents()
            self._reset_sort_indicator()
        else:
            self.plain_text_edit.setPlainText(data)
        self._baseline = copy.deepcopy(self._snapshot())
        self._update_dirty_status()

    def showEvent(self, event):
        # The old table pages reloaded unconditionally; that would erase tab drafts.
        QFrame.showEvent(self, event)
        if self._guidance_ready and not self._is_dirty():
            try:
                self._apply_guidance(self.load_config())
            except Exception as error:
                self.error_toast(self.tra("读取失败"), str(error))

    def _payload(self):
        if hasattr(self, "table"):
            if any(not row[0].strip() and any(cell.strip() for cell in row[1:]) for row in self._snapshot()[1]):
                raise ValueError(self.tra("请补全每行的原名或原文，再保存。"))
            data = TableHelper.load_from_table(self.table, self.KEYS)
            if self.DATA_KEY == "characterization_data":
                data = CharacterHelper.normalize_rows(data)
        else:
            data = self.plain_text_edit.toPlainText()
        return {self.DATA_KEY: data, self.SWITCH_KEY: self.enabled_switch.isChecked()}

    def save_config(self, new, *, _table_update=False):
        # Legacy import tools pass a full config: restrict writes to these two fields.
        config = ConfigMixin.save_config(self, {
            self.DATA_KEY: new[self.DATA_KEY], self.SWITCH_KEY: self.enabled_switch.isChecked(),
        })
        self._baseline = copy.deepcopy(self._snapshot())
        self._update_dirty_status()
        return config

    def save_data(self):
        self._commit_cell_editor()
        if not self._is_dirty():
            return True
        try:
            payload = self._payload()
            self.save_config(payload)
            if hasattr(self, "_refresh_invalid_row_highlight"):
                self._refresh_invalid_row_highlight(payload[self.DATA_KEY])
            self.save_status.setText(self.tra("数据已保存"))
            return True
        except Exception as error:
            self.save_status.setText(self.tra("保存失败"))
            self.error_toast(self.tra("保存失败"), str(error))
            return False

    def prepare_to_leave(self):
        return self.save_data()

    def reset_data(self):
        dialog = MessageBox(self.tra("警告"), self.tra("是否确认重置为默认数据?"), self.window())
        dialog.yesButton.setText(self.tra("确认"))
        dialog.cancelButton.setText(self.tra("取消"))
        if not dialog.exec():
            return
        try:
            data = copy.deepcopy(self.default.get(self.DATA_KEY, [] if hasattr(self, "table") else ""))
            config = self.save_config({self.DATA_KEY: data})
            self._apply_guidance(config)
        except Exception as error:
            self.error_toast(self.tra("保存失败"), str(error))

    def import_data(self):
        self._commit_cell_editor()
        try:
            # Preserve file formats, duplicate handling, and character validation.
            self._payload()
            super().import_data()
        except Exception as error:
            self.error_toast(self.tra("导入失败"), str(error))
        self._update_dirty_status()

    def export_data(self):
        self._commit_cell_editor()
        try:
            super().export_data()
        except Exception as error:
            self.error_toast(self.tra("导出失败"), str(error))


class CharacterGuidanceEditor(GuidanceEditorMixin, CharacterizationPromptPage):
    ROW_ACTIONS_IN_TOOLBAR = False
    TITLE, ICON = "角色介绍", FI.PEOPLE
    DATA_KEY, SWITCH_KEY = "characterization_data", "characterization_switch"
    DESCRIPTION = "将角色信息补充到基础提示词中；可用 [Separator] 分隔姓和名。"


class ExampleGuidanceEditor(GuidanceEditorMixin, TranslationExamplePromptPage):
    TITLE, ICON = "翻译示例", FI.FIT_PAGE
    DATA_KEY, SWITCH_KEY = "translation_example_data", "translation_example_switch"
    DESCRIPTION = "用原文与译文对照示例指导模型的表达方式。"


class WorldGuidanceEditor(GuidanceEditorMixin, WorldBuildingPromptPage):
    TITLE, ICON = "背景设定", FI.QUICK_NOTE
    DATA_KEY, SWITCH_KEY = "world_building_content", "world_building_switch"
    DESCRIPTION = "补充故事背景、世界观和专有概念，帮助模型理解上下文。"


class StyleGuidanceEditor(GuidanceEditorMixin, WritingStylePromptPage):
    TITLE, ICON = "翻译风格", FI.PENCIL_INK
    DATA_KEY, SWITCH_KEY = "writing_style_content", "writing_style_switch"
    DESCRIPTION = "指定译文语气、措辞和表达习惯。"


class TranslationGuidancePage(QFrame, ConfigMixin):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("translation_guidance")
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(TitleLabel(self.tra("管理翻译指导"), self))
        self.description = CaptionLabel(self)
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(8)
        layout.addLayout(tab_layout)
        self.tab_buttons = {}
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)
        self.editors = {}
        for key, factory in (("characters", CharacterGuidanceEditor), ("background", WorldGuidanceEditor), ("style", StyleGuidanceEditor), ("examples", ExampleGuidanceEditor)):
            editor = factory(key, self)
            self.editors[key] = editor
            self.stack.addWidget(editor)
            button = PillPushButton(self.tra(factory.TITLE), self)
            button.setFixedHeight(30)
            button.clicked.connect(lambda _checked=False, k=key: self.switch_editor(k))
            tab_layout.addWidget(button)
            self.tab_buttons[key] = button
        tab_layout.addStretch(1)
        self._select_editor("characters")

    def switch_editor(self, key):
        current = self.stack.currentWidget()
        if current is not self.editors[key] and not current.prepare_to_leave():
            self._select_editor(current.objectName())
            return
        self._select_editor(key)

    def _select_editor(self, key):
        editor = self.editors[key]
        self.stack.setCurrentWidget(editor)
        self.description.setText(self.tra(editor.DESCRIPTION))
        for name, button in self.tab_buttons.items():
            button.setChecked(name == key)

    def prepare_to_leave(self):
        return all(editor.prepare_to_leave() for editor in self.editors.values())
