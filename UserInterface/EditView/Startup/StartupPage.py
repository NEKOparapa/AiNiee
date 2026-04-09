import threading

from PyQt5.QtWidgets import QLayout, QVBoxLayout, QWidget
from qfluentwidgets import MessageBox, StateToolTip, pyqtSignal

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from UserInterface.EditView.Startup.FolderDropCard import FolderDropCard
from UserInterface.EditView.Startup.ProjectHistoryCard import ProjectHistoryCard
from UserInterface.Widget.ComboBoxCard import ComboBoxCard
from UserInterface.Widget.Toast import ToastMixin


class StartupPage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    """启动页。"""

    folderSelected = pyqtSignal(str, str)
    loadSuccess = pyqtSignal(str, str)
    loadFailed = pyqtSignal(str)
    historiesLoaded = pyqtSignal(object, int)

    def __init__(self, support_project_types=None, parent=None, cache_manager=None, file_reader=None):
        super().__init__(parent)
        self.support_project_types = support_project_types
        self.cache_manager = cache_manager
        self.file_reader = file_reader
        self.stateTooltip = None
        self.latest_project_id = ""
        self.history_cards = []
        self.history_refresh_token = 0

        self.loadSuccess.connect(self._on_load_success)
        self.loadFailed.connect(self._on_load_failed)
        self.historiesLoaded.connect(self._on_histories_loaded)

        self.default = {
            "translation_project": "AutoType",
            "label_input_path": "./input",
        }

        config = self.save_config(self.load_config_from_default())

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_projecttype(self.container, config)
        self.add_widget_folder_drop(self.container, config)

        self.history_layout = QVBoxLayout()
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(8)
        self.container.addLayout(self.history_layout)

        self.container.addStretch(1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_project_histories()

    def show_continue_button(self, show: bool) -> None:
        # 启动页仅显示 ProjectHistoryCard 历史列表，不再显示额外继续卡片。
        return

    def add_widget_projecttype(self, parent, config) -> None:
        translated_pairs = [(self.tra(project_type), project_type) for project_type in self.support_project_types]

        def init(widget) -> None:
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "AutoType")
            index = next((i for i, (_, value) in enumerate(translated_pairs) if value == current_value), 0)
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            value = next((value for display, value in translated_pairs if display == text), "AutoType")
            current_config = self.load_config()
            current_config["translation_project"] = value
            self.save_config(current_config)

        options = [display for display, _ in translated_pairs]
        parent.addWidget(
            ComboBoxCard(
                self.tra("项目类型"),
                self.tra("设置当前翻译项目所使用的原始文本格式，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed,
            )
        )

    def add_widget_folder_drop(self, parent: QLayout, config: dict) -> None:
        def widget_callback(path: str) -> None:
            current_config = self.load_config()
            current_config["label_input_path"] = path.strip()
            self.save_config(current_config)
            self.folder_path_changed("new")

        initial_path = config.get("label_input_path", "./input")
        self.drag_card = FolderDropCard(
            init=initial_path,
            path_changed=widget_callback,
        )
        parent.addWidget(self.drag_card)

    def refresh_project_histories(self) -> None:
        self.history_refresh_token += 1
        refresh_token = self.history_refresh_token

        threading.Thread(
            target=self._refresh_project_histories_worker,
            args=(refresh_token,),
            daemon=True,
        ).start()

    def _refresh_project_histories_worker(self, refresh_token: int) -> None:
        histories = []
        try:
            if self.cache_manager:
                histories = self.cache_manager.list_project_histories(
                    limit=self.cache_manager.HISTORY_LIMIT,
                    prune=True,
                )
        except Exception as error:
            self.error("读取项目缓存历史失败", error)

        self.historiesLoaded.emit(histories, refresh_token)

    def _on_histories_loaded(self, histories, refresh_token: int) -> None:
        if refresh_token != self.history_refresh_token:
            return

        self._clear_history_cards()
        self.latest_project_id = histories[0].get("project_id", "") if histories else ""

        for history in histories:
            history_card = ProjectHistoryCard(history, self)
            history_card.continue_clicked.connect(self._on_history_continue_requested)
            history_card.delete_clicked.connect(self._on_history_delete_requested)
            self.history_layout.addWidget(history_card)
            self.history_cards.append(history_card)

    def _clear_history_cards(self) -> None:
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.history_cards.clear()

    def _on_history_continue_requested(self, project_id: str) -> None:
        if project_id:
            self.folder_path_changed("continue", project_id)

    def _on_history_delete_requested(self, project_id: str) -> None:
        if not project_id:
            return

        message_box = MessageBox(
            self.tra("确认"),
            self.tra("是否确认删除该项目缓存？删除后无法恢复。"),
            self.window(),
        )
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        try:
            deleted = self.cache_manager.delete_project_cache(project_id)
            if deleted:
                self.refresh_project_histories()
                self.emit(Base.EVENT.TASK_CONTINUE_CHECK, {})
                self.success_toast(self.tra("成功"), self.tra("项目缓存已删除"))
        except Exception as error:
            self.error("删除项目缓存失败", error)
            self.error_toast(self.tra("错误"), self.tra("删除项目缓存失败"))

    def _set_history_controls_enabled(self, enabled: bool) -> None:
        self.drag_card.setEnabled(enabled)
        for history_card in self.history_cards:
            history_card.setEnabled(enabled)

    def folder_path_changed(self, mode: str, project_id: str = "") -> None:
        if self.stateTooltip:
            self.stateTooltip.close()

        self.stateTooltip = StateToolTip(
            self.tra("正在加载项目..."),
            self.tra("请耐心等待"),
            self.window(),
        )
        x = self.window().width() // 2 - self.stateTooltip.width() // 2
        y = 32
        self.stateTooltip.move(x, y)
        self.stateTooltip.show()

        self._set_history_controls_enabled(False)

        loader_thread = threading.Thread(
            target=self._load_project_worker,
            args=(mode, project_id),
            daemon=True,
        )
        loader_thread.start()

    def _load_project_worker(self, mode: str, project_id: str = "") -> None:
        try:
            config = self.load_config()
            translation_project = config.get("translation_project", "AutoType")
            label_input_path = config.get("label_input_path", "./input")
            label_input_exclude_rule = config.get("label_input_exclude_rule", "")

            if mode == "new":
                cache_project = self.file_reader.read_files(
                    translation_project,
                    label_input_path,
                    label_input_exclude_rule,
                )
                self.cache_manager.load_from_project(cache_project)
                self.cache_manager.save_to_file()
            elif project_id:
                self.cache_manager.load_from_project_id(project_id)
            else:
                self.cache_manager.load_from_file()

            if mode != "new" and self.cache_manager.project:
                current_config = dict(config)
                if self.cache_manager.project.input_path:
                    current_config["label_input_path"] = self.cache_manager.project.input_path
                if current_config != config:
                    self.save_config(current_config)

            if self.cache_manager.get_item_count() == 0:
                raise ValueError("项目数据为空，可能是项目类型或输入文件夹设置不正确。")

            project_name = self.cache_manager.project.project_name
            self.loadSuccess.emit(project_name, mode)
        except Exception as error:
            error_message = "翻译项目数据载入失败，请检查项目类型与输入文件夹设置。"
            self.error(error_message, error)
            self.loadFailed.emit(error_message)

    def _on_load_success(self, project_name: str, project_mode: str) -> None:
        if self.stateTooltip:
            self.stateTooltip.setContent(self.tra("项目加载成功"))
            self.stateTooltip.setState(True)
            self.stateTooltip = None

        self._set_history_controls_enabled(True)
        self.refresh_project_histories()

        self.print("")
        self.info("项目数据全部载入成功 ...")
        for _, file in self.cache_manager.project.files.items():
            language_stats = file.language_stats
            storage_path = file.storage_path
            encoding = file.encoding
            file_project_type = file.file_project_type

            self.print("")
            self.info(f"已经载入文件 - {storage_path}")
            self.info(f"文件类型 - {file_project_type}")
            self.info(f"文件编码 - {encoding}")
            self.info(f"语言统计 - {language_stats}")
        self.print("")

        self.folderSelected.emit(project_name, project_mode)

    def _on_load_failed(self, error_message: str) -> None:
        if self.stateTooltip:
            self.stateTooltip.setContent(self.tra("加载失败"))
            self.stateTooltip.setState(False)
            self.stateTooltip = None

        self._set_history_controls_enabled(True)
        self.refresh_project_histories()
        self.error_toast(self.tra("错误"), error_message)
