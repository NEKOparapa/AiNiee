"""Compact provider lists shared by transcription and image generation."""

import copy
from uuid import uuid4

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action, BodyLabel, CardWidget, FluentIcon, IconWidget, MessageBox,
    PrimaryPushButton, RoundMenu, SingleDirectionScrollArea, StrongBodyLabel,
    SubtitleLabel, TitleLabel, qconfig, themeColor,
)

from Frontend.components.toast import ToastMixin
from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.core.media_provider_config import build_media_provider_update, normalize_media_provider
from Frontend.pages.providers.api_item_card import APIItemCard
from Frontend.pages.providers.media_provider_dialog import (
    AddMediaProviderDialog, EditMediaProviderDialog, MediaProviderArgsDialog,
)
from Frontend.pages.providers.platform_page import APITypeCard


class ProviderHeaderCard(CardWidget, ConfigMixin):
    def __init__(self, title, icon, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        self.leftSection = QWidget(self)
        title_layout = QHBoxLayout(self.leftSection)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)
        self.titleIcon = IconWidget(icon, self)
        self.titleIcon.setFixedSize(30, 30)
        title_layout.addWidget(self.titleIcon)
        self.titleLabel = TitleLabel(self.tra(title), self)
        title_layout.addWidget(self.titleLabel)
        title_layout.addStretch(1)
        layout.addWidget(self.leftSection)

        self.statusPill = QFrame(self)
        self.statusPill.setObjectName("providerStatusPill")
        pill_layout = QHBoxLayout(self.statusPill)
        pill_layout.setContentsMargins(14, 6, 16, 6)
        pill_layout.setSpacing(8)
        self.statusIcon = IconWidget(FluentIcon.INFO, self.statusPill)
        self.statusIcon.setFixedSize(16, 16)
        pill_layout.addWidget(self.statusIcon)
        self.statusLabel = StrongBodyLabel(self.statusPill)
        pill_layout.addWidget(self.statusLabel)
        center = QWidget(self)
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.statusPill, 0, Qt.AlignCenter)
        layout.addWidget(center, 1)

        self.rightSection = QWidget(self)
        actions = QHBoxLayout(self.rightSection)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch(1)
        self.add_button = PrimaryPushButton(FluentIcon.ADD, self.tra("添加接口"), self)
        self.add_button.setMinimumWidth(120)
        actions.addWidget(self.add_button, 0, Qt.AlignRight)
        layout.addWidget(self.rightSection)
        side_width = max(self.leftSection.sizeHint().width(), self.rightSection.sizeHint().width())
        self.leftSection.setFixedWidth(side_width)
        self.rightSection.setFixedWidth(side_width)
        self._active_name = None
        self.set_active_api(None)
        qconfig.themeColorChanged.connect(self._refresh_status)

    def set_active_api(self, name):
        self._active_name = name
        self._refresh_status()

    def _refresh_status(self, *_):
        active = bool(self._active_name)
        text = f"{self.tra('已激活')}: {self._active_name}" if active else self.tra("未设置激活接口")
        self.statusLabel.setText(self.statusLabel.fontMetrics().elidedText(text, Qt.ElideRight, 280))
        self.statusLabel.setToolTip(text)
        self.statusIcon.setIcon(FluentIcon.ROBOT if active else FluentIcon.INFO)
        color = themeColor()
        rgb = f"{color.red()}, {color.green()}, {color.blue()}" if active else "128, 128, 128"
        self.statusPill.setStyleSheet(
            "QFrame#providerStatusPill {"
            f"background-color: rgba({rgb}, 0.08); border: 1px solid rgba({rgb}, 0.22);"
            "border-radius: 16px; }"
        )


