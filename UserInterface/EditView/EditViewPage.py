import json
import os
import threading
import time

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout
from qfluentwidgets import (
    CardWidget,
    FluentIcon as FIF,
    SegmentedWidget,
    TransparentPushButton,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from UserInterface.EditView.Analysis.AnalysisPage import AnalysisPage
from UserInterface.EditView.Proofreading.ProofreadingPage import ProofreadingPage
from UserInterface.EditView.Startup.StartupPage import StartupPage
from UserInterface.EditView.Translation.TranslationPage import TranslationPage
from UserInterface.Widget.Toast import ToastMixin


class WorkflowHeaderBar(ConfigMixin, CardWidget):
    backRequested = pyqtSignal()
    saveRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    stepChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self.back_button = TransparentPushButton(FIF.RETURN, self.tra("返回"), self)
        self.save_button = TransparentPushButton(FIF.SAVE, self.tra("缓存"), self)
        self.export_button = TransparentPushButton(FIF.SHARE, self.tra("导出结果"), self)
        self.step_widget = SegmentedWidget(self)
        self.step_widget.setFixedWidth(380)
        step_height = 38
        self.step_widget.setFixedHeight(step_height)

        for route_key, text in (
            ("analysis", self.tra("分析")),
            ("translation", self.tra("翻译")),
            ("proofreading", self.tra("校对")),
        ):
            step_item = self.step_widget.addItem(
                routeKey=route_key,
                text=text,
                onClick=lambda checked=False, key=route_key: self.stepChanged.emit(key),
            )
            step_item.setFixedHeight(step_height)

        self.back_button.clicked.connect(self.backRequested.emit)
        self.save_button.clicked.connect(self.saveRequested.emit)
        self.export_button.clicked.connect(self.exportRequested.emit)

        layout.addWidget(self.back_button)
        layout.addStretch(1)
        layout.addWidget(self.step_widget, 0, Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(self.save_button)
        layout.addWidget(self.export_button)

    def set_current_step(self, route_key: str) -> None:
        if route_key:
            self.step_widget.setCurrentItem(route_key)


class EditViewPage(ConfigMixin, LogMixin, ToastMixin, Base, QFrame):
    continueCardStateChanged = pyqtSignal(bool, str)
    resumableStateChanged = pyqtSignal(bool)

    ROUTE_ANALYSIS = "analysis"
    ROUTE_TRANSLATION = "translation"
    ROUTE_PROOFREADING = "proofreading"

    def __init__(self, text: str, window, cache_manager, file_reader) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.cache_manager = cache_manager
        self.file_reader = file_reader
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.top_stacked_widget = QStackedWidget(self)
        main_layout.addWidget(self.top_stacked_widget)

        support_project_types = self.file_reader.get_support_project_types()
        self.startup_page = StartupPage(
            support_project_types=support_project_types,
            parent=window,
            cache_manager=cache_manager,
            file_reader=file_reader,
        )

        self.workflow_container = QFrame(self)
        workflow_layout = QVBoxLayout(self.workflow_container)
        workflow_layout.setContentsMargins(0, 0, 0, 0)
        workflow_layout.setSpacing(0)

        self.workflow_header = WorkflowHeaderBar(self.workflow_container)
        self.workflow_stacked_widget = QStackedWidget(self.workflow_container)

        self.analysis_page = AnalysisPage(cache_manager, self.workflow_stacked_widget)
        self.translation_page = TranslationPage(self.workflow_stacked_widget)
        self.proofreading_page = ProofreadingPage(cache_manager, self.workflow_stacked_widget)

        self.route_to_widget = {
            self.ROUTE_ANALYSIS: self.analysis_page,
            self.ROUTE_TRANSLATION: self.translation_page,
            self.ROUTE_PROOFREADING: self.proofreading_page,
        }

        for widget in self.route_to_widget.values():
            self.workflow_stacked_widget.addWidget(widget)

        workflow_layout.addWidget(self.workflow_header)
        workflow_layout.addWidget(self.workflow_stacked_widget)

        self.top_stacked_widget.addWidget(self.startup_page)
        self.top_stacked_widget.addWidget(self.workflow_container)
        self.top_stacked_widget.setCurrentWidget(self.startup_page)

        self.workflow_header.set_current_step(self.ROUTE_ANALYSIS)
        self.workflow_stacked_widget.setCurrentWidget(self.analysis_page)

        self.startup_page.folderSelected.connect(self.on_folder_selected)
        self.workflow_header.backRequested.connect(self.on_back_button_clicked)
        self.workflow_header.saveRequested.connect(self.command_save_cache)
        self.workflow_header.exportRequested.connect(self.command_export)
        self.workflow_header.stepChanged.connect(self.switch_workflow_page)
        self.continueCardStateChanged.connect(self._on_continue_card_state_changed)
        self.resumableStateChanged.connect(self.translation_page.enable_continue_button)

        self.subscribe(Base.EVENT.TASK_CONTINUE_CHECK, self.task_continue_check)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.task_continue_check(event=None, data=None)

    def switch_workflow_page(self, route_key: str) -> None:
        widget = self.route_to_widget.get(route_key)
        if widget is None:
            return

        self.workflow_header.set_current_step(route_key)
        self.workflow_stacked_widget.setCurrentWidget(widget)

    def task_continue_check(self, event: int, data: dict) -> None:
        threading.Thread(target=self.task_continue_check_target, daemon=True).start()

    def task_continue_check_target(self) -> None:
        time.sleep(0.5)
        continue_visible = False
        continue_enabled = False
        project_name = ""

        if Base.work_status == Base.STATUS.IDLE:
            config = self.load_config()
            cache_folder_path = os.path.join(config.get("label_output_path", "./output"), "cache")

            if os.path.isdir(cache_folder_path):
                json_file_path = os.path.join(cache_folder_path, "ProjectStatistics.json")

                if os.path.isfile(json_file_path):
                    max_retries = 3
                    retry_delay = 0.1

                    for attempt in range(max_retries):
                        try:
                            if os.path.getsize(json_file_path) == 0:
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay)
                                    continue
                                print("[WARNING] ProjectStatistics.json文件为空，跳过继续检查")
                                break

                            with open(json_file_path, "r", encoding="utf-8") as file:
                                content = file.read().strip()

                            if not content:
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay)
                                    continue
                                print("[WARNING] ProjectStatistics.json内容为空")
                                break

                            data = json.loads(content)
                            total_line = data.get("total_line", 0)
                            line = data.get("line", 0)
                            project_name = data.get("project_name", "")

                            if total_line:
                                continue_visible = True
                                continue_enabled = line < total_line

                            break
                        except (json.JSONDecodeError, OSError, IOError) as e:
                            if attempt < max_retries - 1:
                                print(f"[WARNING] 读取ProjectStatistics.json失败(尝试{attempt + 1}/{max_retries}): {e}")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            print(f"[ERROR] 读取ProjectStatistics.json最终失败: {e}")
                        except Exception as e:
                            print(f"[ERROR] 读取ProjectStatistics.json时发生未知错误: {e}")
                            break

        self.continueCardStateChanged.emit(continue_visible, project_name)
        self.resumableStateChanged.emit(continue_enabled)

    def _on_continue_card_state_changed(self, show: bool, project_name: str) -> None:
        self.startup_page.show_continue_button(show)
        if show:
            self.startup_page.continue_card.set_project_name(project_name)
        else:
            self.startup_page.continue_card.hide_project_name()

    def on_folder_selected(self, project_name: str, project_mode: str) -> None:
        file_hierarchy = self.cache_manager.get_file_hierarchy()

        self.proofreading_page.clear_tabs()
        self.proofreading_page.update_tree(file_hierarchy)
        self.analysis_page.refresh_from_project()

        if project_mode == "new":
            self.translation_page.enable_continue_button(False)
        else:
            self.translation_page.enable_continue_button(True)

        self.top_stacked_widget.setCurrentWidget(self.workflow_container)
        self.switch_workflow_page(self.ROUTE_ANALYSIS)

    def on_back_button_clicked(self) -> None:
        if Base.work_status == Base.STATUS.IDLE:
            self.top_stacked_widget.setCurrentWidget(self.startup_page)

    def command_export(self) -> None:
        selected_path = QFileDialog.getExistingDirectory(
            self.window(),
            self.tra("选择导出目录"),
            ".",
        )
        if selected_path:
            self.emit(Base.EVENT.TASK_MANUAL_EXPORT, {"export_path": selected_path})

    def command_save_cache(self) -> None:
        config = self.load_config()
        output_path = config.get("label_output_path")

        if not output_path:
            self.error_toast(self.tra("错误"), self.tra("当前没有可保存的项目输出路径。"))
            return

        try:
            cache_dir = os.path.join(output_path, "cache")
            if not os.path.isdir(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
        except OSError as e:
            self.error_toast(self.tra("路径错误"), self.tra("创建缓存目录失败: {}").format(e))
            return

        self.emit(Base.EVENT.TASK_MANUAL_SAVE_CACHE, {"output_path": output_path})
        self.success_toast(self.tra("成功"), self.tra("项目缓存文件已保存到翻译输出文件夹"))
