import os
import threading
import time

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, FluentIcon as FIF, MessageBox, PushButton, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.TranslationChecker.CheckResult import CheckResult
from ModuleFolders.Service.TranslationChecker.LanguageChecker import LanguageChecker
from ModuleFolders.Service.TranslationChecker.RuleChecker import RuleChecker
from ModuleFolders.Service.TranslationChecker.TerminologyChecker import TerminologyChecker
from UserInterface.EditView.Proofreading.LanguageCheck.LanguageCheckDialog import LanguageCheckDialog
from UserInterface.EditView.Proofreading.LanguageCheck.LanguageCheckResultPage import LanguageCheckResultPage
from UserInterface.EditView.Proofreading.Layout.NavigationCard import NavigationCard
from UserInterface.EditView.Proofreading.Layout.PageCard import PageCard
from UserInterface.EditView.Proofreading.RuleCheck.RuleCheckDialog import RuleCheckDialog
from UserInterface.EditView.Proofreading.RuleCheck.RuleCheckResultPage import RuleCheckResultPage
from UserInterface.EditView.Proofreading.Search.SearchDialog import SearchDialog
from UserInterface.EditView.Proofreading.Search.SearchResultPage import SearchResultPage
from UserInterface.EditView.Proofreading.Table.TabInterface import TabInterface
from UserInterface.EditView.Proofreading.TerminologyCheck.TerminologyCheckResultPage import TerminologyCheckResultPage
from UserInterface.Widget.Toast import ToastMixin