class MediaProviderItemCard(APIItemCard):
    """Use the translation-provider button style with only supported actions."""

    def _apply_info(self):
        name = str(self.api_data.get("name", ""))
        icon = self._get_icon()
        for button in (self.normal_button, self.active_button):
            button.setIcon(icon)
            button.setText(name)
            button.ensurePolished()
            metrics = button.fontMetrics()
            decoration_width = button.sizeHint().width() - metrics.horizontalAdvance(name)
            text_width = max(0, button.width() - decoration_width - 2)
            button.setText(metrics.elidedText(name, Qt.ElideRight, text_width))
            button.setToolTip(name)
        self.setFixedHeight(self.normal_button.sizeHint().height())

    def _build_menu(self, button):
        menu = RoundMenu(parent=button)
        activate = Action(FluentIcon.ACCEPT_MEDIUM, self.tra("激活接口"),
                          triggered=lambda checked=False: self.activateClicked.emit(self.api_tag))
        self._activate_actions.append(activate)
        menu.addAction(activate)
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.EDIT, self.tra("编辑接口"),
                              triggered=lambda checked=False: self.editClicked.emit(self.api_tag)))
        menu.addAction(Action(FluentIcon.DEVELOPER_TOOLS, self.tra("调整参数"),
                              triggered=lambda checked=False: self.editArgsClicked.emit(self.api_tag)))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, self.tra("删除接口"),
                              triggered=lambda checked=False: self.deleteClicked.emit(self.api_tag)))
        button.setMenu(menu)


