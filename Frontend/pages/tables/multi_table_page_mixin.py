import copy
import re
from pathlib import Path

import pandas
import rapidjson as json
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QAbstractItemDelegate, QAbstractItemView, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action, BodyLabel, CaptionLabel, ComboBox, DropDownPushButton, DropDownToolButton, FluentIcon, LineEdit,
    MessageBox, MessageBoxBase, PushButton, RoundMenu, StrongBodyLabel, SwitchButton, TabBar,
    SubtitleLabel, TabCloseButtonDisplayMode, TransparentToolButton,
)

from Frontend.services.editor import TableConfigHelper
from Frontend.platform.file_dialogs import get_open_file_name, get_save_file_name
from Frontend.components.tables.table_helper import TableHelper
from Frontend.services.public_tables import PublicTableFileHelper
from Frontend.components.dialogs.public_table_check_dialog import PublicTableCheckDialog


class TableNameDialog(MessageBoxBase):
    def __init__(self, title, value, translate, parent):
        super().__init__(parent)
        self.viewLayout.addWidget(StrongBodyLabel(title, self))
        self.name_edit = LineEdit(self)
        self.name_edit.setText(value)
        self.name_edit.selectAll()
        self.viewLayout.addWidget(self.name_edit)
        self.widget.setMinimumWidth(360)
        self.yesButton.setText(translate("确认"))
        self.cancelButton.setText(translate("取消"))
        self.name_edit.textChanged.connect(lambda text: self.yesButton.setEnabled(bool(text.strip())))
        self.yesButton.setEnabled(bool(value.strip()))


class TableTransferDialog(MessageBoxBase):
    def __init__(self, tables, row_count, translate, parent):
        super().__init__(parent)
        self._table_ids = [table["id"] for table in tables]
        self.viewLayout.addWidget(StrongBodyLabel(translate("转移表格"), self))
        self.viewLayout.addWidget(BodyLabel(translate("将选中的 {0} 条数据转移到：").format(row_count), self))
        self.table_combo = ComboBox(self)
        self.table_combo.setMinimumWidth(360)
        for table in tables:
            suffix = "" if table["enabled"] else f" ({translate('已停用')})"
            self.table_combo.addItem(table["name"] + suffix)
        self.viewLayout.addWidget(self.table_combo)
        note = CaptionLabel(translate("目标表中已存在相同原文的条目将保留在当前表。"), self)
        note.setWordWrap(True)
        self.viewLayout.addWidget(note)
        self.yesButton.setText(translate("确认"))
        self.cancelButton.setText(translate("取消"))
        self.yesButton.setEnabled(bool(tables))

    @property
    def table_id(self):
        index = self.table_combo.currentIndex()
        return self._table_ids[index] if 0 <= index < len(self._table_ids) else None

    def validate(self):
        return self.table_id is not None


