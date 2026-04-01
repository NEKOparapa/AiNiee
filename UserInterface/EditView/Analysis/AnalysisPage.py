import concurrent.futures
import re
import time
from datetime import datetime
from typing import Any, Callable
import rapidjson as json

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QSplitter,
    QStackedWidget,
    QTableWidgetItem,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    FluentIcon as FIF,
    MessageBox,
    PrimaryPushButton,
    StrongBodyLabel,
    TableWidget,
    TransparentPushButton,
    TransparentToolButton,
    TreeWidget,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.Toast import ToastMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Infrastructure.RequestLimiter.RequestLimiter import RequestLimiter


class AnalysisPage(QFrame, ConfigMixin, LogMixin, ToastMixin, Base):
    VIEW_CHARACTERS = "characters"
    VIEW_TERMS = "terms"
    VIEW_NON_TRANSLATE = "non_translate"

    CHARACTER_MALE = "男性"
    CHARACTER_FEMALE = "女性"
    CHARACTER_OTHER = "其他"
    CHARACTER_CATEGORIES = (
        CHARACTER_MALE,
        CHARACTER_FEMALE,
        CHARACTER_OTHER,
    )

    TERM_IDENTITY = "身份"
    TERM_ITEM = "物品"
    TERM_ORGANIZATION = "组织"
    TERM_LOCATION = "地名"
    TERM_OTHER = "其他"
    TERM_CATEGORIES = (
        TERM_IDENTITY,
        TERM_ITEM,
        TERM_ORGANIZATION,
        TERM_LOCATION,
        TERM_OTHER,
    )

    NON_TRANSLATE_PLACEHOLDER = "占位符"
    NON_TRANSLATE_MARKUP = "标记符"
    NON_TRANSLATE_CODE = "调用代码"
    NON_TRANSLATE_ESCAPE = "转义控制符"
    NON_TRANSLATE_VARIABLE = "变量键名"
    NON_TRANSLATE_RESOURCE = "资源标识"
    NON_TRANSLATE_NUMERIC = "数值公式"
    NON_TRANSLATE_OTHER = "其他"
    NON_TRANSLATE_CATEGORIES = (
        NON_TRANSLATE_PLACEHOLDER,
        NON_TRANSLATE_MARKUP,
        NON_TRANSLATE_CODE,
        NON_TRANSLATE_ESCAPE,
        NON_TRANSLATE_VARIABLE,
        NON_TRANSLATE_RESOURCE,
        NON_TRANSLATE_NUMERIC,
        NON_TRANSLATE_OTHER,
    )

    def __init__(self, cache_manager, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("AnalysisPage")

        self.cache_manager = cache_manager
        self.analysis_data = {}
        self.current_view = self.VIEW_CHARACTERS
        self.current_character_filter = None
        self.current_term_filter = None
        self.current_non_translate_filter = None
        self._updating_ui = False
        self._splitter_ratio_initialized = False

        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)
        self.container.setSpacing(12)

        self._build_body()
        self._build_action_bar()

        self.subscribe(Base.EVENT.ANALYSIS_TASK_UPDATE, self.on_analysis_task_update)
        self.subscribe(Base.EVENT.ANALYSIS_TASK_DONE, self.on_analysis_task_done)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_from_project()
        if not self._splitter_ratio_initialized:
            QTimer.singleShot(0, self._apply_initial_splitter_sizes)

    def refresh_from_project(self) -> None:
        self.analysis_data = self._clone_analysis_data(self.cache_manager.get_analysis_data())
        self._sync_stats()
        self._refresh_navigation()
        self._refresh_all_views()
        self._update_status_labels()
        self._update_action_buttons()

    def _build_action_bar(self) -> None:
        self.action_card = CardWidget(self)
        action_layout = QHBoxLayout(self.action_card)
        action_layout.setContentsMargins(18, 14, 18, 14)
        action_layout.setSpacing(10)

        self.start_button = PrimaryPushButton(FIF.PLAY, "开始分析", self.action_card)
        self.stop_button = TransparentPushButton(FIF.CANCEL_MEDIUM, "停止", self.action_card)

        self.start_button.clicked.connect(self.start_analysis)
        self.stop_button.clicked.connect(self.stop_analysis)

        self.status_label = BodyLabel("状态: 未分析", self.action_card)
        self.time_label = BodyLabel("最近分析: -", self.action_card)
        self.count_label = BodyLabel("命中数: 0", self.action_card)

        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.stop_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.status_label)
        action_layout.addWidget(self.time_label)
        action_layout.addWidget(self.count_label)

        self.container.addWidget(self.action_card)

    def _build_body(self) -> None:
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setHandleWidth(0)
        self.splitter.setStyleSheet("QSplitter::handle { width: 0px; }")
        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)

        self.nav_card = CardWidget(self)
        self.nav_card.setMinimumWidth(0)
        nav_layout = QVBoxLayout(self.nav_card)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(8)

        self.nav_toolbar = QWidget(self.nav_card)
        self.nav_toolbar_layout = QHBoxLayout(self.nav_toolbar)
        self.nav_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.nav_toolbar_layout.setSpacing(0)

        self.apply_button = TransparentPushButton(FIF.SAVE, "保存", self.nav_toolbar)

        self.apply_button.clicked.connect(self.apply_to_config)

        button_width = 75
        self.apply_button.setFixedWidth(button_width)

        self.nav_toolbar_layout.addWidget(self.apply_button)
        nav_layout.addWidget(self.nav_toolbar)

        self.nav_tree = TreeWidget(self.nav_card)
        self.nav_tree.setMinimumWidth(0)
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        nav_layout.addWidget(self.nav_tree)

        self.page_card = CardWidget(self)
        self.page_card.setMinimumWidth(0)
        page_layout = QVBoxLayout(self.page_card)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.content_stack = QStackedWidget(self.page_card)
        self.characters_page = self._build_characters_page()
        self.terms_page = self._build_terms_page()
        self.non_translate_page = self._build_non_translate_page()

        for widget in (
            self.characters_page,
            self.terms_page,
            self.non_translate_page,
        ):
            self.content_stack.addWidget(widget)

        page_layout.addWidget(self.content_stack)

        self.splitter.addWidget(self.nav_card)
        self.splitter.addWidget(self.page_card)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 9)
        self.container.addWidget(self.splitter, 1)

    def _apply_initial_splitter_sizes(self) -> None:
        if self._splitter_ratio_initialized:
            return

        total_width = self.splitter.width() or self.width()
        if total_width <= 0:
            return

        left_width = max(220, int(total_width * 0.15))
        right_width = max(total_width - left_width, 1)
        self.splitter.setSizes([left_width, right_width])
        self._splitter_ratio_initialized = True

    def _build_characters_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 4, 0, 6)
        self.characters_title_label = StrongBodyLabel("角色表", page)
        header_layout.addWidget(self.characters_title_label)
        header_layout.addStretch(1)
        self.characters_clear_button = TransparentPushButton(FIF.DELETE, "清空", page)
        self.characters_clear_button.clicked.connect(
            lambda: self._clear_current_table(self.VIEW_CHARACTERS)
        )
        header_layout.addWidget(self.characters_clear_button)
        layout.addLayout(header_layout)

        self.characters_table = self._create_table(
            [
                "原文名",
                "推荐译名",
                "性别",
                "备注",
                "操作",
            ]
        )
        self.characters_table.itemChanged.connect(
            lambda item: self._on_table_item_changed(self.VIEW_CHARACTERS, item)
        )
        layout.addWidget(self.characters_table, 1)
        return page

    def _build_terms_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 4, 0, 6)
        self.terms_title_label = StrongBodyLabel("术语表", page)
        header_layout.addWidget(self.terms_title_label)
        header_layout.addStretch(1)
        self.terms_clear_button = TransparentPushButton(FIF.DELETE, "清空", page)
        self.terms_clear_button.clicked.connect(
            lambda: self._clear_current_table(self.VIEW_TERMS)
        )
        header_layout.addWidget(self.terms_clear_button)
        layout.addLayout(header_layout)

        self.terms_table = self._create_table(
            [
                "原文",
                "推荐译名",
                "分类属性",
                "备注",
                "操作",
            ]
        )
        self.terms_table.itemChanged.connect(
            lambda item: self._on_table_item_changed(self.VIEW_TERMS, item)
        )
        layout.addWidget(self.terms_table, 1)
        return page

    def _build_non_translate_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 4, 0, 6)
        self.non_translate_title_label = StrongBodyLabel("禁翻表", page)
        header_layout.addWidget(self.non_translate_title_label)
        header_layout.addStretch(1)
        self.non_translate_clear_button = TransparentPushButton(FIF.DELETE, "清空", page)
        self.non_translate_clear_button.clicked.connect(
            lambda: self._clear_current_table(self.VIEW_NON_TRANSLATE)
        )
        header_layout.addWidget(self.non_translate_clear_button)
        layout.addLayout(header_layout)

        self.non_translate_table = self._create_table(
            ["原文", "分类", "备注", "操作"]
        )
        self.non_translate_table.itemChanged.connect(
            lambda item: self._on_table_item_changed(self.VIEW_NON_TRANSLATE, item)
        )
        layout.addWidget(self.non_translate_table, 1)
        return page

    def _create_table(self, headers: list[str]) -> TableWidget:
        table = TableWidget(self)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.setWordWrap(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setBorderRadius(8)
        table.setBorderVisible(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeToContents)
        return table

    def _refresh_navigation(self) -> None:
        expanded_views = set()
        root = self.nav_tree.invisibleRootItem()
        for index in range(root.childCount()):
            item = root.child(index)
            data = item.data(0, Qt.UserRole)
            if item.isExpanded() and data:
                expanded_views.add(data[0])

        self.nav_tree.clear()
        counts = self._get_counts()

        characters_item = QTreeWidgetItem([f"角色表 ({counts['characters']})"])
        characters_item.setData(0, Qt.UserRole, (self.VIEW_CHARACTERS, None))
        for category in self.CHARACTER_CATEGORIES:
            child = QTreeWidgetItem([f"{category} ({counts['character_categories'].get(category, 0)})"])
            child.setData(0, Qt.UserRole, (self.VIEW_CHARACTERS, category))
            characters_item.addChild(child)

        terms_item = QTreeWidgetItem([f"术语表 ({counts['terms']})"])
        terms_item.setData(0, Qt.UserRole, (self.VIEW_TERMS, None))
        for category in self.TERM_CATEGORIES:
            child = QTreeWidgetItem([f"{category} ({counts['term_categories'].get(category, 0)})"])
            child.setData(0, Qt.UserRole, (self.VIEW_TERMS, category))
            terms_item.addChild(child)

        non_translate_item = QTreeWidgetItem([f"禁翻表 ({counts['non_translate']})"])
        non_translate_item.setData(0, Qt.UserRole, (self.VIEW_NON_TRANSLATE, None))
        for category in self.NON_TRANSLATE_CATEGORIES:
            child = QTreeWidgetItem([f"{category} ({counts['non_translate_categories'].get(category, 0)})"])
            child.setData(0, Qt.UserRole, (self.VIEW_NON_TRANSLATE, category))
            non_translate_item.addChild(child)

        for item in (characters_item, terms_item, non_translate_item):
            self.nav_tree.addTopLevelItem(item)
            data = item.data(0, Qt.UserRole)
            if data and data[0] in expanded_views:
                self.nav_tree.expandItem(item)

        self._select_current_nav_item()

    def _refresh_all_views(self) -> None:
        self._updating_ui = True
        try:
            self._populate_characters_table()
            self._populate_terms_table()
            self._populate_non_translate_table()
        finally:
            self._updating_ui = False

    def _populate_characters_table(self) -> None:
        rows = self._get_visible_rows(self.VIEW_CHARACTERS)
        self.characters_title_label.setText(self._get_current_view_title(self.VIEW_CHARACTERS))
        self.characters_clear_button.setEnabled(bool(rows) and not self._is_analysis_running())

        self._fill_table(
            self.characters_table,
            rows,
            [("source", True), ("recommended_translation", True), ("gender", True), ("note", True)],
            self.VIEW_CHARACTERS,
        )

    def _populate_terms_table(self) -> None:
        rows = self._get_visible_rows(self.VIEW_TERMS)
        self.terms_title_label.setText(self._get_current_view_title(self.VIEW_TERMS))
        self.terms_clear_button.setEnabled(bool(rows) and not self._is_analysis_running())

        self._fill_table(
            self.terms_table,
            rows,
            [("source", True), ("recommended_translation", True), ("category_path", True), ("note", True)],
            self.VIEW_TERMS,
        )

    def _populate_non_translate_table(self) -> None:
        rows = self._get_visible_rows(self.VIEW_NON_TRANSLATE)
        self.non_translate_title_label.setText(self._get_current_view_title(self.VIEW_NON_TRANSLATE))
        self.non_translate_clear_button.setEnabled(bool(rows) and not self._is_analysis_running())

        self._fill_table(
            self.non_translate_table,
            rows,
            [("marker", True), ("category", True), ("note", True)],
            self.VIEW_NON_TRANSLATE,
        )

    def _fill_table(
        self,
        table: TableWidget,
        rows: list[dict],
        field_specs: list[tuple[str, bool]],
        view_name: str,
    ) -> None:
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            row_key = self._get_row_key(view_name, row)
            for col_index, (field_name, editable) in enumerate(field_specs):
                value = row.get(field_name, "")
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(Qt.UserRole, row_key)
                if not editable:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row_index, col_index, item)
            table.setCellWidget(row_index, len(field_specs), self._build_delete_button(view_name, row_key))
        table.resizeRowsToContents()
        table.blockSignals(False)

    def _build_delete_button(self, view_name: str, row_key: str) -> QWidget:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        button = TransparentToolButton(FIF.DELETE, container)
        button.clicked.connect(lambda: self._delete_row(view_name, row_key))
        layout.addWidget(button)
        return container

    def on_nav_item_clicked(self, item, column) -> None:
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        view_name, filter_value = data
        self.current_view = view_name
        if view_name == self.VIEW_CHARACTERS:
            self.current_character_filter = filter_value
            self._populate_characters_table()
        elif view_name == self.VIEW_TERMS:
            self.current_term_filter = filter_value
            self._populate_terms_table()
        else:
            self.current_non_translate_filter = filter_value
            self._populate_non_translate_table()

        self._switch_content_view(view_name)

    def _switch_content_view(self, view_name: str) -> None:
        mapping = {
            self.VIEW_CHARACTERS: self.characters_page,
            self.VIEW_TERMS: self.terms_page,
            self.VIEW_NON_TRANSLATE: self.non_translate_page,
        }
        self.content_stack.setCurrentWidget(mapping.get(view_name, self.characters_page))

    def _select_current_nav_item(self) -> None:
        target = (self.current_view, self._get_filter_for_view(self.current_view))
        root = self.nav_tree.invisibleRootItem()
        fallback_item = None
        for row in range(root.childCount()):
            item = root.child(row)
            data = item.data(0, Qt.UserRole)
            if data == (self.current_view, None):
                fallback_item = item
            if data == target:
                self.nav_tree.setCurrentItem(item)
                self._switch_content_view(self.current_view)
                return
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                if child.data(0, Qt.UserRole) == target:
                    self.nav_tree.setCurrentItem(child)
                    self._switch_content_view(self.current_view)
                    return

        if fallback_item is not None:
            self.nav_tree.setCurrentItem(fallback_item)
        self._switch_content_view(self.current_view)

    def _get_filter_for_view(self, view_name: str):
        if view_name == self.VIEW_CHARACTERS:
            return self.current_character_filter
        if view_name == self.VIEW_TERMS:
            return self.current_term_filter
        if view_name == self.VIEW_NON_TRANSLATE:
            return self.current_non_translate_filter
        return None

    def start_analysis(self) -> None:
        if Base.work_status != Base.STATUS.IDLE:
            self.warning_toast("提示", "当前有其他任务正在执行，请稍后再试。")
            return
        if not self.cache_manager or not self.cache_manager.project:
            self.warning_toast("提示", "当前没有已加载的项目。")
            return

        if self.analysis_data:
            message_box = MessageBox(
                "确认",
                "重新开始分析会覆盖当前项目中的分析结果，是否继续？",
                self.window(),
            )
            message_box.yesButton.setText("确认")
            message_box.cancelButton.setText("取消")
            if not message_box.exec():
                return

        self._update_status_labels("分析中")
        self._update_action_buttons(running=True)
        self.emit(Base.EVENT.ANALYSIS_TASK_START, {})

    def stop_analysis(self) -> None:
        if not self._is_analysis_running():
            return

        message_box = MessageBox(
            "确认",
            "是否确定停止当前分析任务？",
            self.window(),
        )
        message_box.yesButton.setText("确认")
        message_box.cancelButton.setText("取消")
        if not message_box.exec():
            return

        self._update_status_labels("正在停止")
        self._update_action_buttons(running=True)
        self.stop_button.setEnabled(False)
        self.emit(Base.EVENT.TASK_STOP, {})

    def clear_analysis_result(self) -> None:
        if self._is_analysis_running():
            self.warning_toast("提示", "分析任务执行中，暂时不能清空结果。")
            return
        if not self.analysis_data:
            self.info_toast("提示", "当前项目没有可清空的分析结果。")
            return

        message_box = MessageBox(
            "确认",
            "确定要清空当前项目的分析结果吗？",
            self.window(),
        )
        message_box.yesButton.setText("确认")
        message_box.cancelButton.setText("取消")
        if not message_box.exec():
            return

        self.analysis_data = {}
        self.cache_manager.clear_analysis_data()
        self._request_cache_save()
        self._refresh_navigation()
        self._refresh_all_views()
        self._update_status_labels()
        self._update_action_buttons()
        self.success_toast("完成", "已清空当前项目的分析结果。")

    def apply_to_config(self) -> None:
        if not self.analysis_data:
            self.warning_toast("提示", "当前没有可应用的分析结果。")
            return

        config = self.load_config()

        char_data = list(config.get("characterization_data", []) or [])
        existing_characters = {str(item.get("original_name", "")).strip() for item in char_data}
        char_added = 0
        char_skipped = 0
        for row in self.analysis_data.get("characters", []):
            source = str(row.get("source", "")).strip()
            if not source or source in existing_characters:
                char_skipped += 1
                continue
            char_data.append(
                {
                    "original_name": source,
                    "translated_name": str(row.get("recommended_translation", "")),
                    "gender": str(row.get("gender", "")),
                    "age": "",
                    "personality": "",
                    "speech_style": "",
                    "additional_info": str(row.get("note", "")),
                }
            )
            existing_characters.add(source)
            char_added += 1
        config["characterization_data"] = char_data

        term_data = list(config.get("prompt_dictionary_data", []) or [])
        existing_terms = {str(item.get("src", "")).strip() for item in term_data}
        term_added = 0
        term_skipped = 0
        for row in self.analysis_data.get("terms", []):
            source = str(row.get("source", "")).strip()
            if not source or source in existing_terms:
                term_skipped += 1
                continue
            term_data.append(
                {
                    "src": source,
                    "dst": str(row.get("recommended_translation", "")),
                    "info": self._join_non_empty(
                        str(row.get("category_path", "")),
                        str(row.get("note", "")),
                        " | ",
                    ),
                }
            )
            existing_terms.add(source)
            term_added += 1
        config["prompt_dictionary_data"] = term_data

        non_translate_data = list(config.get("exclusion_list_data", []) or [])
        existing_markers = {str(item.get("markers", "")).strip() for item in non_translate_data}
        non_translate_added = 0
        non_translate_skipped = 0
        for row in self.analysis_data.get("non_translate", []):
            marker = str(row.get("marker", "")).strip()
            if not marker or marker in existing_markers:
                non_translate_skipped += 1
                continue
            non_translate_data.append(
                {
                    "markers": marker,
                    "info": self._join_non_empty(
                        str(row.get("category", "")),
                        str(row.get("note", "")),
                        " | ",
                    ),
                    "regex": "",
                }
            )
            existing_markers.add(marker)
            non_translate_added += 1
        config["exclusion_list_data"] = non_translate_data

        self.save_config(config)
        self.success_toast(
            "完成",
            (
                f"已应用到配置。"
                f"角色 +{char_added} / 跳过 {char_skipped}，"
                f"术语 +{term_added} / 跳过 {term_skipped}，"
                f"禁翻 +{non_translate_added} / 跳过 {non_translate_skipped}。"
            ),
        )

    def on_analysis_task_update(self, event: int, data: dict) -> None:
        message = str(data.get("message", "")).strip() or "分析中"
        self._update_status_labels(message)

    def on_analysis_task_done(self, event: int, data: dict) -> None:
        status = str(data.get("status", "error"))
        analysis_data = data.get("analysis_data")
        message = str(data.get("message", "")).strip()

        if analysis_data:
            self.analysis_data = self._clone_analysis_data(analysis_data)
            self._sync_stats()
            self._refresh_navigation()
            self._refresh_all_views()
            self._request_cache_save()

        self._update_action_buttons()
        if status == "success":
            self._update_status_labels("分析完成")
            self.success_toast("完成", message or "全文分析完成。")
        elif status == "partial":
            self._update_status_labels("部分完成")
            self.warning_toast("完成", message or "分析已完成，但存在失败的分块。")
        elif status == "stopped":
            self._update_status_labels("已停止")
            self.info_toast("已停止", message or "分析任务已停止。")
        else:
            self._update_status_labels("分析失败")
            self.error_toast("失败", message or "全文分析失败。")

    def _on_table_item_changed(self, view_name: str, item: QTableWidgetItem) -> None:
        if self._updating_ui:
            return

        row_key = self._normalize_row_key(item.data(Qt.UserRole))
        if not row_key:
            return

        if view_name == self.VIEW_CHARACTERS:
            field_map = {0: "source", 1: "recommended_translation", 2: "gender", 3: "note"}
        elif view_name == self.VIEW_TERMS:
            field_map = {0: "source", 1: "recommended_translation", 2: "category_path", 3: "note"}
        else:
            field_map = {0: "marker", 1: "category", 2: "note"}

        target_row = self._find_row_by_key(view_name, row_key)
        if not target_row:
            return

        field_name = field_map.get(item.column())
        if not field_name:
            return

        new_value = item.text().strip()
        refresh_navigation = False
        refresh_view = False
        if view_name == self.VIEW_CHARACTERS and field_name == "gender":
            new_value = self._normalize_character_category(new_value)
            refresh_navigation = True
            refresh_view = True
        elif view_name == self.VIEW_TERMS and field_name == "category_path":
            new_value = self._normalize_term_category(new_value)
            refresh_navigation = True
            refresh_view = True
        elif view_name == self.VIEW_NON_TRANSLATE and field_name == "category":
            new_value = self._normalize_non_translate_category(
                new_value,
                marker=target_row.get("marker", ""),
                note=target_row.get("note", ""),
            )
            refresh_navigation = True
            refresh_view = True

        key_field = self._get_row_identity_field(view_name)
        if field_name == key_field:
            current_key = self._get_row_key(view_name, target_row)
            if not new_value:
                new_value = current_key
            else:
                next_key = self._normalize_row_key(new_value)
                existing_row = self._find_row_by_key(view_name, next_key)
                if next_key != current_key and existing_row and existing_row is not target_row:
                    self.warning_toast("提示", "原文键已存在，不能重复。")
                    new_value = current_key
                refresh_view = True

        if item.text() != new_value:
            self._updating_ui = True
            item.setText(new_value)
            self._updating_ui = False

        target_row[field_name] = new_value
        self._persist_analysis_state(refresh_navigation=refresh_navigation)
        if refresh_view:
            if view_name == self.VIEW_CHARACTERS:
                self._populate_characters_table()
            elif view_name == self.VIEW_TERMS:
                self._populate_terms_table()
            else:
                self._populate_non_translate_table()

    def _delete_row(self, view_name: str, row_key: str) -> None:
        if not row_key:
            return

        key = self._get_analysis_key(view_name)
        if not key:
            return

        rows = self.analysis_data.get(key, []) or []
        self.analysis_data[key] = [
            row for row in rows if self._get_row_key(view_name, row) != self._normalize_row_key(row_key)
        ]
        self._persist_analysis_state(refresh_navigation=True)
        self._refresh_all_views()

    def _clear_current_table(self, view_name: str) -> None:
        if self._is_analysis_running():
            self.warning_toast("提示", "分析任务执行中，暂时不能删除当前表内容。")
            return
        if not self.analysis_data:
            self.info_toast("提示", "当前项目没有可删除的分析结果。")
            return

        visible_rows = self._get_visible_rows(view_name)
        if not visible_rows:
            self.info_toast("提示", "当前表格没有可删除的内容。")
            return

        message_box = MessageBox(
            "确认",
            f"确定要删除当前表格中的 {len(visible_rows)} 条内容吗？",
            self.window(),
        )
        message_box.yesButton.setText("确认")
        message_box.cancelButton.setText("取消")
        if not message_box.exec():
            return

        key = self._get_analysis_key(view_name)
        if not key:
            return

        visible_row_keys = {
            self._get_row_key(view_name, row)
            for row in visible_rows
        }
        self.analysis_data[key] = [
            row
            for row in self.analysis_data.get(key, []) or []
            if self._get_row_key(view_name, row) not in visible_row_keys
        ]
        self._persist_analysis_state(refresh_navigation=True)
        self._refresh_all_views()
        self.success_toast("完成", f"已删除当前表格中的 {len(visible_rows)} 条内容。")

    def _persist_analysis_state(self, refresh_navigation: bool = False) -> None:
        if not self.cache_manager or not self.cache_manager.project:
            return

        self._flush_pending_stats_only()
        self.cache_manager.set_analysis_data(self._clone_analysis_data(self.analysis_data))
        self._request_cache_save()
        if refresh_navigation:
            self._refresh_navigation()
        self._update_status_labels("已修改")
        self._update_action_buttons()

    def _request_cache_save(self) -> None:
        config = self.load_config()
        output_path = config.get("label_output_path", "")
        if output_path:
            self.emit(Base.EVENT.TASK_MANUAL_SAVE_CACHE, {"output_path": output_path})

    def _sync_stats(self) -> None:
        if not self.analysis_data:
            return
        stats = dict(self.analysis_data.get("stats", {}) or {})
        stats["character_count"] = len(self.analysis_data.get("characters", []) or [])
        stats["term_count"] = len(self.analysis_data.get("terms", []) or [])
        stats["non_translate_count"] = len(self.analysis_data.get("non_translate", []) or [])
        self.analysis_data["stats"] = stats

    def _flush_pending_stats_only(self) -> None:
        self._sync_stats()

    def _update_status_labels(self, override_text: str | None = None) -> None:
        if self._is_analysis_running():
            rendered_status = override_text or "分析中"
        elif override_text:
            rendered_status = override_text
        else:
            status_key = str(self.analysis_data.get("status", "")).strip()
            status_map = {
                "success": "已完成",
                "partial": "部分完成",
                "stopped": "已停止",
                "error": "失败",
            }
            rendered_status = status_map.get(
                status_key,
                "未分析" if not self.analysis_data else "就绪",
            )

        last_run_at = self.analysis_data.get("last_run_at", "-") if self.analysis_data else "-"
        counts = self._get_counts()
        total_hits = counts["characters"] + counts["terms"] + counts["non_translate"]

        self.status_label.setText(f"状态: {rendered_status}")
        self.time_label.setText(f"最近分析: {last_run_at}")
        self.count_label.setText(f"命中数: {total_hits}")

    def _update_action_buttons(self, running: bool | None = None) -> None:
        has_project = bool(self.cache_manager and self.cache_manager.project)
        has_analysis = bool(self.analysis_data)
        if running is None:
            running = self._is_analysis_running()

        self.start_button.setEnabled(has_project and not running)
        self.stop_button.setEnabled(running)
        self.apply_button.setEnabled(has_analysis and not running)
        self.characters_clear_button.setEnabled(
            bool(self._get_visible_rows(self.VIEW_CHARACTERS)) and not running
        )
        self.terms_clear_button.setEnabled(
            bool(self._get_visible_rows(self.VIEW_TERMS)) and not running
        )
        self.non_translate_clear_button.setEnabled(
            bool(self._get_visible_rows(self.VIEW_NON_TRANSLATE)) and not running
        )

    def _get_counts(self) -> dict:
        characters = self.analysis_data.get("characters", []) or []
        character_categories = {category: 0 for category in self.CHARACTER_CATEGORIES}
        for row in characters:
            category = self._normalize_character_category(row.get("gender", self.CHARACTER_OTHER))
            character_categories[category] += 1

        terms = self.analysis_data.get("terms", []) or []
        term_categories = {category: 0 for category in self.TERM_CATEGORIES}
        for row in terms:
            category = self._normalize_term_category(row.get("category_path", self.TERM_OTHER))
            term_categories[category] += 1

        non_translates = self.analysis_data.get("non_translate", []) or []
        non_translate_categories = {category: 0 for category in self.NON_TRANSLATE_CATEGORIES}
        for row in non_translates:
            category = self._normalize_non_translate_category(row.get("category", self.NON_TRANSLATE_OTHER))
            non_translate_categories[category] += 1

        return {
            "characters": len(characters),
            "terms": len(terms),
            "non_translate": len(non_translates),
            "character_categories": character_categories,
            "term_categories": term_categories,
            "non_translate_categories": non_translate_categories,
        }

    def _get_current_view_title(self, view_name: str) -> str:
        filter_value = self._get_filter_for_view(view_name)
        base_title = {
            self.VIEW_CHARACTERS: "角色表",
            self.VIEW_TERMS: "术语表",
            self.VIEW_NON_TRANSLATE: "禁翻表",
        }.get(view_name, "")
        if filter_value:
            return f"{base_title} / {filter_value}"
        return base_title

    def _get_visible_rows(self, view_name: str) -> list[dict]:
        key = self._get_analysis_key(view_name)
        if not key:
            return []

        rows = list(self.analysis_data.get(key, []) or [])
        current_filter = self._get_filter_for_view(view_name)
        if not current_filter:
            return rows

        if view_name == self.VIEW_CHARACTERS:
            return [
                row
                for row in rows
                if self._normalize_character_category(row.get("gender", "")) == current_filter
            ]
        if view_name == self.VIEW_TERMS:
            return [
                row
                for row in rows
                if self._normalize_term_category(row.get("category_path", self.TERM_OTHER))
                == current_filter
            ]
        if view_name == self.VIEW_NON_TRANSLATE:
            return [
                row
                for row in rows
                if self._normalize_non_translate_category(
                    row.get("category", ""),
                    marker=row.get("marker", ""),
                    note=row.get("note", ""),
                )
                == current_filter
            ]
        return rows

    def _join_non_empty(self, left: str, right: str, separator: str) -> str:
        parts = [part.strip() for part in (str(left), str(right)) if str(part).strip()]
        return separator.join(parts)

    def _get_analysis_key(self, view_name: str) -> str | None:
        return {
            self.VIEW_CHARACTERS: "characters",
            self.VIEW_TERMS: "terms",
            self.VIEW_NON_TRANSLATE: "non_translate",
        }.get(view_name)

    def _get_row_identity_field(self, view_name: str) -> str:
        if view_name == self.VIEW_NON_TRANSLATE:
            return "marker"
        return "source"

    def _normalize_row_key(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _get_row_key(self, view_name: str, row: dict) -> str:
        return self._normalize_row_key(row.get(self._get_row_identity_field(view_name), ""))

    def _find_row_by_key(self, view_name: str, row_key: str) -> dict | None:
        key = self._get_analysis_key(view_name)
        if not key:
            return None

        normalized_row_key = self._normalize_row_key(row_key)
        if not normalized_row_key:
            return None

        rows = self.analysis_data.get(key, []) or []
        return next(
            (row for row in rows if self._get_row_key(view_name, row) == normalized_row_key),
            None,
        )

    def _clone_analysis_data(self, data: dict) -> dict:
        if not data:
            return {}
        return {
            "version": data.get("version", 1),
            "status": data.get("status", ""),
            "last_run_at": data.get("last_run_at", ""),
            "characters": [
                {k: v for k, v in dict(row).items() if k not in {"id", "_type_"}}
                for row in data.get("characters", []) or []
            ],
            "terms": [
                {k: v for k, v in dict(row).items() if k not in {"id", "_type_"}}
                for row in data.get("terms", []) or []
            ],
            "non_translate": [
                {k: v for k, v in dict(row).items() if k not in {"id", "_type_"}}
                for row in data.get("non_translate", []) or []
            ],
            "stats": dict(data.get("stats", {}) or {}),
        }

    def _normalize_character_category(self, value) -> str:
        text = str(value or "").strip().lower()
        if any(token in text for token in ["男", "male", "m", "boy", "man"]):
            return self.CHARACTER_MALE
        if any(token in text for token in ["女", "female", "f", "girl", "woman"]):
            return self.CHARACTER_FEMALE
        return self.CHARACTER_OTHER

    def _normalize_term_category(self, value) -> str:
        text = str(value or "").strip().lower()
        if any(token in text for token in ["身份", "人物身份", "称谓", "头衔", "职业", "角色", "identity", "role", "title", "class"]):
            return self.TERM_IDENTITY
        if any(token in text for token in ["物品", "道具", "装备", "item", "artifact", "product", "weapon"]):
            return self.TERM_ITEM
        if any(token in text for token in ["组织", "势力", "阵营", "团体", "organization", "org", "faction"]):
            return self.TERM_ORGANIZATION
        if any(token in text for token in ["地名", "地点", "城市", "国家", "location", "place", "loc", "gpe"]):
            return self.TERM_LOCATION
        return self.TERM_OTHER

    def _normalize_non_translate_category(self, value, marker="", note="") -> str:
        text = str(value or "").strip().lower()
        combined_hint = f"{text} {marker} {note}".lower()
        
        if any(token in combined_hint for token in ["占位", "placeholder", "%s", "{0}", "%d", "{x}"]):
            return self.NON_TRANSLATE_PLACEHOLDER
        if any(token in combined_hint for token in ["标记", "markup", "标签", "<", ">", "color=", "size=", "<b>", "<i>"]):
            return self.NON_TRANSLATE_MARKUP
        if any(token in combined_hint for token in ["调用", "代码", "函数", "code", "func", "call", "()"]):
            return self.NON_TRANSLATE_CODE
        if any(token in combined_hint for token in ["转义", "换行", "escape", "\\n", "\\t", "\\r"]):
            return self.NON_TRANSLATE_ESCAPE
        if any(token in combined_hint for token in ["变量", "键名", "variable", "var", "key", "$", "@"]):
            return self.NON_TRANSLATE_VARIABLE
        if any(token in combined_hint for token in ["资源", "路径", "标识", "resource", "asset", "path", ".png", ".wav", ".mp3", "assets/"]):
            return self.NON_TRANSLATE_RESOURCE
        if any(token in combined_hint for token in ["数值", "公式", "计算", "numeric", "math", "+", "-", "*", "/", "="]):
            return self.NON_TRANSLATE_NUMERIC
            
        return self.NON_TRANSLATE_OTHER

    def _is_analysis_running(self) -> bool:
        return Base.work_status in (Base.STATUS.ANALYSIS_TASK, Base.STATUS.STOPING)
