from typing import List
import re

from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout

import httpx

from qfluentwidgets import (
    MessageBoxBase, LineEdit, PushButton, StrongBodyLabel, FluentIcon,
    PillPushButton, SingleDirectionScrollArea, isDarkTheme, IndeterminateProgressRing,
)

from Base.Base import Base
from ModuleFolders.LLMRequester.LLMClientFactory import LLMClientFactory

class _GoogleModelFetchWorker(QObject):
    """用于从 google-genai 获取模型的工作线程"""
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, platform_config: dict):
        super().__init__()
        self.platform_config = platform_config
        self._aborted = False

    def cancel(self):
        self._aborted = True

    def run(self):
        if self._aborted:
            return
        try:
            # 使用 LLMClientFactory 获取 Google 客户端
            client = LLMClientFactory().get_google_client(self.platform_config)

            # 获取所有可用模型
            all_models_iterator = client.models.list()

            if self._aborted:
                return

            filtered_models = []
            exclude_keywords = ["native-audio", "image", "tts", "live"]

            # 遍历并按要求过滤模型
            for model in all_models_iterator:
                model_name = model.name

                # 保留 gemini 和 gemma 模型
                if 'gemini' in model_name or 'gemma' in model_name:
                    # 排除特定类型的模型
                    if not any(keyword in model_name for keyword in exclude_keywords):
                        short_name = model_name.split('/')[-1]
                        filtered_models.append(short_name)

            if not self._aborted:
                self.finished.emit(filtered_models)

        except Exception as e:
            if not self._aborted:
                self.failed.emit(str(e))
            return

