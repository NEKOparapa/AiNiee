import copy
import json
import os
import random

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FlowLayout,
    FluentIcon,
    HorizontalSeparator,
    IconWidget,
    PrimaryPushButton,
    StrongBodyLabel,
    SubtitleLabel,
    themeColor,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Platform.APIEditPage import APIEditPage
from UserInterface.Platform.APIItemCard import APIItemCard
from UserInterface.Platform.AddAPIDialog import AddAPIDialog
from UserInterface.Platform.ArgsEditPage import ArgsEditPage
from UserInterface.Platform.LimitEditPage import LimitEditPage
from UserInterface.Widget.Toast import ToastMixin


class APITypeCard(CardWidget):
    """按接口类型分组显示接口按钮"""

    def __init__(self, title: str, icon: FluentIcon, description: str = "", parent=None):
        super().__init__(parent)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 16, 20, 16)
        self.vBoxLayout.setSpacing(16)

        self.headerWidget = QWidget()
        self.headerWidget.setMaximumWidth(1000)
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLayout.setSpacing(12)

        self.iconWidget = IconWidget(icon, self)
        self.iconWidget.setFixedSize(28, 28)
        self.headerLayout.addWidget(self.iconWidget)

        self.titleContainer = QWidget()
        self.titleLayout = QVBoxLayout(self.titleContainer)
        self.titleLayout.setContentsMargins(0, 0, 0, 0)
        self.titleLayout.setSpacing(2)

        self.titleLabel = StrongBodyLabel(title, self)
        self.titleLayout.addWidget(self.titleLabel)

        if description:
            self.descLabel = CaptionLabel(description, self)
            self.titleLayout.addWidget(self.descLabel)

        self.headerLayout.addWidget(self.titleContainer)
        self.headerLayout.addStretch(1)

        self.vBoxLayout.addWidget(self.headerWidget)
        self.vBoxLayout.addWidget(HorizontalSeparator(self))

        self.contentWidget = QWidget()
        self.flowLayout = FlowLayout(self.contentWidget, needAni=False)
        self.flowLayout.setContentsMargins(0, 4, 0, 0)
        self.flowLayout.setVerticalSpacing(12)
        self.flowLayout.setHorizontalSpacing(12)

        self.vBoxLayout.addWidget(self.contentWidget)

        self._card_count = 0

    def addWidget(self, widget):
        self.flowLayout.addWidget(widget)
        self._card_count += 1

    def removeWidget(self, widget):
        self.flowLayout.removeWidget(widget)
        self._card_count = max(0, self._card_count - 1)

    def get_card_count(self):
        return self._card_count


class InterfaceHeaderCard(CardWidget, ConfigMixin):
    """顶部接口管理栏"""

    addClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(92)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(16)

        self.titleLabel = SubtitleLabel(self.tra("接口管理"), self)
        self.layout.addWidget(self.titleLabel)
        self.layout.addStretch(1)

        self.activeInfoWidget = QWidget(self)
        self.activeInfoLayout = QVBoxLayout(self.activeInfoWidget)
        self.activeInfoLayout.setContentsMargins(0, 0, 0, 0)
        self.activeInfoLayout.setSpacing(2)

        self.activeCaptionLabel = CaptionLabel(self.tra("当前激活接口"), self.activeInfoWidget)
        self.activeNameLabel = StrongBodyLabel(self.tra("未设置"), self.activeInfoWidget)
        self.activeInfoLayout.addWidget(self.activeCaptionLabel)
        self.activeInfoLayout.addWidget(self.activeNameLabel)

        self.layout.addWidget(self.activeInfoWidget)

        self.add_btn = PrimaryPushButton(self.tra("添加接口"), self)
        self.add_btn.setIcon(FluentIcon.ADD)
        self.add_btn.clicked.connect(lambda checked=False: self.addClicked.emit())
        self.layout.addWidget(self.add_btn)

        self.set_active_api(None)

    def set_active_api(self, name: str | None):
        if name:
            self.activeNameLabel.setText(name)
            self.activeNameLabel.setStyleSheet(f"color: {themeColor().name()};")
        else:
            self.activeNameLabel.setText(self.tra("未设置"))
            self.activeNameLabel.setStyleSheet("color: rgba(128, 128, 128, 0.85);")


