import os
import json
import copy
import random

from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QWidget, QHBoxLayout

from qfluentwidgets import (
    PrimaryPushButton, FluentIcon, SingleDirectionScrollArea,
    StrongBodyLabel, CardWidget, FlowLayout, SubtitleLabel, BodyLabel
)

from ModuleFolders.Base.Base import Base
from UserInterface.Platform.AddAPIDialog import AddAPIDialog
from UserInterface.Platform.APIItemCard import APIItemCard
from UserInterface.Platform.APIEditPage import APIEditPage
from UserInterface.Platform.ArgsEditPage import ArgsEditPage
from UserInterface.Platform.LimitEditPage import LimitEditPage

class PlatformPage(QFrame, Base):

    # 分组配置
    GROUP_CONFIG = {
        "local": {
            "title_key": "本地接口",
            "icon": FluentIcon.HOME,
            "order": 0
        },
        "online": {
            "title_key": "官方接口",
            "icon": FluentIcon.GLOBE,
            "order": 1
        },
        "custom": {
            "title_key": "自定义接口",
            "icon": FluentIcon.EDIT,
            "order": 2
        }
    }

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "platforms": {},
            "api_settings": {
                "translate": None,
                "polish": None
            }
        }

        self.window = window
        self.api_cards = {}
        self.group_containers = {}
        self.group_layouts = {}
        self.group_card_counts = {}  # 跟踪每个分组的卡片数量

        # 主滚动区域
        self.main_scroll = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("QWidget { background: transparent; }")
        self.container = QVBoxLayout(self.scroll_widget)
        self.container.setSpacing(24)
        self.container.setContentsMargins(36, 20, 36, 36)
        self.main_scroll.setWidget(self.scroll_widget)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_scroll)

        # 创建空状态提示组件（初始隐藏）
        self._create_empty_hint_widget()

        config = self.save_config(self.load_config_from_default())

        self.add_api_list_widget(self.container, config)

        self.bottom_spacer = QWidget()
        self.bottom_spacer.setFixedHeight(60)
        self.bottom_spacer.setStyleSheet("background: transparent;")
        self.container.addWidget(self.bottom_spacer)

        self.container.addStretch(1)
        
        self.create_floating_add_button()
        
        self.subscribe(Base.EVENT.API_TEST_DONE, self.api_test_done)

        # 初始化完成后更新可见性
        self._update_visibility()

    def _create_empty_hint_widget(self):
        """创建空状态提示组件"""
        self.empty_hint_widget = QWidget()
        self.empty_hint_widget.setStyleSheet("QWidget { background: transparent; }")
        
        hint_layout = QVBoxLayout(self.empty_hint_widget)
        hint_layout.setContentsMargins(0, 100, 0, 100)
        hint_layout.setSpacing(16)
        hint_layout.setAlignment(Qt.AlignCenter)
        
        # 图标
        icon_widget = QWidget()
        icon_layout = QHBoxLayout(icon_widget)
        icon_layout.setAlignment(Qt.AlignCenter)
        from qfluentwidgets import IconWidget
        empty_icon = IconWidget(FluentIcon.ADD_TO, self.empty_hint_widget)
        empty_icon.setFixedSize(64, 64)
        icon_layout.addWidget(empty_icon)
        hint_layout.addWidget(icon_widget)
        
        # 主标题
        title_label = SubtitleLabel(self.tra("暂无接口"))
        title_label.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = BodyLabel(self.tra("点击右下角的「添加接口」按钮创建您的第一个接口"))
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #707070;")
        hint_layout.addWidget(subtitle_label)
        
        # 初始隐藏
        self.empty_hint_widget.hide()
        self.container.addWidget(self.empty_hint_widget)

    def _update_visibility(self):
        """更新分组和空状态提示的可见性"""
        total_cards = len(self.api_cards)
        
        # 更新每个分组的可见性
        for group_name, container in self.group_containers.items():
            card_count = self.group_card_counts.get(group_name, 0)
            if card_count > 0:
                container.show()
            else:
                container.hide()
        
        # 更新空状态提示和底部间隔的可见性
        if total_cards == 0:
            self.empty_hint_widget.show()
            self.bottom_spacer.hide()
        else:
            self.empty_hint_widget.hide()
            self.bottom_spacer.show()

    def create_floating_add_button(self):
        """创建悬浮的添加按钮"""
        self.floating_add_btn = PrimaryPushButton(self.tra("添加接口"), self)
        self.floating_add_btn.setIcon(FluentIcon.ADD)
        self.floating_add_btn.setFixedSize(140, 50)
        font = self.floating_add_btn.font()
        font.setPointSize(12)
        font.setBold(True)
        self.floating_add_btn.setFont(font)
        self.floating_add_btn.clicked.connect(self.on_add_api_clicked)
        
        self.update_floating_button_position()
        QTimer.singleShot(100, self._refresh_floating_button_style)

    def _refresh_floating_button_style(self):
        if hasattr(self, 'floating_add_btn') and self.floating_add_btn:
            self.floating_add_btn.update()
            self.floating_add_btn.raise_()
            self.floating_add_btn.show()

    def update_floating_button_position(self):
        if hasattr(self, 'floating_add_btn'):
            margin_right = 30
            margin_bottom = 30
            btn_width = self.floating_add_btn.width()
            btn_height = self.floating_add_btn.height()
            
            x = self.width() - btn_width - margin_right
            y = self.height() - btn_height - margin_bottom
            
            self.floating_add_btn.move(x, y)
            self.floating_add_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_floating_button_position()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_floating_button_position()

    def load_file(self, path: str) -> dict:
        result = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as reader:
                result = json.load(reader)
        return result

    def api_test(self, tag: str):
        config = self.load_config()
        platform = config.get("platforms").get(tag)
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
            info_cont = self.tra("测试完成：成功") + f" {len(data.get('success', []))} " + self.tra("失败") + f" {len(data.get('failure', []))}"
            self.error_toast("", info_cont)
        else:
            info_cont = self.tra("测试成功")
            self.success_toast("", info_cont)
            
    def delete_platform(self, tag: str) -> None:
        config = self.load_config()
        if tag not in config.get("platforms", {}): 
            return
        
        api_settings = config.get("api_settings", {})
        if api_settings.get("translate") == tag: 
            api_settings["translate"] = None
        if api_settings.get("polish") == tag: 
            api_settings["polish"] = None
        
        del config["platforms"][tag]
        self.save_config(config)
        
        if tag in self.api_cards:
            card = self.api_cards.pop(tag)
            
            # 获取该卡片所属的分组名称
            group_name = card.api_data.get("group", "custom")
            if group_name not in self.group_layouts:
                group_name = "custom"
            
            # 更新分组卡片计数
            if group_name in self.group_card_counts:
                self.group_card_counts[group_name] = max(0, self.group_card_counts[group_name] - 1)
            
            # 从布局中移除
            if group_name in self.group_layouts:
                self.group_layouts[group_name].removeWidget(card)

            card.deleteLater()
            self.success_toast("", self.tra("接口已删除"))
            
            # 更新可见性
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
        if tag in self.api_cards:
            config = self.load_config()
            api_data = config.get("platforms", {}).get(tag, {})
            if api_data:
                self.api_cards[tag].update_info(api_data)

    def on_add_api_clicked(self):
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})
        
        def on_confirm(data):
            self.create_new_api(data)
        
        dialog = AddAPIDialog(self.window, preset_platforms, on_confirm=on_confirm)
        dialog.exec()

    def create_new_api(self, data: dict):
        """创建新接口并正确分类"""
        config = self.load_config()
        
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})
        
        platform_tag = data.get("platform_tag")
        
        if platform_tag in preset_platforms:
            preset = preset_platforms[platform_tag]
            new_platform = copy.deepcopy(preset)
        else:
            self.error_toast("", self.tra("未找到选定的平台预设"))
            return

        # 1. 生成唯一 Tag
        tag = f"{platform_tag}_{random.randint(10000, 99999)}"
        new_platform["tag"] = tag
        
        # 2. 从预设中获取 group，如果预设没有则默认为 custom
        new_platform["group"] = preset.get("group", "custom")
        
        new_platform["name"] = data.get("name")
        new_platform["model"] = data.get("model")

        # 填充用户输入的数据
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

        if "platforms" not in config:
            config["platforms"] = {}

        config["platforms"][tag] = new_platform
        self.save_config(config)
        
        # 添加卡片到对应分组
        self.add_api_card(tag, new_platform, config.get("api_settings", {}))
        self.success_toast("", self.tra("接口添加成功"))
        
        # 更新可见性
        self._update_visibility()

    def _create_group_section(self, parent, group_name: str):
        """创建分组区域，使用 FlowLayout 实现卡片排列"""
        group_config = self.GROUP_CONFIG.get(group_name, {
            "title_key": group_name,
            "icon": FluentIcon.FOLDER,
            "order": 99
        })
        
        # 整个分组容器
        group_container = QFrame()
        group_container.setStyleSheet("QFrame { background: transparent; }")
        group_layout = QVBoxLayout(group_container)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(12)
        
        # 标题栏
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(4, 0, 0, 0)
        title_layout.setSpacing(10)
        
        # 图标和标题
        title_label = StrongBodyLabel(self.tra(group_config["title_key"]))
        
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        
        group_layout.addWidget(title_container)
        
        # 卡片容器
        cards_container = QFrame()
        cards_container.setStyleSheet("QFrame { background: transparent; }")
        
        # 开启排版动画
        cards_layout = FlowLayout(cards_container, needAni=True)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setVerticalSpacing(12)
        cards_layout.setHorizontalSpacing(12)
        
        group_layout.addWidget(cards_container)
        
        self.group_containers[group_name] = group_container
        self.group_layouts[group_name] = cards_layout
        self.group_card_counts[group_name] = 0  # 初始化计数
        
        parent.addWidget(group_container)
        
        return cards_layout

    def add_api_list_widget(self, parent, config):
        """初始化接口列表"""
        platforms = config.get("platforms", {})
        api_settings = config.get("api_settings", {})
        
        grouped_platforms = {"local": [], "online": [], "custom": []}
        
        for tag, api_data in platforms.items():
            group = api_data.get("group", "custom")
            if group not in grouped_platforms: 
                group = "custom"
            grouped_platforms[group].append((tag, api_data))
        
        sorted_groups = sorted(self.GROUP_CONFIG.keys(), key=lambda g: self.GROUP_CONFIG[g]["order"])
        
        for group_name in sorted_groups:
            self._create_group_section(parent, group_name)
            
            # 按名称排序，使界面更整洁
            items = grouped_platforms.get(group_name, [])
            items.sort(key=lambda x: x[1].get("name", ""))
            
            for tag, api_data in items:
                self.add_api_card(tag, api_data, api_settings)

    def add_api_card(self, tag: str, api_data: dict, api_settings: dict):
        """添加卡片"""
        activate_status = None
        if api_settings.get("translate") == tag:
            activate_status = "translate"
        elif api_settings.get("polish") == tag:
            activate_status = "polish"
        
        card = APIItemCard(tag, api_data, activate_status, self)
        
        card.testClicked.connect(self.api_test)
        card.activateChanged.connect(self.on_activate_changed)
        card.editClicked.connect(self.show_api_edit_page)
        card.editLimitClicked.connect(self.show_limit_edit_page)
        card.editArgsClicked.connect(self.show_args_edit_page)
        card.deleteClicked.connect(self.delete_platform)
        
        self.api_cards[tag] = card
        
        group = api_data.get("group", "custom")
        if group not in self.group_layouts: 
            group = "custom"
        
        # 添加到 FlowLayout 并更新计数
        if group in self.group_layouts:
            self.group_layouts[group].addWidget(card)
            self.group_card_counts[group] = self.group_card_counts.get(group, 0) + 1

    def on_activate_changed(self, api_tag: str, activate_type: str):
        config = self.load_config()
        if "api_settings" not in config:
            config["api_settings"] = {"translate": None, "polish": None}
        
        # 如果是激活操作，先清除旧的激活状态（UI上）
        if activate_type:
            old_tag = config["api_settings"].get(activate_type)
            if old_tag and old_tag != api_tag and old_tag in self.api_cards:
                self.api_cards[old_tag].set_activate_status(None)

        # 更新配置
        if activate_type == "translate":
            config["api_settings"]["translate"] = api_tag
        elif activate_type == "polish":
            config["api_settings"]["polish"] = api_tag
        else:
            # 取消激活的情况，需要判断是取消了谁
            if config["api_settings"].get("translate") == api_tag:
                config["api_settings"]["translate"] = None
            if config["api_settings"].get("polish") == api_tag:
                config["api_settings"]["polish"] = None

        self.save_config(config)
        
        if activate_type == "translate":
            self.success_toast("", self.tra(f"已设置 {api_tag} 为翻译接口"))
        elif activate_type == "polish":
            self.success_toast("", self.tra(f"已设置 {api_tag} 为润色接口"))