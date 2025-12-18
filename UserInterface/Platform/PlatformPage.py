import os
import json
import copy
import random

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QWidget, QHBoxLayout

from qfluentwidgets import (
    PrimaryPushButton, FluentIcon,
    StrongBodyLabel, FlowLayout, SubtitleLabel, BodyLabel, HorizontalSeparator, VerticalSeparator,
    CardWidget, IconWidget, themeColor, CaptionLabel
)

from ModuleFolders.Base.Base import Base
from UserInterface.Platform.AddAPIDialog import AddAPIDialog
from UserInterface.Platform.APIItemCard import APIItemCard
from UserInterface.Platform.APIEditPage import APIEditPage
from UserInterface.Platform.ArgsEditPage import ArgsEditPage
from UserInterface.Platform.LimitEditPage import LimitEditPage


# ==========================================
# 接口类型分组卡片
# ==========================================

class APITypeCard(CardWidget):
    """
    接口类型分组卡片，用于容纳同一类型的接口按钮
    """

    def __init__(self, title: str, icon: FluentIcon, description: str = "", parent=None):
        super().__init__(parent)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 16, 20, 16)
        self.vBoxLayout.setSpacing(16)

        # ===== 头部区域 =====
        self.headerWidget = QWidget()
        self.headerWidget.setMaximumWidth(1000)
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLayout.setSpacing(12)

        # 图标
        self.iconWidget = IconWidget(icon, self)
        self.iconWidget.setFixedSize(28, 28)
        self.headerLayout.addWidget(self.iconWidget)

        # 标题和描述
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

        # ===== 分隔线 =====
        self.line = HorizontalSeparator(self)
        self.vBoxLayout.addWidget(self.line)

        # ===== 内容区域 =====
        self.contentWidget = QWidget()
        self.flowLayout = FlowLayout(self.contentWidget, needAni=False)
        self.flowLayout.setContentsMargins(0, 4, 0, 0)
        self.flowLayout.setVerticalSpacing(12)
        self.flowLayout.setHorizontalSpacing(12)

        self.vBoxLayout.addWidget(self.contentWidget)

        self._card_count = 0

    def addWidget(self, widget):
        """添加接口按钮到卡片"""
        self.flowLayout.addWidget(widget)
        self._card_count += 1

    def removeWidget(self, widget):
        """从卡片移除接口按钮"""
        self.flowLayout.removeWidget(widget)
        self._card_count = max(0, self._card_count - 1)

    def get_card_count(self):
        return self._card_count


# ==========================================
# 接收拖拽的区域组件
# ==========================================

