from typing import Any
import rapidjson as json

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QColor
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
    Action,
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon as FIF,
    MessageBox,
    PrimaryPushButton,
    ProgressBar,
    RoundMenu,
    StrongBodyLabel,
    SubtitleLabel,
    TableWidget,
    TransparentPushButton,
    TreeWidget,
    setFont,
    themeColor,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.Toast import ToastMixin


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
    TERM_SKILL = "技能"
    TERM_RACE = "种族"
    TERM_OTHER = "其他"
    TERM_CATEGORIES = (
        TERM_IDENTITY,
        TERM_ITEM,
        TERM_ORGANIZATION,
        TERM_LOCATION,
        TERM_SKILL,
        TERM_RACE,
        TERM_OTHER,
    )

    # ==========================
    # 更新：8 大不翻译项分类常量
    # ==========================
    NON_TRANSLATE_TAG = "标签"
    NON_TRANSLATE_VARIABLE = "变量"
    NON_TRANSLATE_PLACEHOLDER = "占位符"
    NON_TRANSLATE_MACRO = "特殊宏"
    NON_TRANSLATE_ESCAPE = "转义符"
    NON_TRANSLATE_RESOURCE = "资源标识"
    NON_TRANSLATE_NUMERIC = "数值公式"
    NON_TRANSLATE_OTHER = "其他"
    
    NON_TRANSLATE_CATEGORIES = (
        NON_TRANSLATE_TAG,
        NON_TRANSLATE_VARIABLE,
        NON_TRANSLATE_PLACEHOLDER,
        NON_TRANSLATE_MACRO,
        NON_TRANSLATE_ESCAPE,
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
        self._table_width_ratio_initialized = set()
        self._temp_row_counter = 0
        self.analysis_runtime_state = self._create_default_runtime_state()

        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 12, 0, 0)
        self.container.setSpacing(12)

        self._build_action_bar()
        self._build_body()

        self.subscribe(Base.EVENT.ANALYSIS_TASK_UPDATE, self.on_analysis_task_update)
        self.subscribe(Base.EVENT.ANALYSIS_TASK_DONE, self.on_analysis_task_done)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_from_project()
        if not self._splitter_ratio_initialized:
            QTimer.singleShot(0, self._apply_initial_splitter_sizes)
        QTimer.singleShot(0, lambda: self._apply_initial_table_widths(self.current_view))

    def refresh_from_project(self) -> None:
        self.analysis_data = self._clone_analysis_data(self.cache_manager.get_analysis_data())
        self._sync_stats()
        self._sync_runtime_state_from_context()
        self._refresh_navigation()
        self._refresh_all_views()
        self._render_header()
        self._update_action_buttons()

    def _normalize_category_text(self, value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _compact_category_value(self, value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _matches_category_alias(self, value: Any, canonical: str, *aliases: str) -> bool:
        normalized_value = self._normalize_category_text(value)
        if not normalized_value:
            return False

        candidates = {
            self._normalize_category_text(canonical),
            self._normalize_category_text(self.tra(canonical)),
        }
        candidates.update(self._normalize_category_text(alias) for alias in aliases if alias)
        return normalized_value in candidates

    def _contains_category_hint(self, value: Any, canonical: str, *aliases: str) -> bool:
        normalized_value = self._normalize_category_text(value)
        if not normalized_value:
            return False

        candidates = {
            self._normalize_category_text(canonical),
            self._normalize_category_text(self.tra(canonical)),
        }
        candidates.update(self._normalize_category_text(alias) for alias in aliases if alias)
        return any(candidate and candidate in normalized_value for candidate in candidates)

    def _get_view_display_name(self, view_name: str) -> str:
        return {
            self.VIEW_CHARACTERS: self.tra("角色表"),
            self.VIEW_TERMS: self.tra("术语表"),
            self.VIEW_NON_TRANSLATE: self.tra("禁翻表"),
        }.get(view_name, self.tra("角色表"))

    def _get_display_field_value(
        self,
        view_name: str,
        field_name: str,
        value: Any,
        row: dict | None = None,
    ) -> str:
        if field_name == "gender":
            return self._get_character_category_value(value)
        if field_name == "category_path":
            return self._get_term_category_value(value)
        if field_name == "category":
            return self._get_non_translate_category_value(value)
        return "" if value is None else str(value)

    def _get_display_filter_value(self, view_name: str, value: Any) -> str:
        field_name = {
            self.VIEW_CHARACTERS: "gender",
            self.VIEW_TERMS: "category_path",
            self.VIEW_NON_TRANSLATE: "category",
        }.get(view_name)
        if not field_name:
            return "" if value is None else str(value)
        return self._get_display_field_value(view_name, field_name, value)

    def _build_action_bar(self) -> None:
        self.header_widget = QWidget(self)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.status_card = CardWidget(self.header_widget)
        self.status_card.setBorderRadius(12)
        self.status_card.setMinimumHeight(92)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(4)
        status_card_title = StrongBodyLabel(self.tra("操作"), self.status_card)
        self.start_button = PrimaryPushButton(FIF.PLAY, self.tra("开始分析"), self.status_card)
        self.stop_button = TransparentPushButton(FIF.CANCEL_MEDIUM, self.tra("停止"), self.status_card)
        self.start_button.setFixedHeight(28)
        self.stop_button.setFixedHeight(28)
        self.start_button.clicked.connect(self.start_analysis)
        self.stop_button.clicked.connect(self.stop_analysis)
        status_layout.addWidget(status_card_title)
        status_layout.addStretch(1)
        action_button_layout = QHBoxLayout()
        action_button_layout.setContentsMargins(0, 0, 0, 0)
        action_button_layout.setSpacing(4)
        action_button_layout.addWidget(self.start_button)
        action_button_layout.addWidget(self.stop_button)
        status_layout.addLayout(action_button_layout)
        status_layout.addStretch(1)

        self.progress_card = CardWidget(self.header_widget)
        self.progress_card.setBorderRadius(12)
        self.progress_card.setMinimumHeight(92)
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(12, 10, 12, 10)
        progress_layout.setSpacing(4)

        progress_title_layout = QHBoxLayout()
        progress_title_layout.setContentsMargins(0, 0, 0, 0)
        progress_title_layout.setSpacing(4)
        progress_card_title = StrongBodyLabel(self.tra("进度"), self.progress_card)
        self.progress_percent_label = StrongBodyLabel("0%", self.progress_card)
        progress_title_layout.addWidget(progress_card_title)
        progress_title_layout.addStretch(1)
        progress_title_layout.addWidget(self.progress_percent_label)

        self.progress_bar = ProgressBar(self.progress_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(5)
        self.phase_label = BodyLabel(self.tra("待开始"), self.progress_card)
        self.progress_info_label = CaptionLabel("", self.progress_card)
        self.progress_info_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        progress_info_layout = QHBoxLayout()
        progress_info_layout.setContentsMargins(0, 0, 0, 0)
        progress_info_layout.setSpacing(4)
        progress_info_layout.addWidget(self.phase_label)
        progress_info_layout.addStretch(1)
        progress_info_layout.addWidget(self.progress_info_label, 0, Qt.AlignRight)

        progress_layout.addLayout(progress_title_layout)
        progress_layout.addStretch(1)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(progress_info_layout)
        progress_layout.addStretch(1)

        self.result_card = CardWidget(self.header_widget)
        self.result_card.setBorderRadius(12)
        self.result_card.setMinimumHeight(92)
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setContentsMargins(12, 10, 12, 10)
        result_layout.setSpacing(4)

        result_card_title = StrongBodyLabel(self.tra("结果"), self.result_card)
        metrics_layout = QHBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(2)
        self.characters_metric_value = self._create_result_metric(
            metrics_layout,
            "角色",
        )
        self.terms_metric_value = self._create_result_metric(
            metrics_layout,
            "术语",
        )
        self.non_translate_metric_value = self._create_result_metric(
            metrics_layout,
            "禁翻",
        )

        result_layout.addWidget(result_card_title)
        result_layout.addStretch(1)
        result_layout.addLayout(metrics_layout)

        header_layout.addWidget(self.status_card, 2)
        header_layout.addWidget(self.progress_card, 5)
        header_layout.addWidget(self.result_card, 4)

    def _create_result_metric(self, parent_layout: QHBoxLayout, title: str) -> SubtitleLabel:
        metric_widget = QWidget(self.result_card)
        metric_layout = QVBoxLayout(metric_widget)
        metric_layout.setContentsMargins(4, 0, 4, 0)
        metric_layout.setSpacing(0)
        metric_value = SubtitleLabel("0", metric_widget)
        metric_value.setAlignment(Qt.AlignCenter)
        metric_label = CaptionLabel(self.tra(title), metric_widget)
        metric_label.setAlignment(Qt.AlignCenter)
        metric_label.setStyleSheet("color: #7A7A7A;")
        metric_layout.addWidget(metric_value)
        metric_layout.addWidget(metric_label)
        parent_layout.addWidget(metric_widget, 1)
        return metric_value

    def _create_default_runtime_state(self) -> dict:
        return {
            "status_key": "idle",
            "phase_key": "prepare",
            "percent": 0,
            "info_text": "",
        }

    def _apply_runtime_state(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if key in self.analysis_runtime_state and value is not None:
                self.analysis_runtime_state[key] = value

    def _sync_runtime_state_from_context(self) -> None:
        if self._is_analysis_running():
            if self.analysis_runtime_state.get("status_key") == "stopping":
                return
            if self.analysis_runtime_state.get("status_key") != "running":
                self.analysis_runtime_state = self._create_default_runtime_state()
                self._apply_runtime_state(
                    status_key="running",
                    phase_key="prepare",
                    info_text=self.tra("分析中..."),
                )
            return

        status_key = str(self.analysis_data.get("status", "")).strip()
        if status_key == "success":
            self.analysis_runtime_state = self._create_default_runtime_state()
            self._apply_runtime_state(
                status_key="success",
                phase_key="finalize",
                percent=100,
            )
            return

        if status_key == "partial":
            self.analysis_runtime_state = self._create_default_runtime_state()
            self._apply_runtime_state(
                status_key="partial",
                phase_key="finalize",
                percent=100,
            )
            return

        self.analysis_runtime_state = self._create_default_runtime_state()
        if self.analysis_data:
            self._apply_runtime_state(percent=100)

    def _infer_phase_key_from_message(self, message: str) -> str:
        text = self._normalize_category_text(message)
        if not text:
            return "prepare"

        phase_hints = (
            (
                "stage1",
                (
                    "第一阶段",
                    "stage 1",
                    self.tra("第一阶段"),
                    self.tra("开始执行第一阶段分析任务..."),
                    self.tra("第一阶段提取中..."),
                ),
            ),
            (
                "stage2",
                (
                    "第二阶段",
                    "stage 2",
                    self.tra("第二阶段"),
                    self.tra("开始执行第二阶段分析任务..."),
                    self.tra("第二阶段合并中..."),
                ),
            ),
            (
                "finalize",
                (
                    "结果整合",
                    "最终",
                    "finalize",
                    self.tra("结果整合"),
                    self.tra("正在整合最终分析结果..."),
                    self.tra("分析结果已生成..."),
                ),
            ),
        )
        for phase_key, hints in phase_hints:
            if any(self._normalize_category_text(hint) in text for hint in hints if hint):
                return phase_key
        return "prepare"

    def _get_status_color(self, status_key: str) -> QColor:
        if status_key == "running":
            return QColor(themeColor())
        if status_key == "stopping":
            return QColor("#D0891A")
        if status_key == "success":
            return QColor("#2A9D68")
        if status_key in ("stopped", "partial"):
            return QColor("#B7791F")
        if status_key == "error":
            return QColor("#D64545")
        return QColor("#8A9099")

    def _render_header(self) -> None:
        state = self.analysis_runtime_state
        status_key = str(state.get("status_key", "idle") or "idle")
        phase_key = str(state.get("phase_key", "prepare") or "prepare")
        info_text = str(state.get("info_text", "") or "")
        percent = max(0, min(100, int(state.get("percent", 0) or 0)))

        color = self._get_status_color(status_key)
        phase_text = {
            "prepare": self.tra("准备"),
            "stage1": self.tra("阶段 1"),
            "stage2": self.tra("阶段 2"),
            "finalize": self.tra("完成"),
        }.get(phase_key, self.tra("待开始"))

        self.progress_percent_label.setText(f"{percent}%")
        self.progress_percent_label.setStyleSheet(f"color: {color.name()};")
        self.progress_bar.setValue(percent)
        self.phase_label.setText(phase_text)
        self.phase_label.setStyleSheet(f"color: {color.name()};")
        progress_info = info_text if status_key in ("running", "stopping") else ""
        self.progress_info_label.setText(progress_info)
        self.progress_info_label.setStyleSheet("color: #7A7A7A;")

        counts = self._get_counts()
        self.characters_metric_value.setText(str(counts["characters"]))
        self.terms_metric_value.setText(str(counts["terms"]))
        self.non_translate_metric_value.setText(str(counts["non_translate"]))

    def _build_body(self) -> None:
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("QSplitter::handle { width: 8px; background: transparent; }")

        self.nav_card = CardWidget(self)
        self.nav_card.setMinimumWidth(0)
        self.nav_card.setBorderRadius(12)
        nav_layout = QVBoxLayout(self.nav_card)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(8)

        self.nav_title_label = StrongBodyLabel(self.tra("项目表格"), self.nav_card)
        setFont(self.nav_title_label, 12)
        self.nav_title_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(self.nav_title_label)

        self.nav_tree = TreeWidget(self.nav_card)
        self.nav_tree.setMinimumWidth(0)
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        nav_layout.addWidget(self.nav_tree)

        self.right_panel = QWidget(self)
        self.right_panel.setMinimumWidth(0)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.page_card = CardWidget(self)
        self.page_card.setMinimumWidth(0)
        self.page_card.setBorderRadius(12)
        page_layout = QVBoxLayout(self.page_card)
        page_layout.setContentsMargins(10, 10, 10, 10)
        page_layout.setSpacing(8)

        self.table_detail_widget = QWidget(self.page_card)
        detail_layout = QHBoxLayout(self.table_detail_widget)
        detail_layout.setContentsMargins(2, 0, 2, 0)
        detail_layout.setSpacing(8)

        self.table_detail_label = BodyLabel(self.tra("角色表"), self.table_detail_widget)
        detail_layout.addWidget(self.table_detail_label)
        detail_layout.addStretch(1)

        self.save_public_table_button = TransparentPushButton(self.tra("保存到公共表"), self.table_detail_widget)
        self.clear_current_table_button = TransparentPushButton(self.tra("清空"), self.table_detail_widget)
        self.save_public_table_button.setFixedHeight(28)
        self.clear_current_table_button.setFixedHeight(28)
        self.save_public_table_button.clicked.connect(self._save_current_view_to_public_table)
        self.clear_current_table_button.clicked.connect(self._clear_current_view_rows)
        detail_layout.addWidget(self.save_public_table_button)
        detail_layout.addWidget(self.clear_current_table_button)

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

        page_layout.addWidget(self.table_detail_widget)
        page_layout.addWidget(self.content_stack)
        right_layout.addWidget(self.header_widget)
        right_layout.addWidget(self.page_card, 1)

        self.splitter.addWidget(self.nav_card)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.characters_table = self._create_table(
            self.VIEW_CHARACTERS,
            [
                self.tra("原文键"),
                self.tra("推荐译名"),
                self.tra("性别"),
                self.tra("备注"),
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.terms_table = self._create_table(
            self.VIEW_TERMS,
            [
                self.tra("原文"),
                self.tra("推荐译名"),
                self.tra("分类属性"),
                self.tra("备注"),
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.non_translate_table = self._create_table(
            self.VIEW_NON_TRANSLATE,
            [self.tra("原文"), self.tra("分类"), self.tra("备注")],
        )
        self.non_translate_table.itemChanged.connect(
            lambda item: self._on_table_item_changed(self.VIEW_NON_TRANSLATE, item)
        )
        layout.addWidget(self.non_translate_table, 1)
        return page

    def _create_table(self, view_name: str, headers: list[str]) -> TableWidget:
        table = TableWidget(self)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.setWordWrap(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setBorderRadius(8)
        table.setBorderVisible(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, current_table=table, current_view=view_name: self._show_table_context_menu(
                current_view, current_table, pos
            )
        )
        return table

    def _show_table_context_menu(self, view_name: str, table: TableWidget, pos: QPoint) -> None:
        item = table.itemAt(pos)
        if item and not table.selectionModel().isRowSelected(item.row(), table.rootIndex()):
            table.clearSelection()
            table.selectRow(item.row())

        menu = RoundMenu(parent=self)
        selected_row_count = len(table.selectionModel().selectedRows()) if table.selectionModel() else 0
        running = self._is_analysis_running()

        insert_action = Action(
            FIF.ADD_TO,
            self.tra("插入新行"),
            triggered=lambda: self._insert_row(view_name, table),
        )
        insert_action.setEnabled(not running)
        menu.addAction(insert_action)

        delete_action = Action(
            FIF.DELETE,
            self.tra("删除选中项"),
            triggered=lambda: self._delete_selected_rows(view_name, table),
        )
        delete_action.setEnabled(selected_row_count > 0 and not running)
        menu.addAction(delete_action)
        menu.addSeparator()

        row_count_action = Action(FIF.LEAF, self.tra("行数: {0}").format(table.rowCount()))
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)

        menu.exec(table.mapToGlobal(pos))

    def _apply_initial_table_widths(self, view_name: str) -> None:
        if view_name in self._table_width_ratio_initialized:
            return

        table = self._get_table_for_view(view_name)
        if not table:
            return

        ratios = self._get_initial_column_ratios(view_name)
        if not ratios or len(ratios) != table.columnCount():
            return

        available_width = table.viewport().width() or table.width()
        if available_width <= 0:
            return

        min_widths = self._get_initial_column_min_widths(view_name)
        total_ratio = sum(ratios)
        used_width = 0
        last_column_index = table.columnCount() - 1

        for index in range(last_column_index):
            width = int(available_width * ratios[index] / total_ratio)
            if index < len(min_widths):
                width = max(min_widths[index], width)
            table.setColumnWidth(index, width)
            used_width += width

        last_width = max(
            min_widths[last_column_index] if last_column_index < len(min_widths) else 120,
            available_width - used_width,
        )
        table.setColumnWidth(last_column_index, last_width)
        self._table_width_ratio_initialized.add(view_name)

    def _get_table_for_view(self, view_name: str) -> TableWidget | None:
        return {
            self.VIEW_CHARACTERS: self.characters_table,
            self.VIEW_TERMS: self.terms_table,
            self.VIEW_NON_TRANSLATE: self.non_translate_table,
        }.get(view_name)

    def _get_initial_column_ratios(self, view_name: str) -> tuple[int, ...]:
        return {
            self.VIEW_CHARACTERS: (18, 18, 7, 57),
            self.VIEW_TERMS: (18, 18, 7, 57),
            self.VIEW_NON_TRANSLATE: (18, 15, 67),
        }.get(view_name, ())

    def _get_initial_column_min_widths(self, view_name: str) -> tuple[int, ...]:
        return {
            self.VIEW_CHARACTERS: (180, 180, 100, 200),
            self.VIEW_TERMS: (170, 170, 130, 220),
            self.VIEW_NON_TRANSLATE: (180, 120, 260),
        }.get(view_name, ())

    def _get_category_options_for_view(self, view_name: str) -> tuple[str, ...]:
        return {
            self.VIEW_CHARACTERS: self.CHARACTER_CATEGORIES,
            self.VIEW_TERMS: self.TERM_CATEGORIES,
            self.VIEW_NON_TRANSLATE: self.NON_TRANSLATE_CATEGORIES,
        }.get(view_name, ())

    def _allows_custom_categories_for_view(self, view_name: str) -> bool:
        return view_name in (self.VIEW_CHARACTERS, self.VIEW_TERMS, self.VIEW_NON_TRANSLATE)

    def _get_category_count_key_for_view(self, view_name: str) -> str | None:
        return {
            self.VIEW_CHARACTERS: "character_categories",
            self.VIEW_TERMS: "term_categories",
            self.VIEW_NON_TRANSLATE: "non_translate_categories",
        }.get(view_name)

    def _get_total_count_for_view(self, counts: dict, view_name: str) -> int:
        total_key = self._get_analysis_key(view_name)
        return int(counts.get(total_key or "", 0) or 0)

    def _get_category_for_row(self, view_name: str, row: dict) -> str:
        if view_name == self.VIEW_CHARACTERS:
            return self._get_character_category_value(row.get("gender"), fallback=self.CHARACTER_OTHER)
        if view_name == self.VIEW_TERMS:
            return self._get_term_category_value(row.get("category_path"), fallback="Other")
        if view_name == self.VIEW_NON_TRANSLATE:
            return self._get_non_translate_category_value(
                row.get("category"),
                fallback="Other",
            )
        return ""

    def _build_category_counts(self, view_name: str, rows: list[dict]) -> dict[str, int]:
        counts = {category: 0 for category in self._get_category_options_for_view(view_name)}
        for row in rows:
            category = self._get_category_for_row(view_name, row)
            if category not in counts and self._allows_custom_categories_for_view(view_name) and category:
                counts[category] = 0
            if category in counts:
                counts[category] += 1
        return counts

    def _get_navigation_categories_for_view(
        self,
        view_name: str,
        category_counts: dict[str, int],
        empty_state: bool,
    ) -> list[str]:
        default_categories = list(self._get_category_options_for_view(view_name))
        if empty_state:
            return default_categories

        categories = [
            category for category in default_categories if int(category_counts.get(category, 0) or 0) > 0
        ]
        if self._allows_custom_categories_for_view(view_name):
            categories.extend(
                category
                for category in category_counts.keys()
                if category not in default_categories and int(category_counts.get(category, 0) or 0) > 0
            )
        return categories

    def _is_navigation_empty_state(self, counts: dict) -> bool:
        return (
            self._get_total_count_for_view(counts, self.VIEW_CHARACTERS)
            + self._get_total_count_for_view(counts, self.VIEW_TERMS)
            + self._get_total_count_for_view(counts, self.VIEW_NON_TRANSLATE)
            == 0
        )

    def _build_navigation_model(self) -> list[dict[str, Any]]:
        counts = self._get_counts()
        empty_state = self._is_navigation_empty_state(counts)
        navigation_model = []

        for view_name in (self.VIEW_CHARACTERS, self.VIEW_TERMS, self.VIEW_NON_TRANSLATE):
            category_count_key = self._get_category_count_key_for_view(view_name)
            category_counts = dict(counts.get(category_count_key or "", {}) or {})
            categories = self._get_navigation_categories_for_view(
                view_name, category_counts, empty_state
            )

            navigation_model.append(
                {
                    "view_name": view_name,
                    "title": self._get_view_display_name(view_name),
                    "count": self._get_total_count_for_view(counts, view_name),
                    "categories": [
                        {
                            "name": category,
                            "count": int(category_counts.get(category, 0) or 0),
                        }
                        for category in categories
                    ],
                }
            )

        return navigation_model

    def _set_filter_for_view(self, view_name: str, filter_value) -> None:
        if view_name == self.VIEW_CHARACTERS:
            self.current_character_filter = filter_value
        elif view_name == self.VIEW_TERMS:
            self.current_term_filter = filter_value
        elif view_name == self.VIEW_NON_TRANSLATE:
            self.current_non_translate_filter = filter_value

    def _field_affects_category_grouping(self, view_name: str, field_name: str) -> bool:
        if view_name == self.VIEW_CHARACTERS:
            return field_name == "gender"
        if view_name == self.VIEW_TERMS:
            return field_name == "category_path"
        if view_name == self.VIEW_NON_TRANSLATE:
            return field_name in {"category", "marker", "note"}
        return False

    def _refresh_navigation(self) -> None:
        expanded_views = set()
        root = self.nav_tree.invisibleRootItem()
        for index in range(root.childCount()):
            item = root.child(index)
            data = item.data(0, Qt.UserRole)
            if item.isExpanded() and data:
                expanded_views.add(data[0])

        self.nav_tree.clear()
        for section in self._build_navigation_model():
            item = QTreeWidgetItem([f"{section['title']} ({section['count']})"])
            item.setData(0, Qt.UserRole, (section["view_name"], None))
            for category in section["categories"]:
                child = QTreeWidgetItem([f"{category['name']} ({category['count']})"])
                child.setData(0, Qt.UserRole, (section["view_name"], category["name"]))
                item.addChild(child)
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

        self._fill_table(
            self.characters_table,
            rows,
            [("source", True), ("recommended_translation", True), ("gender", True), ("note", True)],
            self.VIEW_CHARACTERS,
        )

    def _populate_terms_table(self) -> None:
        rows = self._get_visible_rows(self.VIEW_TERMS)

        self._fill_table(
            self.terms_table,
            rows,
            [("source", True), ("recommended_translation", True), ("category_path", True), ("note", True)],
            self.VIEW_TERMS,
        )

    def _populate_non_translate_table(self) -> None:
        rows = self._get_visible_rows(self.VIEW_NON_TRANSLATE)

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
                display_value = self._get_display_field_value(view_name, field_name, value, row)
                item = QTableWidgetItem(display_value)
                item.setData(Qt.UserRole, row_key)
                if not editable:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row_index, col_index, item)
        table.resizeRowsToContents()
        table.blockSignals(False)

    def on_nav_item_clicked(self, item, column) -> None:
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        view_name, filter_value = data
        self.current_view = view_name
        self._set_filter_for_view(view_name, filter_value)
        if view_name == self.VIEW_CHARACTERS:
            self._populate_characters_table()
        elif view_name == self.VIEW_TERMS:
            self._populate_terms_table()
        else:
            self._populate_non_translate_table()

        self._switch_content_view(view_name)

    def _switch_content_view(self, view_name: str) -> None:
        mapping = {
            self.VIEW_CHARACTERS: self.characters_page,
            self.VIEW_TERMS: self.terms_page,
            self.VIEW_NON_TRANSLATE: self.non_translate_page,
        }
        self.content_stack.setCurrentWidget(mapping.get(view_name, self.characters_page))
        self._refresh_table_detail_header()
        QTimer.singleShot(0, lambda: self._apply_initial_table_widths(view_name))

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
            self._set_filter_for_view(self.current_view, None)
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
            self.warning_toast(self.tra("提示"), self.tra("当前有其他任务正在执行，请稍后再试。"))
            return
        if not self.cache_manager or not self.cache_manager.project:
            self.warning_toast(self.tra("提示"), self.tra("当前没有已加载的项目。"))
            return

        if self.analysis_data:
            message_box = MessageBox(
                self.tra("确认"),
                self.tra("重新开始分析会覆盖当前项目中的分析结果，是否继续？"),
                self.window(),
            )
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if not message_box.exec():
                return

        self.analysis_runtime_state = self._create_default_runtime_state()
        self._apply_runtime_state(
            status_key="running",
            phase_key="prepare",
            info_text=self.tra("正在准备..."),
        )
        self._render_header()
        self._update_action_buttons(running=True)
        self.emit(Base.EVENT.ANALYSIS_TASK_START, {})

    def stop_analysis(self) -> None:
        if not self._is_analysis_running():
            return

        message_box = MessageBox(
            self.tra("确认"),
            self.tra("是否确定停止当前分析任务？"),
            self.window(),
        )
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        self._apply_runtime_state(
            status_key="stopping",
            info_text=self.tra("正在停止..."),
        )
        self._render_header()
        self._update_action_buttons(running=True)
        self.stop_button.setEnabled(False)
        self.emit(Base.EVENT.TASK_STOP, {})

    def on_analysis_task_update(self, event: int, data: dict) -> None:
        if self.analysis_runtime_state.get("status_key") == "stopping":
            return

        message = str(data.get("message", "")).strip() or self.tra("分析中")
        is_structured = any(
            key in data for key in ("status", "phase", "percent", "detail")
        )
        if is_structured:
            self._apply_runtime_state(
                status_key=str(data.get("status", "running") or "running"),
                phase_key=str(data.get("phase", "prepare") or "prepare"),
                percent=int(data.get("percent", 0) or 0),
                info_text=str(data.get("detail", "")).strip() or message,
            )
        else:
            phase_key = self._infer_phase_key_from_message(message)
            self._apply_runtime_state(
                status_key="running",
                phase_key=phase_key,
                info_text=message,
            )
        self._render_header()

    def on_analysis_task_done(self, event: int, data: dict) -> None:
        status = str(data.get("status", "error"))
        analysis_data = data.get("analysis_data")
        message = str(data.get("message", "")).strip()

        if analysis_data:
            self.analysis_data = self._clone_analysis_data(analysis_data)
            self._sync_stats()
            self.cache_manager.set_analysis_data(self._clone_analysis_data(self.analysis_data))
            self._refresh_navigation()
            self._refresh_all_views()
            self._request_cache_save()

        self._update_action_buttons()
        if status == "success":
            self._apply_runtime_state(
                status_key="success",
                phase_key="finalize",
                percent=100,
            )
            self._render_header()
            self.success_toast(self.tra("完成"), message or self.tra("全文分析完成。"))
        elif status == "partial":
            self._apply_runtime_state(
                status_key="partial",
                phase_key="finalize",
                percent=100,
            )
            self._render_header()
            self.warning_toast(self.tra("完成"), message or self.tra("分析已完成，但存在失败的分块。"))
        elif status == "stopped":
            self._apply_runtime_state(
                status_key="stopped",
            )
            self._render_header()
            self.info_toast(self.tra("已停止"), message or self.tra("分析任务已停止。"))
        else:
            self._apply_runtime_state(
                status_key="error",
            )
            self._render_header()
            self.error_toast(self.tra("失败"), message or self.tra("全文分析失败。"))

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
        display_value = new_value
        refresh_navigation = self._field_affects_category_grouping(view_name, field_name)
        refresh_view = refresh_navigation
        if view_name == self.VIEW_CHARACTERS and field_name == "gender":
            new_value = self._get_character_category_value(new_value, fallback=self.CHARACTER_OTHER)
            display_value = self._get_display_field_value(view_name, field_name, new_value, target_row)
        elif view_name == self.VIEW_TERMS and field_name == "category_path":
            new_value = self._get_term_category_value(new_value, fallback="Other")
            display_value = self._get_display_field_value(view_name, field_name, new_value, target_row)
        elif view_name == self.VIEW_NON_TRANSLATE and field_name == "category":
            new_value = self._get_non_translate_category_value(
                new_value,
                fallback="Other",
            )
            display_value = self._get_display_field_value(view_name, field_name, new_value, target_row)

        key_field = self._get_row_identity_field(view_name)
        if field_name == key_field:
            current_identity_value = self._normalize_row_key(target_row.get(key_field, ""))
            if not new_value:
                new_value = current_identity_value
            else:
                next_key = self._normalize_row_key(new_value)
                existing_row = self._find_row_by_key(view_name, next_key)
                if existing_row and existing_row is not target_row:
                    self.warning_toast(self.tra("提示"), self.tra("原文键已存在，不能重复。"))
                    new_value = current_identity_value
                    display_value = current_identity_value
                refresh_view = True

        if item.text() != display_value:
            self._updating_ui = True
            item.setText(display_value)
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

    def _insert_row(self, view_name: str, table: TableWidget) -> None:
        if self._is_analysis_running():
            self.warning_toast(self.tra("提示"), self.tra("分析任务执行中，暂时不能插入新行。"))
            return

        key = self._get_analysis_key(view_name)
        if not key:
            return

        rows = self.analysis_data.setdefault(key, [])
        insert_index = self._get_insert_row_index(view_name, table)
        new_row = self._create_empty_row(view_name)
        new_row["_row_key"] = self._create_temp_row_key()
        rows.insert(insert_index, new_row)

        self._persist_analysis_state(refresh_navigation=True)
        self._refresh_all_views()
        self._focus_row_by_key(view_name, new_row["_row_key"])
        self.success_toast(self.tra("完成"), self.tra("新行已插入。"))

    def _create_empty_row(self, view_name: str) -> dict:
        current_filter = self._get_filter_for_view(view_name)
        if view_name == self.VIEW_CHARACTERS:
            return {
                "source": "",
                "recommended_translation": "",
                "gender": self._get_character_category_value(current_filter, fallback=self.CHARACTER_OTHER),
                "note": "",
            }
        if view_name == self.VIEW_TERMS:
            return {
                "source": "",
                "recommended_translation": "",
                "category_path": self._get_term_category_value(current_filter, fallback="Other"),
                "note": "",
            }
        return {
            "marker": "",
            "category": self._get_non_translate_category_value(current_filter, fallback="Other"),
            "note": "",
        }

    def _get_insert_row_index(self, view_name: str, table: TableWidget) -> int:
        key = self._get_analysis_key(view_name)
        rows = self.analysis_data.get(key, []) or []
        selected_row_keys = self._get_selected_row_keys(table)
        if selected_row_keys:
            anchor_row_key = selected_row_keys[-1]
        else:
            visible_rows = self._get_visible_rows(view_name)
            anchor_row_key = self._get_row_key(view_name, visible_rows[-1]) if visible_rows else ""

        if not anchor_row_key:
            return len(rows)

        for index, row in enumerate(rows):
            if self._get_row_key(view_name, row) == anchor_row_key:
                return index + 1

        return len(rows)

    def _create_temp_row_key(self) -> str:
        self._temp_row_counter += 1
        return f"__analysis_temp_row__{self._temp_row_counter}"

    def _focus_row_by_key(self, view_name: str, row_key: str) -> None:
        table = self._get_table_for_view(view_name)
        normalized_row_key = self._normalize_row_key(row_key)
        if not table or not normalized_row_key:
            return

        table.clearSelection()
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            current_row_key = self._normalize_row_key(item.data(Qt.UserRole) if item else "")
            if current_row_key != normalized_row_key:
                continue

            table.setCurrentCell(row_index, 0)
            table.selectRow(row_index)
            if item:
                table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                table.editItem(item)
            return

    def _save_current_view_to_public_table(self) -> None:
        if self._is_analysis_running():
            self.warning_toast(self.tra("提示"), self.tra("分析任务执行中，暂时不能保存到公共表。"))
            return
        if not self.cache_manager or not self.cache_manager.project:
            self.warning_toast(self.tra("提示"), self.tra("当前没有已加载的项目。"))
            return

        public_rows = self._build_public_table_rows(self.current_view)
        if not public_rows:
            self.info_toast(self.tra("提示"), self.tra("当前显示内容中没有可保存的条目。"))
            return

        config = self.load_config()
        added_count = 0
        if self.current_view == self.VIEW_NON_TRANSLATE:
            current_rows = list(config.get("exclusion_list_data", []) or [])
            existing_keys = {
                self._normalize_row_key(item.get("markers"))
                for item in current_rows
                if self._normalize_row_key(item.get("markers"))
            }
            for row in public_rows:
                row_key = self._normalize_row_key(row.get("markers"))
                if not row_key or row_key in existing_keys:
                    continue
                current_rows.append(row)
                existing_keys.add(row_key)
                added_count += 1
            config["exclusion_list_data"] = current_rows
        else:
            current_rows = list(config.get("prompt_dictionary_data", []) or [])
            existing_keys = {
                self._normalize_row_key(item.get("src"))
                for item in current_rows
                if self._normalize_row_key(item.get("src"))
            }
            for row in public_rows:
                row_key = self._normalize_row_key(row.get("src"))
                if not row_key or row_key in existing_keys:
                    continue
                current_rows.append(row)
                existing_keys.add(row_key)
                added_count += 1
            config["prompt_dictionary_data"] = GlossaryHelper.normalize_rows(current_rows)

        if added_count <= 0:
            self.info_toast(self.tra("提示"), self.tra("当前内容均已存在于公共表中。"))
            return

        self.save_config(config)
        self.success_toast(self.tra("完成"), self.tra("已保存到公共表，新增 {0} 条内容。").format(added_count))

    def _build_public_table_rows(self, view_name: str) -> list[dict]:
        rows = []
        for row in self._get_visible_rows(view_name):
            if view_name == self.VIEW_CHARACTERS:
                source = self._normalize_row_key(row.get("source"))
                if not source:
                    continue
                rows.append(
                    {
                        "src": source,
                        "dst": str(row.get("recommended_translation", "") or "").strip(),
                        "info": self._join_public_info_parts(
                            f"性别: {self._get_character_category_value(row.get('gender'), fallback=self.CHARACTER_OTHER)}",
                            f"备注: {str(row.get('note', '') or '').strip()}",
                        ),
                    }
                )
            elif view_name == self.VIEW_TERMS:
                source = self._normalize_row_key(row.get("source"))
                if not source:
                    continue
                rows.append(
                    {
                        "src": source,
                        "dst": str(row.get("recommended_translation", "") or "").strip(),
                        "info": self._join_public_info_parts(
                            f"分类: {self._get_term_category_value(row.get('category_path'), fallback='Other')}",
                            f"备注: {str(row.get('note', '') or '').strip()}",
                        ),
                    }
                )
            else:
                marker = self._normalize_row_key(row.get("marker"))
                if not marker:
                    continue
                rows.append(
                    {
                        "markers": marker,
                        "info": self._join_public_info_parts(
                            f"分类: {self._get_non_translate_category_value(row.get('category'), fallback='Other')}",
                            f"备注: {str(row.get('note', '') or '').strip()}",
                        ),
                        "regex": "",
                    }
                )
        return rows

    def _join_public_info_parts(self, *parts: str) -> str:
        return "；".join(part for part in parts if str(part).strip())

    def _clear_current_view_rows(self) -> None:
        if self._is_analysis_running():
            self.warning_toast(self.tra("提示"), self.tra("分析任务执行中，暂时不能清空当前显示内容。"))
            return

        row_keys = self._get_visible_row_keys(self.current_view)
        if not row_keys:
            self.info_toast(self.tra("提示"), self.tra("当前显示内容为空。"))
            return

        detail_name = self._get_table_detail_display_text()
        message_box = MessageBox(
            self.tra("确认"),
            self.tra("确定要清空当前显示的 {0} 吗？\n共 {1} 条内容将被删除。").format(detail_name, len(row_keys)),
            self.window(),
        )
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        deleted_count = self._delete_rows(self.current_view, row_keys)
        if deleted_count:
            self._refresh_navigation()
            self.nav_tree.viewport().update()
            self.success_toast(self.tra("完成"), self.tra("已清空当前显示的 {0} 条内容。").format(deleted_count))

    def _get_visible_row_keys(self, view_name: str) -> list[str]:
        row_keys = []
        for row in self._get_visible_rows(view_name):
            row_key = self._get_row_key(view_name, row)
            if row_key and row_key not in row_keys:
                row_keys.append(row_key)
        return row_keys

    def _delete_rows(self, view_name: str, row_keys: list[str]) -> int:
        key = self._get_analysis_key(view_name)
        if not key:
            return 0

        normalized_row_keys = {
            self._normalize_row_key(row_key)
            for row_key in row_keys
            if self._normalize_row_key(row_key)
        }
        if not normalized_row_keys:
            return 0

        rows = self.analysis_data.get(key, []) or []
        original_count = len(rows)
        self.analysis_data[key] = [
            row for row in rows if self._get_row_key(view_name, row) not in normalized_row_keys
        ]
        deleted_count = original_count - len(self.analysis_data[key])
        if deleted_count <= 0:
            return 0

        self._persist_analysis_state(refresh_navigation=True)
        self._refresh_all_views()
        return deleted_count

    def _get_selected_row_keys(self, table: TableWidget) -> list[str]:
        if not table.selectionModel():
            return []

        row_keys = []
        for model_index in table.selectionModel().selectedRows():
            item = table.item(model_index.row(), 0)
            row_key = self._normalize_row_key(item.data(Qt.UserRole) if item else "")
            if row_key and row_key not in row_keys:
                row_keys.append(row_key)
        return row_keys

    def _delete_selected_rows(self, view_name: str, table: TableWidget) -> None:
        if self._is_analysis_running():
            self.warning_toast(self.tra("提示"), self.tra("分析任务执行中，暂时不能删除当前表内容。"))
            return

        row_keys = self._get_selected_row_keys(table)
        if not row_keys:
            self.info_toast(self.tra("提示"), self.tra("当前没有选中的内容。"))
            return

        message_box = MessageBox(
            self.tra("确认"),
            self.tra("确定要删除当前选中的 {0} 条内容吗？").format(len(row_keys)),
            self.window(),
        )
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        deleted_count = self._delete_rows(view_name, row_keys)
        if deleted_count:
            self.success_toast(self.tra("完成"), self.tra("已删除 {0} 条内容。").format(deleted_count))

    def _persist_analysis_state(self, refresh_navigation: bool = False) -> None:
        if not self.cache_manager or not self.cache_manager.project:
            return

        self._sync_stats()
        self.cache_manager.set_analysis_data(self._clone_analysis_data(self.analysis_data))
        self._request_cache_save()
        if refresh_navigation:
            self._refresh_navigation()
        self._apply_runtime_state(
            status_key="idle",
            phase_key="finalize" if self.analysis_data else "prepare",
            percent=100 if self.analysis_data else 0,
        )
        self._render_header()
        self._update_action_buttons()

    def _request_cache_save(self) -> None:
        if self.cache_manager and self.cache_manager.project:
            self.emit(Base.EVENT.TASK_MANUAL_SAVE_CACHE, {})

    def _sync_stats(self) -> None:
        if not self.analysis_data:
            return
        stats = dict(self.analysis_data.get("stats", {}) or {})
        stats["character_count"] = len(self.analysis_data.get("characters", []) or [])
        stats["term_count"] = len(self.analysis_data.get("terms", []) or [])
        stats["non_translate_count"] = len(self.analysis_data.get("non_translate", []) or [])
        stats["total_hits"] = (
            stats["character_count"] + stats["term_count"] + stats["non_translate_count"]
        )
        self.analysis_data["stats"] = stats



    def _update_action_buttons(self, running: bool | None = None) -> None:
        has_project = bool(self.cache_manager and self.cache_manager.project)
        if running is None:
            running = self._is_analysis_running()

        self.start_button.setEnabled(has_project and not running)
        self.stop_button.setEnabled(running)

        self._refresh_table_detail_header()

    def _refresh_table_detail_header(self) -> None:
        if not hasattr(self, "table_detail_label"):
            return

        self.table_detail_label.setText(self._get_table_detail_display_text())

        has_project = bool(self.cache_manager and self.cache_manager.project)
        running = self._is_analysis_running()
        has_visible_rows = bool(self._get_visible_rows(self.current_view))
        self.save_public_table_button.setEnabled(has_project and not running)
        self.clear_current_table_button.setEnabled(has_project and not running and has_visible_rows)

    def _get_table_detail_display_text(self) -> str:
        table_name = self._get_view_display_name(self.current_view)
        current_filter = self._get_filter_for_view(self.current_view)
        if current_filter:
            return f"{table_name} / {self._get_display_filter_value(self.current_view, current_filter)}"
        return table_name

    def _get_counts(self) -> dict:
        characters = self.analysis_data.get("characters", []) or []
        terms = self.analysis_data.get("terms", []) or []
        non_translates = self.analysis_data.get("non_translate", []) or []

        return {
            "characters": len(characters),
            "terms": len(terms),
            "non_translate": len(non_translates),
            "character_categories": self._build_category_counts(self.VIEW_CHARACTERS, characters),
            "term_categories": self._build_category_counts(self.VIEW_TERMS, terms),
            "non_translate_categories": self._build_category_counts(
                self.VIEW_NON_TRANSLATE, non_translates
            ),
        }

    def _get_visible_rows(self, view_name: str) -> list[dict]:
        key = self._get_analysis_key(view_name)
        if not key:
            return []

        rows = list(self.analysis_data.get(key, []) or [])
        current_filter = self._get_filter_for_view(view_name)
        if not current_filter:
            return rows

        return [row for row in rows if self._get_category_for_row(view_name, row) == current_filter]

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
        identity_value = self._normalize_row_key(row.get(self._get_row_identity_field(view_name), ""))
        if identity_value:
            return identity_value
        return self._normalize_row_key(row.get("_row_key", ""))

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

    def _get_character_category_value(self, value: Any, fallback: str = CHARACTER_OTHER) -> str:
        return self._compact_category_value(value) or fallback

    def _resolve_term_category(self, value) -> str:
        raw_value = self._compact_category_value(value)
        if not raw_value:
            return self.TERM_OTHER

        normalized_value = self._normalize_term_category(raw_value)
        if normalized_value != self.TERM_OTHER:
            return normalized_value
        if self._matches_category_alias(raw_value, self.TERM_OTHER, "other"):
            return self.TERM_OTHER
        return raw_value

    def _normalize_term_category(self, value) -> str:
        if self._matches_category_alias(value, self.TERM_IDENTITY, "人物身份", "称谓", "头衔", "职业", "角色", "identity", "role", "title", "class"):
            return self.TERM_IDENTITY
        if self._matches_category_alias(value, self.TERM_ITEM, "道具", "装备", "item", "artifact", "product", "weapon"):
            return self.TERM_ITEM
        if self._matches_category_alias(value, self.TERM_ORGANIZATION, "势力", "阵营", "团体", "organization", "org", "faction"):
            return self.TERM_ORGANIZATION
        if self._matches_category_alias(value, self.TERM_LOCATION, "地点", "城市", "国家", "location", "place", "loc", "gpe"):
            return self.TERM_LOCATION
        if self._matches_category_alias(value, self.TERM_SKILL, "法术", "招式", "能力", "skill", "skills", "spell", "spells", "ability", "abilities"):
            return self.TERM_SKILL
        if self._matches_category_alias(value, self.TERM_RACE, "族群", "族类", "race", "races", "species", "tribe"):
            return self.TERM_RACE
        return self.TERM_OTHER

    def _get_term_category_value(self, value: Any, fallback: str = "Other") -> str:
        return self._compact_category_value(value) or fallback

    # ==========================
    # 不翻译项分类推导逻辑
    # ==========================
    def _normalize_non_translate_category(self, value, marker="", note="") -> str:
        combined_hint = self._normalize_category_text(f"{value} {marker} {note}")
        
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_TAG, "tag", "html", "<", ">", "</"):
            return self.NON_TRANSLATE_TAG
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_VARIABLE, "var", "{{", "}}", "$"):
            return self.NON_TRANSLATE_VARIABLE
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_PLACEHOLDER, "占位", "placeholder", "%s", "%d", "{0}", "{1}"):
            return self.NON_TRANSLATE_PLACEHOLDER
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_MACRO, "宏", "macro", "icon", "[", "]", "【", "】"):
            return self.NON_TRANSLATE_MACRO
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_ESCAPE, "转义", "escape", "\\n", "\\t", "\\r", "\\\""):
            return self.NON_TRANSLATE_ESCAPE
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_RESOURCE, "路径", "标识", "res", "path", ".png", ".wav", ".mp3", "audio"):
            return self.NON_TRANSLATE_RESOURCE
        if self._contains_category_hint(combined_hint, self.NON_TRANSLATE_NUMERIC, "公式", "计算", "numeric", "math", "+", "-", "*", "/", "="):
            return self.NON_TRANSLATE_NUMERIC
            
        return self.NON_TRANSLATE_OTHER

    def _get_non_translate_category_value(
        self,
        value: Any,
        fallback: str = "Other",
    ) -> str:
        return self._compact_category_value(value) or fallback

    def _is_analysis_running(self) -> bool:
        return Base.work_status in (Base.STATUS.ANALYSIS_TASK, Base.STATUS.STOPING)