class _ModelFetchWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, url: str, headers: dict):
        super().__init__()
        self.url = url
        self.headers = headers
        self._aborted = False

    def cancel(self):
        self._aborted = True

    def run(self):
        if self._aborted:
            return
        try:
            with httpx.Client(http2=True, timeout=10.0) as client:
                resp = client.get(self.url, headers=self.headers, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            if not self._aborted:
                self.failed.emit(str(e))
            return

        if self._aborted:
            return

        models = []
        try:
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                for item in data.get("data", []):
                    mid = item.get("id") or item.get("model")
                    if mid:
                        models.append(str(mid))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        models.append(item)
                    elif isinstance(item, dict):
                        mid = item.get("id") or item.get("model")
                        if mid:
                            models.append(str(mid))
        except Exception:
            pass

        if not self._aborted:
            self.finished.emit(models)



class ModelBrowserDialog(MessageBoxBase, Base):
    """
    统一的“获取模型”对话框：
    - 支持从 OpenAI 兼容接口 GET /v1/models 拉取全部模型
    - 支持从 google-genai 原生接口拉取模型
    - 本地分页与搜索（适配几百条模型的展示）
    - 单/多选：按住 Ctrl/Shift 可多选；双击单条将立即确认
    """
    # 确认时把最终选择通过信号抛出，避免外部读取竞态
    selectedConfirmed = pyqtSignal(list)

    def __init__(self, window, platform_key: str, platform_config: dict):
        super().__init__(parent=window)
        self.platform_key = platform_key
        self.platform_config = platform_config

        # UI 基本设置

        # 关闭/销毁保护标志
        self._closing = False

        self.widget.setMinimumSize(720, 520)
        self.yesButton.setText(self.tra("确定"))
        self.cancelButton.setText(self.tra("取消"))
        self.yesButton.setEnabled(False)

        # 数据
        self._all_models: List[str] = []
        self._filtered: List[str] = []
        self._page_size = 50
        self._current_page = 1

        # 构建界面
        self._build_ui()

        # 轻度样式优化
        self.setStyleSheet("""
        QListWidget { background: transparent; border: 1px solid rgba(255,255,255,0.08); }
        QListWidget::item { padding: 6px 10px; }
        QListWidget::item:selected { background: rgba(98, 160, 234, 0.18); border: none; }
        QLabel { color: palette(window-text); }
        """)

        # 异步/同步拉取数据（这里用同步 httpx，数据量一般可接受）
        # 容器背景使用主题色；按钮与主题色形成明暗对比，文本固定为 #f1356d
        theme_hex = None
        # 根据主题构造对比用的明暗色（覆盖在主题背景上）
        if isDarkTheme():
            theme_hex = "#2b2b2b"
            btn_bg = "#dddddd"
            btn_border = "rgba(255,255,255,0.28)"
            btn_hover = "rgba(255,255,255,0.22)"
            btn_checked = "rgba(255,255,255,0.30)"
        else:
            theme_hex = "#ffffff"
            btn_bg = "rgba(0,0,0,0.06)"
            btn_border = "rgba(0,0,0,0.18)"
            btn_hover = "rgba(0,0,0,0.10)"
            btn_checked = "rgba(0,0,0,0.16)"



        # 设置模型区域背景为主题色
        # 放在 grid_parent 上，使视觉上“模型展示区域”整体统一
        # 注意：为了有留白，外层布局已有边距
        self.grid_parent.setStyleSheet(f"QWidget {{ background-color: {theme_hex}; border-radius: 8px; }}")

        text_color = "#202020"  # 固定按钮文本色

        # 胶囊按钮样式
        self._capsule_style = (
            "QPushButton {"
            " border-radius: 18px; padding: 8px 14px;"
            f" border: 1px solid {btn_border};"
            f" background-color: {btn_bg};"
            f" color: {text_color};"
            "}"
            "QPushButton:hover {"
            f" background-color: {btn_hover};"
            "}"
            "QPushButton:checked {"
            f" background-color: {btn_checked};"
            f" border: 1px solid {btn_border};"
            f" color: {text_color};"
            "}"
        )

        self._begin_loading_state()
        self._fetch_models()

        # 连接确认按钮，点击时调用 accept（保证加的信号和快照逻辑生效）
        try:
            self.yesButton.clicked.disconnect()
        except Exception:
            pass
        self.yesButton.clicked.connect(self.accept)

    # 公开方法：获取选择的模型
    def get_selected_models(self) -> List[str]:
        # 若已在 accept() 阶段确认，则返回确认时的快照，避免并发导致的空值
        if hasattr(self, "_confirmed_models"):
            return list(self._confirmed_models)
        return list(self._selected)

    # UI
    def _build_ui(self) -> None:
        self.viewLayout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = StrongBodyLabel(self.tra("获取模型"), self)
        self.viewLayout.addWidget(title)

        # 搜索条
        top_bar = QHBoxLayout()
        self.search_box = LineEdit(self)
        self.search_box.setPlaceholderText(self.tra("搜索模型..."))
        self.search_box.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_box, 1)

        # 分页控制
        self.prev_btn = PushButton(self.tra("上一页"), self)
        self.prev_btn.setIcon(FluentIcon.LEFT_ARROW)
        self.prev_btn.clicked.connect(lambda: self._goto_page(self._current_page - 1))
        self.next_btn = PushButton(self.tra("下一页"), self)
        self.next_btn.setIcon(FluentIcon.RIGHT_ARROW)
        self.next_btn.clicked.connect(lambda: self._goto_page(self._current_page + 1))
        self.page_label = QLabel("1/1", self)
        self.page_label.setAlignment(Qt.AlignCenter)

        top_bar.addWidget(self.prev_btn)
        top_bar.addWidget(self.page_label)
        top_bar.addWidget(self.next_btn)
        self.viewLayout.addLayout(top_bar)

        # 模型栅格（滚动区 + Grid）
        self.scroll_area = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.grid_parent = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_parent)
        self.grid_layout.setContentsMargins(8, 8, 18, 8)  # 右侧适当留白，避免贴太近滚动条
        self.grid_layout.setHorizontalSpacing(16)
        self.grid_layout.setVerticalSpacing(12)
        self.scroll_area.setWidget(self.grid_parent)
        self.viewLayout.addWidget(self.scroll_area)

        # 选择集合（跨页保留）
        self._selected = set()

    # 拉取模型（异步）
    def _fetch_models(self) -> None:
        # 判断平台类型
        if self.platform_key == "google":
            self._thread = QThread(self)
            self._worker = _GoogleModelFetchWorker(self.platform_config)
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._on_fetch_finished)
            self._worker.failed.connect(self._on_fetch_failed)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.start()
        else:
            # OpenAI 兼容接口
            base_url = self.platform_config.get("api_url", "").rstrip("/")
            auto_complete = self.platform_config.get("auto_complete", False)

            # 自动补全规则（参考 TranslatorConfig）
            if self.platform_key == "sakura" and not base_url.endswith("/v1"):
                base_url = base_url + "/v1"
            elif auto_complete and not re.search(r"/v[1-9]$", base_url):
                base_url = base_url + "/v1"

            url = f"{base_url}/models"

            # 处理鉴权
            headers = {}
            api_keys = self.platform_config.get("api_key", "").replace(" ", "")
            if api_keys:
                headers["Authorization"] = f"Bearer {api_keys.split(',')[0]}"

            # 启动后台线程
            self._thread = QThread(self)
            self._worker = _ModelFetchWorker(url, headers)
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._on_fetch_finished)
            self._worker.failed.connect(self._on_fetch_failed)
            # 线程结束后清理
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.start()

    # 覆写关闭/拒绝，确保停止后台线程并安全清理
    def reject(self) -> None:
        # 先隐藏，减少重绘竞争
        try:
            self.hide()
        except Exception:
            self.debug("hide failed")
        # 如果线程还在跑，发起取消并等待其结束
        try:
            if hasattr(self, "_worker") and self._worker:
                self._worker.cancel()
            if hasattr(self, "_thread") and self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
        except Exception:
            pass
        super().reject()

    def accept(self) -> None:
        # 确认前先打上关闭标志并停止后台线程，避免竞态重绘
        self._closing = True
        # 在任何隐藏/清理动作前，先拍一份快照并发信号，保证上层拿得到
        try:
            self._confirmed_models = list(self._selected)
            self.selectedConfirmed.emit(self._confirmed_models)
        except Exception:
            pass
        try:
            self.hide()
        except Exception:
            self.debug("hide failed")
        try:
            if hasattr(self, "_worker") and self._worker:
                self._worker.cancel()
            if hasattr(self, "_thread") and self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
        except Exception:
            pass
        # 延迟调用父类 accept，确保本轮绘制结束（用 lambda + 显式 super 调用）
        QTimer.singleShot(0, lambda: super(ModelBrowserDialog, self).accept())
        return

    def closeEvent(self, event):
        try:
            if hasattr(self, "_worker") and self._worker:
                self._worker.cancel()
            if hasattr(self, "_thread") and self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
        except Exception:
            pass
        return super().closeEvent(event)



    def _on_fetch_failed(self, err: str):
        # 异步延迟清理 + 提示，避免与关闭/销毁竞争
        QTimer.singleShot(0, self._end_loading_state)
        QTimer.singleShot(0, lambda: self._show_placeholder(self.tra("获取失败")))
        QTimer.singleShot(0, lambda: self.error_toast(self.tra("获取模型"), self.tra("获取模型失败")))
        self.debug(f"fetch models error: {err}")

    def _on_fetch_finished(self, models: list):
        unique = sorted(list(dict.fromkeys(models)))
        self._all_models = unique
        # 异步延迟刷新，避免与关闭/销毁竞争
        QTimer.singleShot(0, self._apply_filter_and_refresh)
        QTimer.singleShot(0, self._end_loading_state)
        if unique:
            QTimer.singleShot(0, lambda: self.success_toast(self.tra("获取模型"), self.tra("获取成功")))
        else:
            QTimer.singleShot(0, lambda: self.warning_toast(self.tra("获取模型"), self.tra("没有返回任何模型")))

    # 事件
    def _on_search_changed(self, text: str) -> None:
        self._apply_filter_and_refresh()

    def _on_selection_change(self) -> None:
        # grid 方案改为使用内部集合控制按钮状态
        self.yesButton.setEnabled(len(self._selected) > 0)
    # 占位/加载提示
    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_placeholder(self, text: str):
        self._clear_grid()
        if not hasattr(self, "_placeholder_label"):
            self._placeholder_label = QLabel(self)
            self._placeholder_label.setAlignment(Qt.AlignCenter)
            self._placeholder_label.setStyleSheet("QLabel { color: palette(window-text); font-size: 14px; }")
        self._placeholder_label.setText(text)
        # 跨两列水平居中
        self.grid_layout.addWidget(self._placeholder_label, 0, 0, 1, 2, alignment=Qt.AlignCenter)

    def _begin_loading_state(self):
        self.search_box.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.page_label.setText("...")
        # 居中显示圆形进度环 + 文本
        self._clear_grid()
        self._loading_container = QWidget(self)
        lay = QVBoxLayout(self._loading_container)
        lay.setContentsMargins(0, 24, 0, 24)
        lay.setSpacing(8)
        ring = IndeterminateProgressRing(self._loading_container)
        ring.setFixedSize(40, 40)
        txt = StrongBodyLabel(self.tra("正在获取模型..."), self._loading_container)
        txt.setAlignment(Qt.AlignCenter)
        # txt.setStyleSheet("QLabel { color: palette(window-text); }")
        lay.addWidget(ring, 0, Qt.AlignCenter)
        lay.addWidget(txt, 0, Qt.AlignCenter)
        self.grid_layout.addWidget(self._loading_container, 0, 0, 1, 2, alignment=Qt.AlignCenter)

    def _end_loading_state(self):
        self.search_box.setEnabled(True)
        if hasattr(self, "_loading_container") and self._loading_container:
            self._loading_container.deleteLater()
            self._loading_container = None
        # 翻页按钮的可用状态由 _refresh_list 里计算


    def _accept_if_single_clicked(self) -> None:
        # grid 方案：如果只有一个选择，仍然允许回车确认
        if len(self._selected) == 1:
            self.accept()

    # 数据刷新
    def _toggle_selection(self, name: str, checked: bool) -> None:
        if checked:
            self._selected.add(name)
        else:
            self._selected.discard(name)
        self._on_selection_change()

    def _apply_filter_and_refresh(self) -> None:
        q = self.search_box.text().strip().lower()
        if q:
            self._filtered = [m for m in self._all_models if q in m.lower()]
        else:
            self._filtered = list(self._all_models)
        self._current_page = 1
        self._refresh_list()

    def _goto_page(self, page: int) -> None:
        total_pages = max(1, (len(self._filtered) + self._page_size - 1) // self._page_size)
        page = max(1, min(page, total_pages))
        if page != self._current_page:
            self._current_page = page
            self._refresh_list()

    def _refresh_list(self) -> None:
        total = len(self._filtered)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        start = (self._current_page - 1) * self._page_size
        end = min(start + self._page_size, total)
        self.page_label.setText(f"{self._current_page}/{total_pages}")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < total_pages)

        # 清空旧的按钮
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # 两列胶囊按钮布局
        cols = 2
        row = 0
        col = 0
        for m in self._filtered[start:end]:
            btn = PillPushButton(m, self.grid_parent)
            btn.setCheckable(True)
            btn.setChecked(m in self._selected)
            btn.setStyleSheet(self._capsule_style)
            btn.setMinimumWidth(240)
            btn.setMinimumHeight(36)
            btn.toggled.connect(lambda checked, name=m: self._toggle_selection(name, checked))
            self.grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1