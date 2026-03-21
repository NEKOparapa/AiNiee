import os
import re
import shutil
import threading
from datetime import datetime
from PyQt5.QtWidgets import QLayout, QVBoxLayout, QWidget
from qfluentwidgets import pyqtSignal, StateToolTip

from ModuleFolders.Base.Base import Base
from UserInterface.EditView.Startup.FolderDropCard import FolderDropCard
from UserInterface.EditView.Startup.ProjectHistoryCard import ProjectHistoryCard
from UserInterface.Widget.ComboBoxCard import ComboBoxCard


def _generate_project_subfolder_name(project_name: str) -> str:
    """根据项目名称生成文件系统安全的子文件夹名"""
    sanitized = re.sub(r'[\\/:*?"<>|\x00]', '_', project_name)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_ ')
    sanitized = sanitized[:80].rstrip('_ ')
    if not sanitized:
        sanitized = "Project"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{sanitized}_{timestamp}"


class StartupPage(Base, QWidget):
    """开始页面"""
    folderSelected = pyqtSignal(str, str)  # 信号：通知主界面文件夹已选好，切换页面
    loadSuccess = pyqtSignal(str, str, str) # 信号(子线程->主线程)：项目加载成功
    loadFailed = pyqtSignal(str)           # 信号(子线程->主线程)：项目加载失败

    def __init__(self, support_project_types=None, parent=None, cache_manager=None, file_reader=None):
        super().__init__(parent)
        self.support_project_types = support_project_types
        self.cache_manager = cache_manager
        self.file_reader = file_reader
        self.stateTooltip = None  # 用于显示状态提示
        self._pending_output_path = None  # 继续历史项目时暂存的 output_path

        # 连接子线程信号到主线程的槽函数
        self.loadSuccess.connect(self._on_load_success)
        self.loadFailed.connect(self._on_load_failed)

        # 默认配置
        self.default = {
            "translation_project": "AutoType",
            "label_input_path": "./input",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        # 添加组件
        self.add_widget_projecttype(self.container, config)
        self.add_widget_folder_drop(self.container, config)

        # 历史项目列表容器（动态填充）
        self.history_container = QVBoxLayout()
        self.history_container.setSpacing(4)
        self.container.addLayout(self.history_container)

        # 添加弹簧
        self.container.addStretch(1)

    def show_project_history(self, entries: list) -> None:
        """清空并重建历史项目列表（在主线程调用）"""
        # 清空旧卡片
        while self.history_container.count():
            item = self.history_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 逐条创建卡片
        for entry in entries:
            card = ProjectHistoryCard(entry, parent=self)
            output_path = entry.get("output_path", "")
            card.continue_clicked.connect(
                lambda checked=False, op=output_path: self.folder_path_changed("continue", op)
            )
            card.delete_clicked.connect(
                lambda checked=False, op=output_path, c=card: self._delete_history_entry(op, c)
            )
            self.history_container.addWidget(card)

    def add_widget_projecttype(self, parent, config) -> None:
        """项目类型"""
        translated_pairs = [(self.tra(project_type), project_type) for project_type in self.support_project_types]

        def init(widget) -> None:
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "AutoType")
            index = next((i for i, (_, value) in enumerate(translated_pairs) if value == current_value), 0)
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            value = next((value for display, value in translated_pairs if display == text), "AutoType")
            config = self.load_config()
            config["translation_project"] = value
            self.save_config(config)

        options = [display for display, value in translated_pairs]
        parent.addWidget(
            ComboBoxCard(
                self.tra("项目类型"),
                self.tra("设置当前翻译项目所使用的原始文本的格式，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    def add_widget_folder_drop(self, parent: QLayout, config: dict) -> None:
        """输入文件夹"""
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

    def folder_path_changed(self, mode: str, output_path: str = None) -> None:
        """
        [主线程] 用户点击按钮或输入文件夹后调用此方法。
        output_path: 继续历史项目时传入对应的 output 路径，None 则使用配置中的路径。
        """
        self._pending_output_path = output_path

        # 显示加载提示
        if self.stateTooltip:
            self.stateTooltip.close()

        self.stateTooltip = StateToolTip(self.tra('正在加载项目...'), self.tra('客官请耐心等待哦~~'), self.window())
        x = self.window().width() // 2 - self.stateTooltip.width() // 2
        y = 32
        self.stateTooltip.move(x, y)
        self.stateTooltip.show()

        # 禁用输入控件，防止重复操作
        self.drag_card.setEnabled(False)
        self._set_history_cards_enabled(False)

        # 在子线程中执行加载任务
        loader_thread = threading.Thread(target=self._load_project_worker, args=(mode,), daemon=True)
        loader_thread.start()

    def _set_history_cards_enabled(self, enabled: bool) -> None:
        """启用或禁用所有历史项目卡片"""
        for i in range(self.history_container.count()):
            item = self.history_container.itemAt(i)
            if item and item.widget():
                item.widget().setEnabled(enabled)

    def _load_project_worker(self, mode: str) -> None:
        """
        [子线程] 执行实际的文件读取和缓存加载工作。
        完成后通过信号通知主线程结果。
        """
        try:
            config = self.load_config()
            translation_project = config.get("translation_project", "AutoType")
            label_input_path = config.get("label_input_path", "./input")
            label_input_exclude_rule = config.get("label_input_exclude_rule", "")

            # 若继续历史项目，先将 output_path 更新到 config
            if self._pending_output_path:
                config["label_output_path"] = self._pending_output_path
                self.save_config(config)
            label_output_path = config.get("label_output_path", "./output")

            if mode == "new":
                CacheProject = self.file_reader.read_files(
                    translation_project,
                    label_input_path,
                    label_input_exclude_rule
                )
                self.cache_manager.load_from_project(CacheProject)

                # 为新项目创建独立子文件夹，避免覆盖之前项目的缓存
                auto_set = config.get("auto_set_output_path", True)
                if auto_set:
                    abs_input = os.path.abspath(label_input_path)
                    base_output_path = os.path.join(os.path.dirname(abs_input), "AiNieeOutput")
                else:
                    base_output_path = label_output_path

                subfolder = _generate_project_subfolder_name(CacheProject.project_name)
                project_output_path = os.path.join(base_output_path, subfolder)

                config["label_output_path"] = project_output_path
                self.save_config(config)
            else:  # "continue"
                self.cache_manager.load_from_file(label_output_path)

            if self.cache_manager.get_item_count() == 0:
                raise ValueError("项目数据为空，可能是项目类型或输入文件夹设置不正确。")

            project_name = self.cache_manager.project.project_name
            final_output_path = config.get("label_output_path", label_output_path)
            self.loadSuccess.emit(project_name, mode, final_output_path)

        except Exception as e:
            error_message = "翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ..."
            self.error(error_message, e)
            self.loadFailed.emit(error_message)

    def _on_load_success(self, project_name: str, project_mode: str, output_path: str) -> None:
        """
        [主线程] 接收加载成功信号后的处理函数。
        """
        # 更新UI提示为成功状态
        if self.stateTooltip:
            info = self.tra('项目加载成功！') + '🚀'
            self.stateTooltip.setContent(self.tra(info))
            self.stateTooltip.setState(True)
            self.stateTooltip = None

        # 重新启用控件
        self.drag_card.setEnabled(True)
        self._set_history_cards_enabled(True)

        # 更新项目历史
        self._save_to_history(self.load_config(), project_name, output_path)
        self._pending_output_path = None

        # 打印文件信息到控制台
        self.print("")
        self.info(f"项目数据全部载入成功 ...")
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

        # 发送最终信号，通知主界面切换页面
        self.folderSelected.emit(project_name, project_mode)

    def _on_load_failed(self, error_message: str) -> None:
        """
        [主线程] 接收加载失败信号后的处理函数。
        """
        if self.stateTooltip:
            info = self.tra('加载失败...') + '😵'
            self.stateTooltip.setContent(self.tra(info))
            self.stateTooltip.setState(False)
            self.stateTooltip = None

        # 重新启用控件
        self.drag_card.setEnabled(True)
        self._set_history_cards_enabled(True)
        self._pending_output_path = None

        self.error_toast(self.tra("错误"), error_message)

    def _delete_history_entry(self, output_path: str, card) -> None:
        """从历史记录中删除指定项目，移除 UI 卡片，并在后台线程删除磁盘上的输出子目录"""
        config = self.load_config()
        history = [h for h in config.get("project_history", []) if h.get("output_path") != output_path]
        config["project_history"] = history
        self.save_config(config)

        if output_path:
            threading.Thread(target=self._delete_directory_worker, args=(output_path,), daemon=True).start()

        self.history_container.removeWidget(card)
        card.deleteLater()

    def _delete_directory_worker(self, output_path: str) -> None:
        """[子线程] 删除磁盘上的输出目录"""
        try:
            shutil.rmtree(output_path)
        except FileNotFoundError:
            pass
        except Exception as e:
            self.error(f"删除输出目录失败: {output_path}", e)

    def _save_to_history(self, config: dict, project_name: str, output_path: str) -> None:
        """将项目记录写入 project_history，按 output_path 去重，最多保留 20 条"""
        history = config.get("project_history", [])
        history = [h for h in history if h.get("output_path") != output_path]
        history.insert(0, {
            "project_name": project_name,
            "output_path": output_path,
            "last_accessed": datetime.now().isoformat(timespec="seconds"),
        })
        config["project_history"] = history[:20]
        self.save_config(config)