class PlatformPage(QFrame, ConfigMixin, ToastMixin, Base):
    GROUP_CONFIG = {
        "local": {
            "title_key": "本地接口",
            "description": "本地部署的模型接口",
            "icon": FluentIcon.CONNECT,
            "order": 0,
        },
        "online": {
            "title_key": "官方接口",
            "description": "官方平台提供的在线接口",
            "icon": FluentIcon.CLOUD,
            "order": 1,
        },
        "custom": {
            "title_key": "自定义接口",
            "description": "第三方或自定义配置的接口",
            "icon": FluentIcon.ASTERISK,
            "order": 2,
        },
    }

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "platforms": {},
            "api_settings": {
                "translate": None,
                "polish": None,
            },
        }

        self.window = window
        self.api_buttons = {}
        self.group_cards = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 12, 24, 20)
        main_layout.setSpacing(12)

        self.header_card = InterfaceHeaderCard(self)
        self.header_card.addClicked.connect(self.on_add_api_clicked)
        main_layout.addWidget(self.header_card)

        self.content_container = QWidget()
        self.content_container.setStyleSheet("QWidget { background: transparent; }")
        self.container = QVBoxLayout(self.content_container)
        self.container.setSpacing(16)
        self.container.setContentsMargins(4, 4, 4, 16)
        main_layout.addWidget(self.content_container, 1)

        self._create_empty_hint_widget()

        config = self.save_config(self.load_config_from_default())
        config = self._normalize_api_settings(config, persist=True)

        self._create_group_cards()
        self._populate_api_cards(config)
        self._refresh_active_interface_ui(config)

        self.subscribe(Base.EVENT.API_TEST_DONE, self.api_test_done)

        self._update_visibility()
        self.container.addStretch(1)

    def _create_empty_hint_widget(self):
        self.empty_hint_widget = QWidget()
        self.empty_hint_widget.setStyleSheet("QWidget { background: transparent; }")

        hint_layout = QVBoxLayout(self.empty_hint_widget)
        hint_layout.setContentsMargins(0, 60, 0, 60)
        hint_layout.setSpacing(20)
        hint_layout.setAlignment(Qt.AlignCenter)

        title_label = SubtitleLabel(self.tra("暂无接口"))
        title_label.setContentsMargins(0, 0, 0, 0)
        title_label.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(title_label)

        subtitle_label = BodyLabel(self.tra("点击顶部的“添加接口”按钮创建您的第一个接口"))
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(subtitle_label)

        self.empty_hint_widget.hide()
        self.container.addWidget(self.empty_hint_widget)

    def _create_group_cards(self):
        sorted_groups = sorted(
            self.GROUP_CONFIG.keys(),
            key=lambda group_name: self.GROUP_CONFIG[group_name]["order"],
        )

        for group_name in sorted_groups:
            group_config = self.GROUP_CONFIG[group_name]
            card = APITypeCard(
                title=self.tra(group_config["title_key"]),
                icon=group_config["icon"],
                description=self.tra(group_config["description"]),
                parent=self,
            )
            self.group_cards[group_name] = card
            self.container.addWidget(card)

    def _populate_api_cards(self, config):
        platforms = config.get("platforms", {})
        grouped_platforms = {"local": [], "online": [], "custom": []}

        for tag, api_data in platforms.items():
            group = api_data.get("group", "custom")
            if group not in grouped_platforms:
                group = "custom"
            grouped_platforms[group].append((tag, api_data))

        for group_name, items in grouped_platforms.items():
            items.sort(key=lambda item: item[1].get("name", ""))
            for tag, api_data in items:
                self.add_api_card(tag, api_data)

    def _update_visibility(self):
        total_cards = len(self.api_buttons)

        for card in self.group_cards.values():
            card.setVisible(card.get_card_count() > 0)

        self.empty_hint_widget.setVisible(total_cards == 0)

    def _normalize_api_settings(self, config: dict, persist: bool = False) -> dict:
        platforms = config.get("platforms", {})
        api_settings = config.setdefault("api_settings", {})

        translate_tag = api_settings.get("translate")
        polish_tag = api_settings.get("polish")

        active_tag = translate_tag if translate_tag in platforms else None
        if active_tag is None and polish_tag in platforms:
            active_tag = polish_tag

        changed = (
            api_settings.get("translate") != active_tag
            or api_settings.get("polish") != active_tag
        )

        api_settings["translate"] = active_tag
        api_settings["polish"] = active_tag

        if persist and changed:
            return self.save_config(config)

        return config

    def _get_active_api_tag(self, config: dict) -> str | None:
        config = self._normalize_api_settings(config)
        return config.get("api_settings", {}).get("translate")

    def _refresh_active_interface_ui(self, config=None):
        if config is None:
            config = self._normalize_api_settings(self.load_config(), persist=True)
        else:
            config = self._normalize_api_settings(config)

        platforms = config.get("platforms", {})
        active_tag = self._get_active_api_tag(config)
        active_name = None

        if active_tag and active_tag in platforms:
            active_name = platforms[active_tag].get("name", active_tag)

        self.header_card.set_active_api(active_name)

        for tag, button in self.api_buttons.items():
            button.set_active(tag == active_tag)

    def load_file(self, path: str) -> dict:
        result = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as reader:
                result = json.load(reader)
        return result

    def api_test(self, tag: str):
        config = self.load_config()
        platform = config.get("platforms", {}).get(tag)
        if platform is None:
            self.warning_toast("", self.tra("接口不存在"))
            return
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.API_TEST
            data = copy.deepcopy(platform)
            self.emit(Base.EVENT.API_TEST_START, data)
        else:
            self.warning_toast("", self.tra("接口测试正在执行中，请稍后再试"))

    def api_test_done(self, event: int, data: dict):
        Base.work_status = Base.STATUS.IDLE
        if len(data.get("failure", [])) > 0:
            info_cont = (
                self.tra("测试完成：成功")
                + f" {len(data.get('success', []))} "
                + self.tra("失败")
                + f" {len(data.get('failure', []))}"
            )
            self.error_toast("", info_cont)
        else:
            self.success_toast("", self.tra("测试成功"))

    def activate_platform(self, tag: str):
        config = self._normalize_api_settings(self.load_config())
        platforms = config.get("platforms", {})
        if tag not in platforms:
            return

        current_tag = self._get_active_api_tag(config)
        if current_tag == tag:
            self._refresh_active_interface_ui(config)
            return

        api_settings = config.setdefault("api_settings", {})
        api_settings["translate"] = tag
        api_settings["polish"] = tag
        config = self.save_config(config)

        self._refresh_active_interface_ui(config)

        api_name = platforms[tag].get("name", tag)
        self.success_toast("", f"{self.tra('已激活接口')}: {api_name}")

    def delete_platform(self, tag: str) -> None:
        config = self._normalize_api_settings(self.load_config())
        platforms = config.get("platforms", {})
        if tag not in platforms:
            return

        api_settings = config.setdefault("api_settings", {})
        if api_settings.get("translate") == tag or api_settings.get("polish") == tag:
            api_settings["translate"] = None
            api_settings["polish"] = None

        del platforms[tag]
        config = self.save_config(config)

        if tag in self.api_buttons:
            button = self.api_buttons.pop(tag)
            group_name = button.api_data.get("group", "custom")
            if group_name not in self.group_cards:
                group_name = "custom"

            self.group_cards[group_name].removeWidget(button)
            button.deleteLater()

        self.success_toast("", self.tra("接口已删除"))
        self._refresh_active_interface_ui(config)
        self._update_visibility()

    def show_api_edit_page(self, key: str):
        APIEditPage(self.window, key).exec()
        self.refresh_card(key)

    def show_args_edit_page(self, key: str):
        ArgsEditPage(self.window, key).exec()

    def show_limit_edit_page(self, key: str):
        LimitEditPage(self.window, key).exec()
        self.refresh_card(key)

    def refresh_card(self, tag: str):
        if tag not in self.api_buttons:
            return

        config = self._normalize_api_settings(self.load_config(), persist=True)
        api_data = config.get("platforms", {}).get(tag)
        if api_data:
            self.api_buttons[tag].update_info(api_data)
        self._refresh_active_interface_ui(config)

    def on_add_api_clicked(self):
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})

        def on_confirm(data):
            self.create_new_api(data)

        dialog = AddAPIDialog(self.window, preset_platforms, on_confirm=on_confirm)
        dialog.exec()

    def create_new_api(self, data: dict):
        config = self._normalize_api_settings(self.load_config())
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})
        platform_tag = data.get("platform_tag")

        if platform_tag not in preset_platforms:
            self.error_toast("", self.tra("未找到选定的平台预设"))
            return

        preset = preset_platforms[platform_tag]
        new_platform = copy.deepcopy(preset)

        tag = f"{platform_tag}_{random.randint(100000, 999999)}"
        new_platform["tag"] = tag
        new_platform["group"] = preset.get("group", "custom")
        new_platform["name"] = data.get("name")
        new_platform["model"] = data.get("model")

        if "api_key" in data:
            new_platform["api_key"] = data.get("api_key", "")
        if "api_url" in data and data.get("api_url"):
            new_platform["api_url"] = data.get("api_url")
        if "api_format" in data:
            new_platform["api_format"] = data.get("api_format")
        if "auto_complete" in data:
            new_platform["auto_complete"] = data.get("auto_complete")
        if platform_tag == "amazonbedrock":
            new_platform["region"] = data.get("region", "")
            new_platform["access_key"] = data.get("access_key", "")
            new_platform["secret_key"] = data.get("secret_key", "")

        if data.get("model") and data.get("model") not in new_platform.get("model_datas", []):
            new_platform["model_datas"].append(data.get("model"))

        config.setdefault("platforms", {})[tag] = new_platform
        self.save_config(config)

        self.add_api_card(tag, new_platform)
        self.success_toast("", self.tra("接口添加成功"))
        self._refresh_active_interface_ui(config)
        self._update_visibility()

    def add_api_card(self, tag: str, api_data: dict):
        button = APIItemCard(tag, api_data, self)

        button.testClicked.connect(self.api_test)
        button.activateClicked.connect(self.activate_platform)
        button.editClicked.connect(self.show_api_edit_page)
        button.editLimitClicked.connect(self.show_limit_edit_page)
        button.editArgsClicked.connect(self.show_args_edit_page)
        button.deleteClicked.connect(self.delete_platform)

        self.api_buttons[tag] = button

        group = api_data.get("group", "custom")
        if group not in self.group_cards:
            group = "custom"

        self.group_cards[group].addWidget(button)