class ApiDropZone(QFrame, Base):
    """
    支持拖拽放置的区域，用于设置 Translate 或 Polish 接口
    """
    apiDropped = pyqtSignal(str)
    clearClicked = pyqtSignal()

    def __init__(self, title: str, icon: FluentIcon, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(60)
        
        self._current_api_name = None  # 用于记录当前设置的API名称，方便样式恢复
        
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(20, 12, 24, 12)
        self.h_layout.setSpacing(16)

        # 1. 左侧图标
        self.icon_widget = IconWidget(icon, self)
        self.icon_widget.setFixedSize(32, 32)
        self.h_layout.addWidget(self.icon_widget)

        # 2. 左侧文本区域 (标题 + 状态说明)
        self.text_container = QWidget()
        self.v_text_layout = QVBoxLayout(self.text_container)
        self.v_text_layout.setContentsMargins(0, 0, 0, 0)
        self.v_text_layout.setSpacing(4)
        self.v_text_layout.setAlignment(Qt.AlignVCenter)

        # 标题
        self.title_label = StrongBodyLabel(title, self)
        self.v_text_layout.addWidget(self.title_label)

        # 状态/辅助文字
        self.status_label = CaptionLabel(self.tra("暂未配置"), self)
        self.v_text_layout.addWidget(self.status_label)

        self.h_layout.addWidget(self.text_container)

        # 3. 中间弹簧
        self.h_layout.addStretch(1)

        # 4. 右侧 API 名称显示
        self.api_name_label = StrongBodyLabel(self.tra("拖拽接口到此处"), self)
        self.api_name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.h_layout.addWidget(self.api_name_label)
        
        # 5. 右侧弹簧
        self.h_layout.addStretch(1)

        # 初始化样式
        self._set_default_style()

    def _set_default_style(self):
        """设置未配置时的默认样式（虚线灰框）"""
        self.setStyleSheet("""
            ApiDropZone {
                background-color: rgba(255, 255, 255, 0.05);
                border: 2px dashed rgba(128, 128, 128, 0.3);
                border-radius: 10px;
            }
            ApiDropZone:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border: 2px dashed rgba(128, 128, 128, 0.6);
            }
        """)
        self.status_label.setText(self.tra("暂未配置"))
        self.status_label.setStyleSheet("color: rgba(128, 128, 128, 0.8);")

    def _set_active_style(self):
        """设置已配置时的样式（实线主题色框）"""
        t_color = themeColor()
        self.setStyleSheet(f"""
            ApiDropZone {{
                background-color: rgba(100, 180, 255, 0.08);
                border: 2px solid {t_color.name()};
                border-radius: 10px;
            }}
        """)
        self.status_label.setText(self.tra("正在使用中"))
        self.status_label.setStyleSheet(f"color: {t_color.name()};")

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            # 拖拽进入时的高亮样式
            self.setStyleSheet("""
                ApiDropZone {
                    background-color: rgba(100, 180, 255, 0.15);
                    border: 2px dashed rgba(100, 180, 255, 0.9);
                    border-radius: 10px;
                }
            """)
            e.accept()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        # 拖拽离开时，恢复之前的状态
        self.set_api_info(self._current_api_name)

    def dropEvent(self, e):
        tag = e.mimeData().text()
        self.apiDropped.emit(tag)
        e.accept()

    def set_api_info(self, name: str):
        """ 设置拖放区显示的接口名称并更新样式 """
        self._current_api_name = name
        
        if name:
            self.api_name_label.setText(name)
            self._set_active_style()
        else:
            self.api_name_label.setText(self.tra("拖拽接口到此处"))
            self._set_default_style()


# ==========================================
# 底部设置卡片
# ==========================================

class BottomSettingCard(CardWidget, Base):
    """界面底部的操作区域"""
    addClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(16)

        # 1. 翻译接口放置区
        self.trans_zone = ApiDropZone(self.tra("翻译接口"), FluentIcon.EXPRESSIVE_INPUT_ENTRY, self)
        self.layout.addWidget(self.trans_zone, 1)

        # 2. 润色接口放置区
        self.polish_zone = ApiDropZone(self.tra("润色接口"), FluentIcon.BRUSH, self)
        self.layout.addWidget(self.polish_zone, 1)

        # 3. 分割线
        line = VerticalSeparator(self)
        self.layout.addWidget(line)

        # 4. 添加接口按钮
        self.add_btn = PrimaryPushButton(self.tra("添加接口"), self)
        self.add_btn.setIcon(FluentIcon.ADD)
        self.add_btn.setFixedSize(130, 50)
        self.add_btn.clicked.connect(self.addClicked.emit)
        self.layout.addWidget(self.add_btn)


# ==========================================
# 主页面类
# ==========================================

class PlatformPage(QFrame, Base):

    # 分组配置：添加图标和描述
    GROUP_CONFIG = {
        "local": {
            "title_key": "本地接口",
            "description": "本地部署的模型接口",
            "icon": FluentIcon.CONNECT,
            "order": 0
        },
        "online": {
            "title_key": "官方接口",
            "description": "官方平台提供的在线接口",
            "icon": FluentIcon.CLOUD,
            "order": 1
        },
        "custom": {
            "title_key": "自定义接口",
            "description": "第三方或自定义配置的接口",
            "icon": FluentIcon.ASTERISK,
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
        self.api_buttons = {}
        self.group_cards = {}

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 0, 24, 20)
        main_layout.setSpacing(12)

        # 1. 上半部分：内容容器 (存放分组卡片和空状态提示)
        self.content_container = QWidget()
        self.content_container.setStyleSheet("QWidget { background: transparent; }")
        self.container = QVBoxLayout(self.content_container)
        self.container.setSpacing(16)
        self.container.setContentsMargins(4, 16, 4, 16)

        main_layout.addWidget(self.content_container, 1)

        # 2. 底部部分：设置卡片
        self.bottom_card = BottomSettingCard(self)
        self.bottom_card.addClicked.connect(self.on_add_api_clicked)
        self.bottom_card.trans_zone.apiDropped.connect(lambda t: self.on_api_dropped(t, "translate"))
        self.bottom_card.polish_zone.apiDropped.connect(lambda t: self.on_api_dropped(t, "polish"))

        main_layout.addWidget(self.bottom_card)

        # 创建空状态提示组件（初始隐藏）
        self._create_empty_hint_widget()

        # 加载配置
        config = self.save_config(self.load_config_from_default())

        # 创建分组卡片并填充接口
        self._create_group_cards()
        self._populate_api_cards(config)

        # 初始化底部卡片状态
        self._refresh_bottom_zones(config)

        self.subscribe(Base.EVENT.API_TEST_DONE, self.api_test_done)

        # 初始化完成后更新可见性
        self._update_visibility()

        # 添加底部弹性空间，让卡片保持在顶部
        self.container.addStretch(1)

    def _create_empty_hint_widget(self):
        """创建空状态提示组件"""
        self.empty_hint_widget = QWidget()
        self.empty_hint_widget.setStyleSheet("QWidget { background: transparent; }")

        hint_layout = QVBoxLayout(self.empty_hint_widget)
        hint_layout.setContentsMargins(0, 60, 0, 60)
        hint_layout.setSpacing(20)
        hint_layout.setAlignment(Qt.AlignCenter)

        # 标题
        title_label = SubtitleLabel(self.tra("暂无接口"))
        title_label.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(title_label)

        # 副标题
        subtitle_label = BodyLabel(self.tra("点击底部的「添加接口」按钮创建您的第一个接口"))
        subtitle_label.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(subtitle_label)

        self.empty_hint_widget.hide()
        self.container.addWidget(self.empty_hint_widget)

    def _create_group_cards(self):
        """创建所有分组卡片"""
        sorted_groups = sorted(
            self.GROUP_CONFIG.keys(),
            key=lambda g: self.GROUP_CONFIG[g]["order"]
        )

        for group_name in sorted_groups:
            config = self.GROUP_CONFIG[group_name]
            card = APITypeCard(
                title=self.tra(config["title_key"]),
                icon=config["icon"],
                description=self.tra(config.get("description", "")),
                parent=self
            )
            self.group_cards[group_name] = card
            self.container.addWidget(card)

    def _populate_api_cards(self, config):
        """填充接口按钮到对应的分组卡片"""
        platforms = config.get("platforms", {})

        # 按分组整理
        grouped_platforms = {"local": [], "online": [], "custom": []}
        for tag, api_data in platforms.items():
            group = api_data.get("group", "custom")
            if group not in grouped_platforms:
                group = "custom"
            grouped_platforms[group].append((tag, api_data))

        # 按名称排序后添加到卡片
        for group_name, items in grouped_platforms.items():
            items.sort(key=lambda x: x[1].get("name", ""))
            for tag, api_data in items:
                self.add_api_card(tag, api_data)

    def _update_visibility(self):
        """更新分组卡片和空状态提示的可见性"""
        total_cards = len(self.api_buttons)

        # 更新每个分组卡片的可见性
        for group_name, card in self.group_cards.items():
            if card.get_card_count() > 0:
                card.show()
            else:
                card.hide()

        # 更新空状态提示
        if total_cards == 0:
            self.empty_hint_widget.show()
        else:
            self.empty_hint_widget.hide()

    def _refresh_bottom_zones(self, config=None):
        """根据配置刷新底部拖放区的显示"""
        if config is None:
            config = self.load_config()

        api_settings = config.get("api_settings", {})
        platforms = config.get("platforms", {})

        # 更新翻译区
        trans_tag = api_settings.get("translate")
        if trans_tag and trans_tag in platforms:
            name = platforms[trans_tag].get("name", trans_tag)
            self.bottom_card.trans_zone.set_api_info(name)
        else:
            self.bottom_card.trans_zone.set_api_info(None)

        # 更新润色区
        polish_tag = api_settings.get("polish")
        if polish_tag and polish_tag in platforms:
            name = platforms[polish_tag].get("name", polish_tag)
            self.bottom_card.polish_zone.set_api_info(name)
        else:
            self.bottom_card.polish_zone.set_api_info(None)

    def on_api_dropped(self, tag: str, target_type: str):
        """处理拖拽释放事件"""
        config = self.load_config()
        if "api_settings" not in config:
            config["api_settings"] = {}

        platforms = config.get("platforms", {})
        if tag not in platforms:
            return

        config["api_settings"][target_type] = tag
        self.save_config(config)

        self._refresh_bottom_zones(config)

        action_name = "翻译" if target_type == "translate" else "润色"

        # 拆分一下toast内容，方便翻译
        api_name = platforms[tag].get('name', '')
        info_name = self.tra(action_name)
        info_text = self.tra("已设置") + info_name + self.tra("接口")+ ': '+ api_name 
        self.success_toast("", info_text)

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

        # 检查是否正在被使用
        api_settings = config.get("api_settings", {})
        refresh_bottom = False
        if api_settings.get("translate") == tag:
            api_settings["translate"] = None
            refresh_bottom = True
        if api_settings.get("polish") == tag:
            api_settings["polish"] = None
            refresh_bottom = True

        del config["platforms"][tag]
        self.save_config(config)

        if tag in self.api_buttons:
            btn = self.api_buttons.pop(tag)

            # 获取该卡片所属的分组名称
            group_name = btn.api_data.get("group", "custom")
            if group_name not in self.group_cards:
                group_name = "custom"

            # 从分组卡片中移除
            if group_name in self.group_cards:
                self.group_cards[group_name].removeWidget(btn)

            btn.deleteLater()
            self.success_toast("", self.tra("接口已删除"))

            self._update_visibility()

            if refresh_bottom:
                self._refresh_bottom_zones()

    def show_api_edit_page(self, key: str):
        APIEditPage(self.window, key).exec()
        self.refresh_card(key)

    def show_args_edit_page(self, key: str):
        ArgsEditPage(self.window, key).exec()

    def show_limit_edit_page(self, key: str):
        LimitEditPage(self.window, key).exec()
        self.refresh_card(key)

    def refresh_card(self, tag: str):
        """刷新按钮和底部区域信息"""
        if tag in self.api_buttons:
            config = self.load_config()
            api_data = config.get("platforms", {}).get(tag, {})
            if api_data:
                self.api_buttons[tag].update_info(api_data)
                self._refresh_bottom_zones(config)

    def on_add_api_clicked(self):
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})

        def on_confirm(data):
            self.create_new_api(data)

        dialog = AddAPIDialog(self.window, preset_platforms, on_confirm=on_confirm)
        dialog.exec()

    def create_new_api(self, data: dict):
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

        if "platforms" not in config:
            config["platforms"] = {}

        config["platforms"][tag] = new_platform
        self.save_config(config)

        self.add_api_card(tag, new_platform)
        self.success_toast("", self.tra("接口添加成功"))
        self._update_visibility()

    def add_api_card(self, tag: str, api_data: dict):
        """添加接口按钮到对应的分组卡片"""
        btn = APIItemCard(tag, api_data, self)

        btn.testClicked.connect(self.api_test)
        btn.editClicked.connect(self.show_api_edit_page)
        btn.editLimitClicked.connect(self.show_limit_edit_page)
        btn.editArgsClicked.connect(self.show_args_edit_page)
        btn.deleteClicked.connect(self.delete_platform)

        self.api_buttons[tag] = btn

        group = api_data.get("group", "custom")
        if group not in self.group_cards:
            group = "custom"

        # 添加到对应的分组卡片
        if group in self.group_cards:
            self.group_cards[group].addWidget(btn)