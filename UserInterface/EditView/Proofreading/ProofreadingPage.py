import os
import threading
import time

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    FluentIcon as FIF,
    MessageBox,
    PrimaryPushButton,
    StrongBodyLabel,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.TranslationChecker.TranslationChecker import CheckResult, TranslationChecker
from UserInterface.EditView.Proofreading.Check.CheckResultPage import CheckResultPage
from UserInterface.EditView.Proofreading.Check.LanguageCheckDialog import LanguageCheckDialog
from UserInterface.EditView.Proofreading.Layout.NavigationCard import NavigationCard
from UserInterface.EditView.Proofreading.Layout.PageCard import PageCard
from UserInterface.EditView.Proofreading.Search.SearchDialog import SearchDialog
from UserInterface.EditView.Proofreading.Search.SearchResultPage import SearchResultPage
from UserInterface.EditView.Proofreading.Table.TabInterface import TabInterface
from UserInterface.Widget.Toast import ToastMixin


class ProofreadingPage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    languageCheckFinished = pyqtSignal(tuple)

    def __init__(self, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("ProofreadingPage")

        self.cache_manager = cache_manager
        self._splitter_ratio_initialized = False
        self._project_file_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        self.command_card = CardWidget(self)
        self.command_card.setBorderRadius(12)
        command_layout = QHBoxLayout(self.command_card)
        command_layout.setContentsMargins(18, 12, 18, 12)
        command_layout.setSpacing(16)

        command_info_layout = QVBoxLayout()
        command_info_layout.setContentsMargins(0, 0, 0, 0)
        command_info_layout.setSpacing(4)
        self.command_title_label = StrongBodyLabel(self.tra("校对"), self.command_card)
        self.command_title_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.command_summary_label = BodyLabel(self.tra("浏览文件、搜索文本并执行语言检测"), self.command_card)
        self.command_summary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        command_info_layout.addWidget(self.command_title_label)
        command_info_layout.addWidget(self.command_summary_label)

        self.start_check_button = PrimaryPushButton(FIF.EDUCATION, self.tra("开始检查"), self.command_card)
        self.start_check_button.setFixedHeight(32)
        self.start_check_button.setMinimumWidth(108)

        self.start_check_button.clicked.connect(self._open_language_check_dialog)
        command_layout.addWidget(self.start_check_button)
        command_layout.addStretch(1)
        command_layout.addLayout(command_info_layout)

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.nav_card = NavigationCard(self)
        self.right_panel = QWidget(self)
        self.page_card = PageCard(self)
        self.nav_card.setBorderRadius(12)
        self.page_card.setBorderRadius(12)
        self.right_panel.setMinimumWidth(0)

        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.command_card)
        right_layout.addWidget(self.page_card, 1)

        self.splitter.addWidget(self.nav_card)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 9)
        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("QSplitter::handle { width: 8px; background: transparent; }")

        layout.addWidget(self.splitter, 1)

        self.nav_card.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.page_card.tab_bar.currentChanged.connect(self.on_tab_changed)
        self.page_card.tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)
        self.nav_card.search_button.clicked.connect(self._open_search_dialog)
        self.languageCheckFinished.connect(self._on_language_check_finished)
        self._update_command_bar()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._splitter_ratio_initialized:
            QTimer.singleShot(0, self._apply_initial_splitter_sizes)

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

    def update_tree(self, hierarchy: dict) -> None:
        self._project_file_count = sum(len(files or []) for files in (hierarchy or {}).values())
        self.nav_card.update_tree(hierarchy)
        self._update_command_bar()

    def clear_tabs(self) -> None:
        while self.page_card.tab_bar.count() > 0:
            self.on_tab_close_requested(self.page_card.tab_bar.count() - 1)
        self._update_command_bar()

    def on_tree_item_clicked(self, item, column) -> None:
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return

        for index in range(self.page_card.stacked_widget.count()):
            widget = self.page_card.stacked_widget.widget(index)
            if widget and widget.objectName() == file_path:
                self.page_card.tab_bar.setCurrentIndex(index)
                self.page_card.stacked_widget.setCurrentIndex(index)
                self._update_command_bar()
                return

        cache_file = self.cache_manager.project.get_file(file_path)
        if not cache_file:
            MessageBox(
                self.tra("错误"),
                self.tra("无法从缓存中加载文件: {}").format(file_path),
                self,
            ).exec()
            return

        tab_name = os.path.basename(file_path)
        new_tab = TabInterface(tab_name, file_path, cache_file.items, self.cache_manager, self)

        self.page_card.stacked_widget.addWidget(new_tab)
        self.page_card.tab_bar.addTab(file_path, tab_name)

        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentWidget(new_tab)
        self._update_command_bar()

    def on_tab_changed(self, index: int) -> None:
        if index < 0:
            return

        widget = self.page_card.stacked_widget.widget(index)
        if widget:
            self.page_card.stacked_widget.setCurrentWidget(widget)

    def on_tab_close_requested(self, index: int) -> None:
        widget_to_remove = self.page_card.stacked_widget.widget(index)
        if widget_to_remove:
            self.page_card.stacked_widget.removeWidget(widget_to_remove)
            widget_to_remove.close()
            widget_to_remove.deleteLater()

        self.page_card.tab_bar.removeTab(index)
        self._update_command_bar()

    def _update_command_bar(self) -> None:
        open_tab_count = self.page_card.tab_bar.count()
        has_project_files = self._project_file_count > 0

        if has_project_files:
            self.command_summary_label.setText(
                self.tra("文件数: {} | 已打开标签: {}").format(self._project_file_count, open_tab_count)
            )
        else:
            self.command_summary_label.setText(self.tra("浏览文件、搜索文本并执行语言检测"))

        self.nav_card.search_button.setEnabled(has_project_files)
        self.start_check_button.setEnabled(has_project_files)

    def _open_search_dialog(self) -> None:
        dialog = SearchDialog(self.window())
        if dialog.exec():
            self.perform_search(
                {
                    "query": dialog.search_query,
                    "is_regex": dialog.is_regex,
                    "scope": dialog.search_scope,
                    "search_flagged": dialog.is_flagged_search,
                }
            )

    def _open_language_check_dialog(self) -> None:
        dialog = LanguageCheckDialog(self.window())
        if dialog.exec():
            self.perform_language_check(dialog.check_params)

    def perform_search(self, params: dict) -> None:
        query = params["query"]
        scope = params["scope"]
        is_regex = params["is_regex"]
        search_flagged = params["search_flagged"]

        self.info(
            f"正在搜索: '{query}' (范围: {scope}, 正则: {is_regex}, 标记行: {search_flagged})"
        )

        results = self.cache_manager.search_items(query, scope, is_regex, search_flagged)
        if not results:
            MessageBox(
                self.tra("未找到结果"),
                self.tra("未能找到与 '{}' 匹配的内容。").format(query),
                self.window(),
            ).exec()
            return

        tab_name = f"Search - {query[:20]}..."
        route_key = f"search_{int(time.time())}"

        for index in range(self.page_card.tab_bar.count()):
            if self.page_card.tab_bar.tabText(index) == tab_name:
                self.page_card.tab_bar.setCurrentIndex(index)
                self.page_card.stacked_widget.setCurrentIndex(index)
                return

        search_page = SearchResultPage(results, self.cache_manager, params)
        search_page.setObjectName(route_key)

        self.page_card.stacked_widget.addWidget(search_page)
        self.page_card.tab_bar.addTab(routeKey=route_key, text=tab_name)

        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentIndex(new_index)

    def perform_language_check(self, params: dict) -> None:
        self.info("开始执行检查任务..")
        thread = threading.Thread(target=self._language_check_worker, args=(params,), daemon=True)
        thread.start()

    def _language_check_worker(self, params: dict) -> None:
        checker = TranslationChecker(self.cache_manager)
        result_code, data = checker.check_process(params)
        self.languageCheckFinished.emit((result_code, data))

    def _on_language_check_finished(self, result: tuple) -> None:
        result_code, data = result

        if result_code == CheckResult.HAS_RULE_ERRORS:
            self._show_check_result_table(data)
            return

        title = self.tra("检查结果")
        msg_box = None

        if result_code == CheckResult.ERROR_CACHE:
            msg_box = MessageBox(title, self.tra("检查失败，请检查项目文件夹缓存是否正常"), self.window())
        elif result_code == CheckResult.ERROR_NO_TRANSLATION:
            msg_box = MessageBox(title, self.tra("检查失败，请先执行翻译流程"), self.window())
        elif result_code == CheckResult.ERROR_NO_POLISH:
            msg_box = MessageBox(title, self.tra("检查失败，请先执行润色流程"), self.window())
        elif result_code == CheckResult.SUCCESS_REPORT:
            msg_box = MessageBox(title, self.tra("检测完成，请查看控制台输出"), self.window())
        elif result_code == CheckResult.SUCCESS_JUDGE_PASS:
            lang = data.get("target_language", "N/A")
            content = self.tra("检查通过：项目的所有文件均符合设定译文预期").format(lang)
            msg_box = MessageBox(title, content, self.window())
        elif result_code == CheckResult.SUCCESS_JUDGE_FAIL:
            lang = data.get("target_language", "N/A")
            content = self.tra("项目的所有文件译文语言占比不正常，请检查标记行和控制台输出").format(lang)
            msg_box = MessageBox(title, content, self.window())

        if msg_box:
            msg_box.yesButton.setText(self.tra("确认"))
            msg_box.cancelButton.hide()
            msg_box.exec()

    def _show_check_result_table(self, errors: list) -> None:
        tab_name = self.tra("检查结果")
        route_key = f"check_res_{int(time.time())}"

        for index in range(self.page_card.tab_bar.count()):
            if self.page_card.tab_bar.tabText(index) == tab_name:
                self.page_card.tab_bar.setCurrentIndex(index)
                self.page_card.stacked_widget.setCurrentIndex(index)

        result_page = CheckResultPage(errors, self.cache_manager)
        result_page.setObjectName(route_key)

        self.page_card.stacked_widget.addWidget(result_page)
        self.page_card.tab_bar.addTab(routeKey=route_key, text=tab_name)

        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentIndex(new_index)

        self.warning("检查完成，发现 {0} 个问题，请查看生成的表格。".format(len(errors)))