class ProofreadingPage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    languageCheckFinished = pyqtSignal(tuple)
    terminologyCheckFinished = pyqtSignal(tuple)
    ruleCheckFinished = pyqtSignal(tuple)

    def __init__(self, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("ProofreadingPage")

        self.cache_manager = cache_manager
        self._splitter_ratio_initialized = False
        self._project_file_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("QSplitter::handle { width: 8px; background: transparent; }")

        self.left_panel = QWidget(self)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.nav_card = NavigationCard(self)
        self.nav_card.setBorderRadius(12)
        left_layout.addWidget(self.nav_card, 1)

        self.check_card = CardWidget(self)
        self.check_card.setBorderRadius(12)
        check_layout = QVBoxLayout(self.check_card)
        check_layout.setContentsMargins(14, 14, 14, 14)
        check_layout.setSpacing(10)

        check_title = StrongBodyLabel(self.tra("翻译检查"), self.check_card)
        check_title.setAlignment(Qt.AlignCenter)
        check_layout.addWidget(check_title)

        self.language_check_button = PushButton(FIF.LANGUAGE, self.tra("语言检查"), self.check_card)
        self.language_check_button.setFixedHeight(34)
        self.language_check_button.setMinimumWidth(128)
        check_layout.addWidget(self.language_check_button, 0, Qt.AlignHCenter)

        self.terminology_check_button = PushButton(FIF.DICTIONARY, self.tra("术语检查"), self.check_card)
        self.terminology_check_button.setFixedHeight(34)
        self.terminology_check_button.setMinimumWidth(128)
        check_layout.addWidget(self.terminology_check_button, 0, Qt.AlignHCenter)

        self.rule_check_button = PushButton(FIF.CHECKBOX, self.tra("规则检查"), self.check_card)
        self.rule_check_button.setFixedHeight(34)
        self.rule_check_button.setMinimumWidth(128)
        check_layout.addWidget(self.rule_check_button, 0, Qt.AlignHCenter)

        left_layout.addWidget(self.check_card)

        self.right_panel = QWidget(self)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.page_card = PageCard(self)
        self.page_card.setBorderRadius(12)
        right_layout.addWidget(self.page_card, 1)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 9)
        layout.addWidget(self.splitter, 1)

        self.nav_card.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.page_card.tab_bar.currentChanged.connect(self.on_tab_changed)
        self.page_card.tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)
        self.nav_card.search_button.clicked.connect(self._open_search_dialog)
        self.language_check_button.clicked.connect(self._open_language_check_dialog)
        self.terminology_check_button.clicked.connect(self._start_terminology_check)
        self.rule_check_button.clicked.connect(self._open_rule_check_dialog)
        self.languageCheckFinished.connect(self._on_language_check_finished)
        self.terminologyCheckFinished.connect(self._on_terminology_check_finished)
        self.ruleCheckFinished.connect(self._on_rule_check_finished)
        self._update_action_state()

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
        self._update_action_state()

    def clear_tabs(self) -> None:
        while self.page_card.tab_bar.count() > 0:
            self.on_tab_close_requested(self.page_card.tab_bar.count() - 1)
        self._update_action_state()

    def on_tree_item_clicked(self, item, column) -> None:
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return

        for index in range(self.page_card.stacked_widget.count()):
            widget = self.page_card.stacked_widget.widget(index)
            if widget and widget.objectName() == file_path:
                self.page_card.tab_bar.setCurrentIndex(index)
                self.page_card.stacked_widget.setCurrentIndex(index)
                return

        cache_file = self.cache_manager.project.get_file(file_path)
        if not cache_file:
            self._show_single_button_message(
                self.tra("错误"),
                self.tra("无法从缓存中加载文件: {}").format(file_path),
            )
            return

        tab_name = os.path.basename(file_path)
        new_tab = TabInterface(tab_name, file_path, cache_file.items, self.cache_manager, self)

        self.page_card.stacked_widget.addWidget(new_tab)
        self.page_card.tab_bar.addTab(file_path, tab_name)

        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentWidget(new_tab)

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

    def _update_action_state(self) -> None:
        has_project_files = self._project_file_count > 0
        self.nav_card.search_button.setEnabled(has_project_files)
        self.language_check_button.setEnabled(has_project_files)
        self.terminology_check_button.setEnabled(has_project_files)
        self.rule_check_button.setEnabled(has_project_files)

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

    def _open_rule_check_dialog(self) -> None:
        dialog = RuleCheckDialog(self.window())
        if dialog.exec():
            self.perform_rule_check(dialog.check_params)

    def _start_terminology_check(self) -> None:
        self.perform_terminology_check({})

    def perform_search(self, params: dict) -> None:
        query = params["query"]
        scope = params["scope"]
        is_regex = params["is_regex"]
        search_flagged = params["search_flagged"]

        self.info(f"正在搜索: '{query}' (范围: {scope}, 正则: {is_regex}, 标记行: {search_flagged})")

        results = self.cache_manager.search_items(query, scope, is_regex, search_flagged)
        if not results:
            self._show_single_button_message(
                self.tra("未找到结果"),
                self.tra("未能找到与 '{}' 匹配的内容。").format(query),
            )
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
        self.info("开始执行语言检查任务。")
        thread = threading.Thread(target=self._language_check_worker, args=(params,), daemon=True)
        thread.start()

    def perform_rule_check(self, params: dict) -> None:
        self.info("开始执行规则检查任务。")
        thread = threading.Thread(target=self._rule_check_worker, args=(params,), daemon=True)
        thread.start()

    def perform_terminology_check(self, params: dict) -> None:
        self.info("开始执行术语检查任务。")
        thread = threading.Thread(target=self._terminology_check_worker, args=(params,), daemon=True)
        thread.start()

    def _language_check_worker(self, params: dict) -> None:
        checker = LanguageChecker(self.cache_manager)
        result_code, data = checker.run_check(params)
        self.languageCheckFinished.emit((result_code, data))

    def _rule_check_worker(self, params: dict) -> None:
        checker = RuleChecker(self.cache_manager)
        result_code, data = checker.run_check(params)
        self.ruleCheckFinished.emit((result_code, data))

    def _terminology_check_worker(self, params: dict) -> None:
        checker = TerminologyChecker(self.cache_manager)
        result_code, data = checker.run_check(params)
        self.terminologyCheckFinished.emit((result_code, data))

    def _on_language_check_finished(self, result: tuple) -> None:
        result_code, data = result
        if result_code == CheckResult.SUCCESS_LANGUAGE_RESULT:
            self._show_language_result_page(data)
            return

        title = self.tra("语言检查")
        if result_code == CheckResult.ERROR_CACHE:
            content = self.tra("检查失败，请检查项目文件夹缓存是否正常")
        elif result_code == CheckResult.ERROR_NO_TRANSLATION:
            content = self.tra("检查失败，请先执行翻译流程")
        elif result_code == CheckResult.ERROR_INVALID_LANG:
            content = self.tra("无法识别目标语言配置: {}").format(data.get("lang_name", "N/A"))
        else:
            content = str(data or "")

        self._show_single_button_message(title, content)

    def _on_rule_check_finished(self, result: tuple) -> None:
        result_code, data = result
        if result_code == CheckResult.SUCCESS_RULE_RESULT:
            self._show_rule_result_page(data)
            return

        title = self.tra("规则检查")
        if result_code == CheckResult.ERROR_CACHE:
            content = self.tra("检查失败，请检查项目文件夹缓存是否正常")
        elif result_code == CheckResult.ERROR_NO_TRANSLATION:
            content = self.tra("检查失败，请先执行翻译流程")
        else:
            content = str(data or "")

        self._show_single_button_message(title, content)

    def _on_terminology_check_finished(self, result: tuple) -> None:
        result_code, data = result
        if result_code == CheckResult.SUCCESS_TERMINOLOGY_RESULT:
            self._show_terminology_result_page(data)
            return

        title = self.tra("术语检查")
        if result_code == CheckResult.ERROR_CACHE:
            content = self.tra("检查失败，请检查项目文件夹缓存是否正常")
        elif result_code == CheckResult.ERROR_NO_TRANSLATION:
            content = self.tra("检查失败，请先执行翻译流程")
        else:
            content = str(data or "")

        self._show_single_button_message(title, content)

    def _show_language_result_page(self, result_data: dict) -> None:
        page = LanguageCheckResultPage(result_data, self.cache_manager, self)
        self._replace_result_tab(self.tra("语言检查结果"), f"language_check_{int(time.time())}", page)

    def _show_rule_result_page(self, result_data: dict) -> None:
        page = RuleCheckResultPage(result_data, self.cache_manager, self)
        self._replace_result_tab(self.tra("规则检查结果"), f"rule_check_{int(time.time())}", page)

    def _show_terminology_result_page(self, result_data: dict) -> None:
        page = TerminologyCheckResultPage(result_data, self.cache_manager, self)
        self._replace_result_tab(self.tra("术语检查结果"), f"terminology_check_{int(time.time())}", page)

    def _replace_result_tab(self, tab_name: str, route_key: str, widget: QWidget) -> None:
        for index in reversed(range(self.page_card.tab_bar.count())):
            if self.page_card.tab_bar.tabText(index) != tab_name:
                continue

            old_widget = self.page_card.stacked_widget.widget(index)
            if old_widget:
                self.page_card.stacked_widget.removeWidget(old_widget)
                old_widget.close()
                old_widget.deleteLater()
            self.page_card.tab_bar.removeTab(index)

        widget.setObjectName(route_key)
        self.page_card.stacked_widget.addWidget(widget)
        self.page_card.tab_bar.addTab(routeKey=route_key, text=tab_name)

        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentIndex(new_index)

    def _show_single_button_message(self, title: str, content: str) -> None:
        msg_box = MessageBox(title, content, self.window())
        msg_box.yesButton.setText(self.tra("确认"))
        msg_box.cancelButton.hide()
        msg_box.exec()