class MultiTablePageMixin:
    """One editor per page, with atomic table-ID based persistence."""

    def _init_multi_table_state(self, config):
        self._table_key = f"{self.TABLE_KIND}_tables"
        self._active_key = f"{self.TABLE_KIND}_active_table_id"
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        ids = {table["id"] for table in self._tables}
        selected = config.get(self._active_key)
        self._active_table_id = selected if selected in ids else (self._tables[0]["id"] if self._tables else None)
        self._loaded_rows = None
        self._multi_table_ready = False
        self._pending_glossary_requests = {}

    def add_widget_head(self, parent, config, window):
        heading = QWidget(self)
        heading_layout = QHBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, 4)
        heading_layout.setSpacing(12)
        heading_layout.addWidget(SubtitleLabel(self.tra(self.TABLE_TITLE), heading))
        self.table_count_label = CaptionLabel(heading)
        self.table_count_label.setTextColor(QColor("#68717d"), QColor("#a5abb4"))
        heading_layout.addWidget(self.table_count_label)
        heading_layout.addStretch(1)
        note = CaptionLabel(self.tra("切换时自动保存"), heading)
        note.setTextColor(QColor("#68717d"), QColor("#a5abb4"))
        note.setToolTip(self.tra("各表独立启用；拖动标签调整顺序，切换表时自动保存。"))
        heading_layout.addWidget(note)
        parent.addWidget(heading)

        self.table_tabs = TabBar(self)
        self.table_tabs.setScrollable(True)
        self.table_tabs.setMovable(True)
        self.table_tabs.setTabMaximumWidth(176)
        self.table_tabs.setTabShadowEnabled(False)
        self.table_tabs.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.ON_HOVER)
        self.table_tabs.setTabSelectedBackgroundColor(QColor("#ffffff"), QColor("#383838"))
        self.table_tabs.setAddButtonVisible(False)
        self.table_tabs.setFixedHeight(40)
        self.table_tabs.itemLayout.setContentsMargins(0, 2, 0, 2)
        self.table_tabs.currentChanged.connect(self._on_table_tab_changed)
        self.table_tabs.tabAddRequested.connect(self._prompt_new_table)
        self.table_tabs.tabBarDoubleClicked.connect(self._prompt_rename_table)
        self.table_tabs.tabCloseRequested.connect(self._confirm_delete_table)
        self.table_tabs.tabMoved.connect(self._on_table_moved)
        self._tab_scroll_timer = QTimer(self)
        self._tab_scroll_timer.setSingleShot(True)
        self._tab_scroll_timer.timeout.connect(self._ensure_active_tab_visible)
        tab_row = QWidget(self)
        tab_row.setFixedHeight(40)
        tab_layout = QHBoxLayout(tab_row)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(6)
        tab_layout.addWidget(self.table_tabs, 1)
        self.new_table_button = TransparentToolButton(FluentIcon.ADD, self)
        self.new_table_button.setFixedSize(32, 32)
        self.new_table_button.setIconSize(QSize(14, 14))
        self.new_table_button.setToolTip(self.tra("新建表"))
        self.new_table_button.setAccessibleName(self.tra("新建表"))
        self.new_table_button.clicked.connect(self._prompt_new_table)
        tab_layout.addWidget(self.new_table_button)
        tab_layout.addStretch()
        parent.addWidget(tab_row)
        self.empty_table_label = BodyLabel(self.tra("暂无表格，请新建或导入一张表。"), self)

    def _create_search_toolbar(self):
        toolbar = QWidget(self)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.search_input = LineEdit(toolbar)
        self.search_input.setPlaceholderText(self.tra("搜索表格内容..."))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_input, 1)

        self.search_field_button = DropDownPushButton(self.tra("全部"), toolbar)
        self.search_field_menu = RoundMenu(parent=self.search_field_button)
        all_action = Action(self.tra("全部"))
        all_action.triggered.connect(lambda: self._set_search_field(-1, self.tra("全部")))
        self.search_field_menu.addAction(all_action)
        self.search_field_menu.addSeparator()
        for index, key in enumerate(self.KEYS):
            if key in self.SWITCH_KEYS:
                continue
            name = self._get_translated_column_name(index)
            action = Action(name)
            action.triggered.connect(lambda checked=False, i=index, text=name: self._set_search_field(i, text))
            self.search_field_menu.addAction(action)
        self.search_field_button.setMenu(self.search_field_menu)
        layout.addWidget(self.search_field_button)

        self.search_results_label = BodyLabel("", toolbar)
        layout.addWidget(self.search_results_label)
        self.search_prev_button = TransparentToolButton(FluentIcon.UP, toolbar)
        self.search_prev_button.setToolTip(self.tra("上一个结果"))
        self.search_prev_button.clicked.connect(self._navigate_previous)
        self.search_prev_button.setEnabled(False)
        layout.addWidget(self.search_prev_button)
        self.search_next_button = TransparentToolButton(FluentIcon.DOWN, toolbar)
        self.search_next_button.setToolTip(self.tra("下一个结果"))
        self.search_next_button.clicked.connect(self._navigate_next)
        self.search_next_button.setEnabled(False)
        layout.addWidget(self.search_next_button)
        layout.addStretch(1)

        self.table_enabled_switch = SwitchButton(self)
        self.table_enabled_switch.setOnText(self.tra("已启用"))
        self.table_enabled_switch.setOffText(self.tra("已停用"))
        self.table_enabled_switch.setToolTip(self.tra("启用此表"))
        self.table_enabled_switch.checkedChanged.connect(self._set_current_table_enabled)
        layout.addWidget(self.table_enabled_switch)

        self.save_button = PushButton(FluentIcon.SAVE, self.tra("保存"), toolbar)
        self.save_button.clicked.connect(self.save_data)
        layout.addWidget(self.save_button)
        self.import_button = self._create_import_button()
        layout.addWidget(self.import_button)

        self.table_tools_button = DropDownToolButton(FluentIcon.SETTING, toolbar)
        self.table_tools_button.setToolTip(self.tra("表设置"))
        self.table_tools_button.setAccessibleName(self.tra("表设置"))
        self.table_tools_menu = RoundMenu(parent=self.table_tools_button)
        self._current_table_actions = []

        def add_action(icon, text, callback):
            action = Action(icon, self.tra(text), triggered=callback)
            self.table_tools_menu.addAction(action)
            self._current_table_actions.append(action)
            return action

        self.rename_table_action = add_action(FluentIcon.EDIT, "重命名表", lambda: self._prompt_rename_table())
        if self.TABLE_KIND == "prompt_dictionary":
            self.match_settings_action = add_action(FluentIcon.SETTING, "匹配设置", self._open_match_settings_dialog)
        self.table_tools_menu.addSeparator()
        self.export_action = add_action(FluentIcon.SHARE, "导出当前子表", self.export_data)
        self.export_selected_action = add_action(FluentIcon.SHARE, "选择子表导出…", self.export_selected_tables)
        if self.TABLE_KIND == "prompt_dictionary":
            self.name_extractor_action = add_action(FluentIcon.PEOPLE, "角色提取", self.name_extractor)
            self.glossary_translation_action = add_action(FluentIcon.SEND_FILL, "简单翻译", self.glossary_translation)
        self.table_tools_menu.addSeparator()
        self.reset_action = add_action(FluentIcon.DELETE, "清空当前表", self.reset_data)
        self.table_tools_button.setMenu(self.table_tools_menu)
        layout.addWidget(self.table_tools_button)

        TableHelper.style_public_table_toolbar(self)
        return toolbar

    @staticmethod
    def _table_status_icon(enabled):
        pixmap = QPixmap(32, 32)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("#28a36a") if enabled else QColor("#909090")
        painter.setPen(color)
        painter.setBrush(color if enabled else Qt.NoBrush)
        painter.drawEllipse(5, 5, 6, 6)
        painter.end()
        return QIcon(pixmap)

    def _finish_multi_table_setup(self):
        self._empty_table_space = QWidget(self)
        empty_layout = QVBoxLayout(self._empty_table_space)
        empty_layout.addStretch(1)
        empty_layout.addWidget(self.empty_table_label, 0, Qt.AlignHCenter)
        empty_layout.addStretch(2)
        self.container.addWidget(self._empty_table_space, 1)
        self.container.setStretchFactor(self.table, 1)
        self._multi_table_ready = True
        self._refresh_tabs()
        self._display_current_table(force=True)
        self._remember_active_table()

    def _current_table(self):
        return next((table for table in self._tables if table["id"] == self._active_table_id), None)

    def _canonical_rows(self, rows):
        values = TableConfigHelper.normalize_rows(self.TABLE_KIND, rows)
        key = self.KEYS[0]
        return list({row[key]: row for row in values if row.get(key)}.values())

    def _commit_cell_editor(self):
        if self.table.state() != QAbstractItemView.EditingState:
            return
        editor = QApplication.focusWidget()
        if editor is not None and editor is not self.table and self.table.isAncestorOf(editor):
            if editor is not self.table.viewport():
                self.table.commitData(editor)
                self.table.closeEditor(editor, QAbstractItemDelegate.NoHint)

    def _save_current_table(self, silent=True):
        if not self._multi_table_ready or not self._active_table_id:
            return True
        self._commit_cell_editor()
        rows = self._canonical_rows(self._load_table_rows())
        if rows == self._loaded_rows:
            return True
        table_id = self._active_table_id
        try:
            def update(config):
                target = next((table for table in config[self._table_key] if table["id"] == table_id), None)
                if target is None:
                    raise ValueError(self.tra("目标表已被删除，无法保存。"))
                target["rows"] = TableConfigHelper.merge_edited_rows(
                    self.TABLE_KIND, self._loaded_rows or [], rows, target["rows"],
                )
            config = self.update_config(update)
        except Exception as error:
            self.error_toast(self.tra("保存失败"), str(error))
            return False
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        rows = self._current_table()["rows"]
        if rows != self._load_table_rows():
            self._update_table_rows(rows)
            self._reset_search()
        self._loaded_rows = copy.deepcopy(rows)
        if not silent:
            self.success_toast("", self.tra("数据已保存") + " ... ")
        return True

    def save_data(self):
        if self._save_current_table():
            self.success_toast("", self.tra("数据已保存") + " ... ")

    def prepare_to_leave(self):
        return self._save_current_table()

    def _handle_transfer_selected_rows(self):
        selected_indices = {index.row() for index in self.table.selectionModel().selectedRows()}
        source_id = self._active_table_id
        if not selected_indices or source_id is None:
            return
        self._commit_cell_editor()
        try:
            tables = TableConfigHelper.get_tables(self.load_config(), self.TABLE_KIND)
        except Exception as error:
            self.error_toast(self.tra("转移失败"), str(error))
            return
        destinations = [table for table in tables if table["id"] != source_id]
        if not destinations:
            self.warning_toast(self.tra("无法转移"), self.tra("当前分类下没有其他表格，无法转移。"))
            return

        # The loader omits blank source cells. Keep their actual UI indices so
        # a selection spanning empty rows still moves exactly the selected rows.
        row_indices = [
            index for index in range(self.table.rowCount())
            if self.table.item(index, 0) is not None and self.table.item(index, 0).text().strip()
        ]
        editor_rows = list(zip(row_indices, TableHelper.load_from_table(
            self.table, self.KEYS, self.SWITCH_KEYS, row_indices=row_indices,
        )))
        incoming = self._canonical_rows([row for index, row in editor_rows if index in selected_indices])
        if not incoming:
            self.warning_toast(self.tra("无法转移"), self.tra("所选行没有可转移的数据。"))
            return
        dialog = TableTransferDialog(destinations, len(incoming), self.tra, self.window())
        if not dialog.exec():
            return
        target_id = dialog.table_id
        if target_id is None or target_id == source_id:
            return
        # A glossary translation can complete while the modal dialog is open.
        # Do not replace its fresh results with the selection's older snapshot.
        if self._active_table_id != source_id or self._load_table_rows() != [row for _, row in editor_rows]:
            self.warning_toast(self.tra("无法转移"), self.tra("当前表格内容已更新，请重新选择要转移的行。"))
            return

        key = self.KEYS[0]
        moved = []
        try:
            def update(config):
                tables = config[self._table_key]
                source = next((table for table in tables if table["id"] == source_id), None)
                target = next((table for table in tables if table["id"] == target_id), None)
                if source is None or target is None:
                    raise ValueError(self.tra("源表或目标表已被删除，无法转移。"))
                existing = {row[key] for row in target["rows"] if row.get(key)}
                moved.extend(row for row in incoming if row[key] not in existing)
                if not moved:
                    return
                moved_keys = {row[key] for row in moved}
                stored_rows = {row[key]: row for row in source["rows"] if row.get(key)}

                def with_metadata(row):
                    return {**copy.deepcopy(stored_rows.get(row[key], {})), **row}

                target["rows"].extend(with_metadata(row) for row in moved)
                source["rows"] = self._canonical_rows([
                    with_metadata(row) for index, row in editor_rows
                    if index not in selected_indices or row[key] not in moved_keys
                ])

            # Both tables are persisted together. Leave the editor untouched if
            # the destination disappears or the atomic config write fails.
            config = self.update_config(update)
        except Exception as error:
            self.error_toast(self.tra("转移失败"), str(error))
            return
        if not moved:
            self.info_toast(self.tra("无法转移"), self.tra("目标表已存在所选条目的原文，未转移任何数据。"))
            return
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        self._refresh_tabs()
        self._display_current_table(force=True)
        target = next(table for table in self._tables if table["id"] == target_id)
        skipped = len(incoming) - len(moved)
        if skipped:
            self.info_toast("", self.tra("已转移 {0} 条数据到“{1}”，{2} 条同原文数据保留在当前表。").format(
                len(moved), target["name"], skipped,
            ))
        else:
            self.success_toast("", self.tra("已转移 {0} 条数据到“{1}”。").format(len(moved), target["name"]))

    def showEvent(self, event):
        super().showEvent(event)
        if self._multi_table_ready:
            self.update_table()

    def hideEvent(self, event):
        if self._multi_table_ready:
            self._save_current_table()
        super().hideEvent(event)

    def update_table(self):
        config = self.load_config()
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        ids = {table["id"] for table in self._tables}
        selected = config.get(self._active_key)
        if selected not in ids:
            selected = self._active_table_id if self._active_table_id in ids else (
                self._tables[0]["id"] if self._tables else None
            )
        has_draft = self._loaded_rows is not None and (
            self._canonical_rows(self._load_table_rows()) != self._loaded_rows
        )
        # Project exports select their destination. Follow it on return, unless
        # the current editor still contains a draft that belongs to another table.
        if self._current_table() is None or (selected != self._active_table_id and not has_draft):
            self._active_table_id = selected
            self._loaded_rows = None
        self._refresh_tabs()
        self._display_current_table()

    def _refresh_tabs(self):
        tabs = self.table_tabs
        previous = tabs.blockSignals(True)
        ids = [table["id"] for table in self._tables]
        old_ids = [tabs.tabData(index) for index in range(tabs.count())]
        if ids != old_ids:
            # TabBar removes items with deleteLater; detach them immediately so
            # repeated refreshes do not leave old tabs in the layout's size hint.
            for index in reversed(range(tabs.count())):
                item = tabs.tabItem(index)
                tabs.itemLayout.removeWidget(item)
                item.hide()
                tabs.removeTab(index)
            for table in self._tables:
                tabs.addTab(table["id"], table["name"])
                tabs.setTabData(tabs.count() - 1, table["id"])
        for index, table in enumerate(self._tables):
            status = self.tra("已启用") if table["enabled"] else self.tra("已停用")
            tabs.setTabText(index, table["name"])
            tabs.setTabIcon(index, self._table_status_icon(table["enabled"]))
            tabs.setTabToolTip(index, f"{table['name']} · {status}")
            item = tabs.tabItem(index)
            item.setFixedWidth(min(176, max(104, item.fontMetrics().horizontalAdvance(table["name"]) + 70)))
        tabs.setMaximumWidth(max(1, sum(tabs.tabItem(index).width() for index in range(tabs.count())) + 3))
        tabs.setVisible(bool(self._tables))
        self.table_count_label.setText(self.tra("{0} 张表 · {1} 张启用").format(
            len(self._tables), sum(table["enabled"] for table in self._tables),
        ))
        if self._active_table_id in ids:
            tabs.setCurrentIndex(ids.index(self._active_table_id))
            self._tab_scroll_timer.start(0)
        tabs.blockSignals(previous)
        current = self._current_table()
        blocked = self.table_enabled_switch.blockSignals(True)
        self.table_enabled_switch.setChecked(bool(current and current["enabled"]))
        self.table_enabled_switch.blockSignals(blocked)
        for widget in (self.table_enabled_switch, self.save_button, self.table_tools_button, *self._current_table_actions):
            widget.setEnabled(current is not None)
        self.empty_table_label.setVisible(current is None)
        self._empty_table_space.setVisible(current is None)
        if hasattr(self, "table"):
            self.table.setVisible(current is not None)

    def _ensure_active_tab_visible(self):
        if self.table_tabs.currentIndex() >= 0:
            self.table_tabs.view.adjustSize()
            self.table_tabs.ensureWidgetVisible(self.table_tabs.currentTab())

    def _display_current_table(self, force=False):
        current = self._current_table()
        rows = self._canonical_rows(current["rows"]) if current else []
        # Compare only editable fields; imported metadata is kept in storage and
        # must not make an unchanged editor look like an unsaved draft.
        rows = [{key: row[key] for key in self.KEYS} for row in rows]
        # Re-showing a page must not replace an unsaved draft with an old snapshot.
        if not force and self._loaded_rows is not None:
            if self._canonical_rows(self._load_table_rows()) != self._loaded_rows:
                return
            if rows == self._loaded_rows:
                return
        self._update_table_rows(rows)
        self._loaded_rows = copy.deepcopy(rows)
        self._reset_search()
        self._reset_sort_indicator()

    def _remember_active_table(self):
        table_id = self._active_table_id
        return self.update_config(lambda config: config.update({self._active_key: table_id}))

    def _on_table_tab_changed(self, index):
        if 0 <= index < self.table_tabs.count():
            self._select_table(self.table_tabs.tabData(index))

    def _select_table(self, table_id):
        if table_id == self._active_table_id:
            return True
        if not self._save_current_table():
            self._refresh_tabs()
            return False
        old_id = self._active_table_id
        self._active_table_id = table_id
        try:
            config = self._remember_active_table()
        except Exception as error:
            self._active_table_id = old_id
            self._refresh_tabs()
            self.error_toast(self.tra("保存失败"), str(error))
            return False
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        self._refresh_tabs()
        self._display_current_table(force=True)
        return True

    def _unique_table_name(self, name, tables, exclude_id=None):
        names = {table["name"] for table in tables if table["id"] != exclude_id}
        candidate, suffix = name.strip() or self.tra("新建表"), 2
        original = candidate
        while candidate in names:
            candidate = f"{original} ({suffix})"
            suffix += 1
        return candidate

    def _prompt_new_table(self):
        dialog = TableNameDialog(self.tra("新建表"), self.tra("新建表"), self.tra, self.window())
        if dialog.exec():
            self._create_table(dialog.name_edit.text())

    def _create_table(self, name, rows=None):
        if not self._save_current_table():
            return None
        new_table = TableConfigHelper.new_table(self.TABLE_KIND, name, self._canonical_rows(rows or []))
        try:
            def update(config):
                tables = config[self._table_key]
                new_table["name"] = self._unique_table_name(name, tables)
                tables.append(copy.deepcopy(new_table))
                config[self._active_key] = new_table["id"]
            config = self.update_config(update)
        except Exception as error:
            self.error_toast(self.tra("保存失败"), str(error))
            return None
        self._active_table_id = new_table["id"]
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        self._refresh_tabs()
        self._display_current_table(force=True)
        return new_table["id"]

    def _prompt_rename_table(self, index=None):
        table_id = self.table_tabs.tabData(index) if isinstance(index, int) and 0 <= index < self.table_tabs.count() else self._active_table_id
        current = next((table for table in self._tables if table["id"] == table_id), None)
        if current is None:
            return
        dialog = TableNameDialog(self.tra("重命名表"), current["name"], self.tra, self.window())
        if dialog.exec():
            self._rename_table(table_id, dialog.name_edit.text())

    def _rename_table(self, table_id, name):
        return self._update_table_metadata(table_id, name=name.strip()) if name.strip() else False

    def _set_current_table_enabled(self, enabled):
        if self._active_table_id:
            self._update_table_metadata(self._active_table_id, enabled=bool(enabled))

    def _update_table_metadata(self, table_id, **changes):
        try:
            def update(config):
                target = next((table for table in config[self._table_key] if table["id"] == table_id), None)
                if target is None:
                    raise ValueError(self.tra("目标表已被删除，无法保存。"))
                if "name" in changes:
                    changes["name"] = self._unique_table_name(changes["name"], config[self._table_key], table_id)
                target.update(copy.deepcopy(changes))
            config = self.update_config(update)
            self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
            self._refresh_tabs()
            return True
        except Exception as error:
            self._refresh_tabs()
            self.error_toast(self.tra("保存失败"), str(error))
            return False

    def _confirm_delete_table(self, index):
        if not 0 <= index < self.table_tabs.count():
            return
        table_id = self.table_tabs.tabData(index)
        table = next(table for table in self._tables if table["id"] == table_id)
        dialog = MessageBox(self.tra("删除表"), self.tra("确认删除表“{}”及其内容？").format(table["name"]), self.window())
        dialog.yesButton.setText(self.tra("删除"))
        dialog.cancelButton.setText(self.tra("取消"))
        if dialog.exec():
            self._delete_table(table_id)

    def _delete_table(self, table_id):
        if not self._save_current_table():
            return False
        try:
            def update(config):
                tables = config[self._table_key]
                tables[:] = [table for table in tables if table["id"] != table_id]
                if config.get(self._active_key) == table_id:
                    config[self._active_key] = tables[0]["id"] if tables else None
            config = self.update_config(update)
        except Exception as error:
            self.error_toast(self.tra("保存失败"), str(error))
            return False
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        self._active_table_id = config.get(self._active_key)
        self._refresh_tabs()
        self._display_current_table(force=True)
        return True

    def _on_table_moved(self, _from, _to):
        ids = [self.table_tabs.tabData(index) for index in range(self.table_tabs.count())]
        self._reorder_tables(ids)

    def _reorder_tables(self, ordered_ids):
        if not self._save_current_table():
            self._refresh_tabs()
            return False
        try:
            def update(config):
                tables = config[self._table_key]
                by_id = {table["id"]: table for table in tables}
                ordered = [by_id[table_id] for table_id in ordered_ids if table_id in by_id]
                ordered.extend(table for table in tables if table["id"] not in ordered_ids)
                config[self._table_key] = ordered
            config = self.update_config(update)
            self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
            self._refresh_tabs()
            return True
        except Exception as error:
            self._refresh_tabs()
            self.error_toast(self.tra("保存失败"), str(error))
            return False

    def reset_data(self):
        if self._current_table() is None:
            return
        dialog = MessageBox(self.tra("清空当前表"), self.tra("确认清空当前表的内容？表名和设置会保留。"), self.window())
        dialog.yesButton.setText(self.tra("确认"))
        dialog.cancelButton.setText(self.tra("取消"))
        if dialog.exec() and self._update_table_metadata(self._active_table_id, rows=[]):
            self._display_current_table(force=True)

    def _create_import_button(self):
        button = DropDownPushButton(FluentIcon.DOWNLOAD, self.tra("导入"), self)
        button.setToolTip(self.tra("导入"))
        menu = RoundMenu(parent=button)
        menu.addAction(Action(self.tra("导入为新表"), triggered=self.import_data))
        menu.addAction(Action(self.tra("导入到当前表"), triggered=self.import_into_current_table))
        button.setMenu(menu)
        return button

    def import_data(self):
        self._import_table_file(as_new=True)

    def import_into_current_table(self):
        self._import_table_file(as_new=False)

    def _import_table_file(self, as_new):
        if not as_new and self._current_table() is None:
            self.warning_toast(self.tra("提示"), self.tra("请先新建或选择一张表。"))
            return
        path, _ = get_open_file_name(self, self.tra("选择文件"), "", "JSON 文件 (*.json);;XLSX 文件 (*.xlsx)")
        if not path:
            return
        try:
            tables = PublicTableFileHelper.load_bundle(path, self.TABLE_KIND, self.KEYS)
            if tables is not None:
                candidates = [dict(table, id=f"import-{index}") for index, table in enumerate(tables)]
                note = (
                    "每张选中的子表将分别导入为新表，保留表名和设置；同名表会自动重命名。" if as_new else
                    "所选子表的数据将合并到当前表，已存在的原文不会覆盖。"
                )
                dialog = PublicTableCheckDialog(
                    candidates, self.tra("选择要导入的子表"), self.tra(note), self.tra, self.window(),
                )
                if not dialog.exec():
                    return
                selected = set(dialog.selected_ids)
                tables = [table for table in candidates if table["id"] in selected]
                if not tables:
                    return
                if as_new:
                    if self._create_imported_tables(tables):
                        self.success_toast("", self.tra("已导入 {0} 张子表。").format(len(tables)))
                else:
                    rows = [row for table in tables for row in table["rows"]]
                    if not self._canonical_rows(rows):
                        self.warning_toast(self.tra("提示"), self.tra("未从文件中加载到有效数据"))
                    elif self._merge_current_rows(rows):
                        self.success_toast("", self.tra("数据已导入并更新"))
                return
            rows = self._canonical_rows(TableHelper.load_from_file(path, self.KEYS, self.SWITCH_KEYS))
            if not rows:
                self.warning_toast(self.tra("提示"), self.tra("未从文件中加载到有效数据"))
                return
            if as_new:
                saved = self._create_table(Path(path).stem, rows) is not None
            else:
                saved = self._merge_current_rows(rows)
            if saved:
                self.success_toast("", self.tra("数据已导入并更新"))
        except Exception as error:
            self.error_toast(self.tra("导入失败"), self.tra(str(error)))

    def _rows_with_metadata(self, rows, stored_rows):
        key = self.KEYS[0]
        by_source = {row[key]: row for row in stored_rows if row.get(key)}
        return [{**copy.deepcopy(by_source.get(row[key], {})), **row} for row in rows]

    def _create_imported_tables(self, tables):
        """Save all imported subtables and the current draft in one transaction."""
        self._commit_cell_editor()
        source_id = self._active_table_id
        draft = self._canonical_rows(self._load_table_rows())
        has_draft = source_id is not None and draft != self._loaded_rows
        created = [TableConfigHelper.new_table(
            self.TABLE_KIND, table["name"], self._canonical_rows(table["rows"]),
            enabled=table["enabled"], match_options=table.get("match_options"),
        ) for table in tables]
        if not created:
            return False
        try:
            def update(config):
                existing = config[self._table_key]
                if has_draft:
                    source = next((table for table in existing if table["id"] == source_id), None)
                    if source is None:
                        raise ValueError(self.tra("目标表已被删除，无法保存。"))
                    source["rows"] = self._rows_with_metadata(draft, source["rows"])
                for table in created:
                    table["name"] = self._unique_table_name(table["name"], existing)
                    existing.append(copy.deepcopy(table))
                config[self._active_key] = created[0]["id"]
            config = self.update_config(update)
        except Exception as error:
            self.error_toast(self.tra("导入失败"), self.tra(str(error)))
            return False
        self._active_table_id = created[0]["id"]
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        self._refresh_tabs()
        self._display_current_table(force=True)
        return True

    def _merge_current_rows(self, rows):
        if not self._save_current_table():
            return False
        current = self._current_table()
        if current is None:
            return False
        key = self.KEYS[0]
        incoming = self._canonical_rows(rows)
        added = []
        try:
            def update(config):
                target = next((table for table in config[self._table_key] if table["id"] == current["id"]), None)
                if target is None:
                    raise ValueError(self.tra("目标表已被删除，无法保存。"))
                existing = {row[key] for row in target["rows"] if row.get(key)}
                added.extend(row for row in incoming if row[key] not in existing)
                target["rows"].extend(copy.deepcopy(added))
            config = self.update_config(update)
        except Exception as error:
            self.error_toast(self.tra("保存失败"), str(error))
            return False
        if not added:
            self.info_toast(self.tra("信息"), self.tra("导入的数据项均已存在于当前表格中"))
            return False
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        self._display_current_table(force=True)
        return True

    def export_data(self):
        current = self._current_table()
        if current is None:
            return
        self._export_table_file([current["id"]], bundle=False)

    def export_selected_tables(self):
        try:
            tables = self._export_tables_snapshot()
            if not tables:
                self.warning_toast(self.tra("提示"), self.tra("请先新建或选择一张表。"))
                return
            dialog = PublicTableCheckDialog(
                tables, self.tra("选择要导出的子表"),
                self.tra("各子表将分别保存，保留表名、启用状态和匹配设置。"),
                self.tra, self.window(), selected_ids=[self._active_table_id],
            )
            if dialog.exec() and dialog.selected_ids:
                self._export_table_file(dialog.selected_ids, bundle=True)
        except Exception as error:
            self.error_toast(self.tra("导出失败"), self.tra(str(error)))

    def _export_tables_snapshot(self):
        self._commit_cell_editor()
        tables = TableConfigHelper.get_tables(self.load_config(), self.TABLE_KIND)
        rows = self._canonical_rows(self._load_table_rows())
        if rows != self._loaded_rows:
            current = next((table for table in tables if table["id"] == self._active_table_id), None)
            if current is not None:
                current["rows"] = self._rows_with_metadata(rows, current["rows"])
        return tables

    def _export_table_file(self, table_ids, bundle):
        try:
            selected = set(table_ids)

            def snapshot():
                tables = [table for table in self._export_tables_snapshot() if table["id"] in selected]
                if len(tables) != len(selected):
                    raise ValueError(self.tra("部分子表已被删除，请重新选择后导出。"))
                return tables

            tables = snapshot()
            if not tables:
                return
            if not bundle and not self._canonical_rows(tables[0]["rows"]):
                self.warning_toast("", self.tra("表格中没有数据可导出"))
                return
            name = self.tra(self.TABLE_TITLE) if bundle else tables[0]["name"]
            safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or self.tra("当前表")
            path, selected_filter = get_save_file_name(
                self, self.tra("导出文件"), f"{self.tra('导出')}_{safe_name}",
                "JSON 文件 (*.json);;XLSX 文件 (*.xlsx)",
            )
            if not path:
                return
            if Path(path).suffix.lower() not in (".json", ".xlsx"):
                path += ".xlsx" if "(*.xlsx)" in selected_filter else ".json"
            # Read again after both dialogs, so completed background translations
            # and unsaved edits are included without saving or switching tabs.
            tables = snapshot()
            headers = [self._get_translated_column_name(index) for index in range(len(self.KEYS))]
            rows = self._canonical_rows(tables[0]["rows"])
            if bundle:
                PublicTableFileHelper.save_bundle(path, self.TABLE_KIND, tables, self.KEYS, headers)
            elif path.lower().endswith(".json"):
                with open(path, "w", encoding="utf-8") as writer:
                    writer.write(json.dumps(rows, indent=4, ensure_ascii=False))
            elif path.lower().endswith(".xlsx"):
                frame = pandas.DataFrame(rows).reindex(columns=list(self.KEYS), fill_value="")
                frame.columns = headers
                frame.to_excel(path, index=False)
            else:
                raise ValueError(self.tra("不支持的文件类型。请选择 .json 或 .xlsx"))
            self.success_toast("", self.tra("数据已导出到") + f": {path}")
        except Exception as error:
            self.error_toast(self.tra("导出失败"), self.tra(str(error)))