class MediaProviderPage(QFrame, ConfigMixin, ToastMixin, Base):
    KIND = ""
    TITLE = ""
    ICON = FluentIcon.IOT

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setObjectName(text.replace(" ", "-"))
        self._platforms = {}
        self._active_id = ""
        self._active_dialog = None
        self._pending_config = None
        self._ready = False
        self.api_buttons = {}
        self.group_cards = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 20)
        layout.setSpacing(12)
        self.header_card = ProviderHeaderCard(self.TITLE, self.ICON, self)
        self.header_card.add_button.clicked.connect(self._add_platform)
        layout.addWidget(self.header_card)
        self.scroll_area = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll_area.viewport().setObjectName("mediaProviderViewport")
        self.scroll_area.viewport().setStyleSheet("QWidget#mediaProviderViewport { background: transparent; }")
        self.content = QWidget()
        self.content.setObjectName("mediaProviderContent")
        self.content.setStyleSheet("QWidget#mediaProviderContent { background: transparent; }")
        self.container = QVBoxLayout(self.content)
        self.container.setContentsMargins(4, 4, 8, 16)
        self.container.setSpacing(16)
        self.scroll_area.setWidget(self.content)
        layout.addWidget(self.scroll_area, 1)
        self._reload_config()
        self._ready = True

    @property
    def _providers_key(self):
        return f"{self.KIND}_platforms"

    @property
    def _active_key(self):
        return f"active_{self.KIND}_platform"

    def showEvent(self, event):
        super().showEvent(event)
        if self._ready and self._active_dialog is None:
            self._reload_config()

    def _apply_config(self, config):
        platforms = config.get(self._providers_key, {})
        if not isinstance(platforms, dict) or any(not isinstance(value, dict) for value in platforms.values()):
            raise ValueError("接口列表必须是对象。")
        groups = {"online": [], "custom": []}
        for identifier, platform in platforms.items():
            data = normalize_media_provider(self.KIND, platform)
            group = "online" if data.get("group") == "online" else "custom"
            if group == "online":
                data.setdefault("icon", "dashscope" if data["api_format"] == "DashScope" else "volcengine")
            groups[group].append((identifier, data))
        if self._active_dialog is not None:
            # The menu's Qt mouse handler is still on the stack inside exec().
            # Rebuilding here deletes that menu and crashes when exec() returns.
            # Persist edits immediately, but keep its widgets alive until the
            # modal dialog AND the originating menu event have both returned.
            self._pending_config = copy.deepcopy(config)
            return
        self._pending_config = None
        self._platforms = copy.deepcopy(platforms)
        self._active_id = config.get(self._active_key, "")
        while self.container.count():
            item = self.container.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.api_buttons.clear()
        self.group_cards.clear()
        for group, title, description, icon in (
            ("online", "官方接口", "官方平台提供的在线接口", FluentIcon.CLOUD),
            ("custom", "自定义接口", "第三方或自定义配置的接口", FluentIcon.ASTERISK),
        ):
            if not groups[group]:
                continue
            card = APITypeCard(self.tra(title), icon, self.tra(description), self.content)
            for identifier, data in groups[group]:
                button = MediaProviderItemCard(identifier, data, card)
                button.setToolTip(str(data.get("name", identifier)))
                button.set_active(identifier == self._active_id)
                button.activateClicked.connect(self._activate_platform)
                button.editClicked.connect(self._edit_platform)
                button.editArgsClicked.connect(self._edit_parameters)
                button.deleteClicked.connect(self._delete_platform)
                self.api_buttons[identifier] = button
                card.addWidget(button)
            self.group_cards[group] = card
            self.container.addWidget(card)
        if not platforms:
            empty = QWidget(self.content)
            hint = QVBoxLayout(empty)
            hint.setContentsMargins(24, 60, 24, 60)
            hint.setSpacing(20)
            title = SubtitleLabel(self.tra("暂无接口"), empty)
            title.setAlignment(Qt.AlignCenter)
            hint.addWidget(title)
            caption = BodyLabel(self.tra("点击顶部的“添加接口”按钮创建您的第一个接口"), empty)
            caption.setWordWrap(True)
            caption.setAlignment(Qt.AlignCenter)
            hint.addWidget(caption)
            self.container.addWidget(empty)
        self.container.addStretch(1)
        active = platforms.get(self._active_id)
        self.header_card.set_active_api(str(active.get("name", self._active_id)) if active else None)

    def _reload_config(self):
        try:
            self._apply_config(self.load_config())
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取接口配置，请检查后端连接后重新打开此页面。"))

    def _commit(self, identifier, platform=None, *, action="save", creating=False):
        def update(current):
            exists = identifier in current.get(self._providers_key, {})
            if action == "save" and exists == creating:
                raise ValueError("接口配置已变化，请重新打开页面后重试。")
            current.update(build_media_provider_update(current, self.KIND, identifier, platform, action=action))
        config = self.update_config(update)
        self._apply_config(config)
        return copy.deepcopy(config.get(self._providers_key, {}).get(identifier, {}))

    def _open_dialog(self, dialog):
        self._active_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._active_dialog = None
            dialog.deleteLater()
            if self._pending_config is not None:
                QTimer.singleShot(0, self._apply_pending_config)

    def _apply_pending_config(self):
        if self._active_dialog is None and self._pending_config is not None:
            self._apply_config(self._pending_config)

    def _add_platform(self):
        identifier = f"{self.KIND}_{uuid4().hex}"
        dialog = AddMediaProviderDialog(
            self.KIND, self.window(),
            on_confirm=lambda data: self._commit(identifier, data, creating=True),
        )
        self._open_dialog(dialog)

    def _edit_platform(self, identifier, *, parameters=False):
        if identifier not in self._platforms:
            return
        try:
            dialog_type = MediaProviderArgsDialog if parameters else EditMediaProviderDialog
            dialog = dialog_type(
                self.KIND, self._platforms[identifier], self.window(),
                on_save=lambda data: self._commit(identifier, data),
            )
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法打开接口配置，请重新打开页面后重试。"))
            return
        self._open_dialog(dialog)

    def _edit_parameters(self, identifier):
        self._edit_platform(identifier, parameters=True)

    def _activate_platform(self, identifier):
        try:
            self._commit(identifier, action="activate")
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("激活失败"), self.tra("无法激活接口，请检查后端连接后重试。"))

    def _delete_platform(self, identifier):
        if identifier not in self._platforms:
            return
        content = self.tra("是否删除此接口配置？")
        if identifier == self._active_id:
            content += "\n" + self.tra("删除后将没有激活的接口。")
        dialog = MessageBox(self.tra("删除接口"), content, self.window())
        dialog.yesButton.setText(self.tra("删除"))
        dialog.cancelButton.setText(self.tra("取消"))
        if not dialog.exec():
            return
        try:
            self._commit(identifier, action="delete")
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("删除失败"), self.tra("无法删除接口，请检查后端连接后重试。"))

    def prepare_to_leave(self):
        if self._active_dialog is not None:
            return self._active_dialog.prepare_to_leave()
        return True
