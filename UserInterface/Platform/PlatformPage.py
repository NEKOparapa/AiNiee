import os
import json
import copy
import random

from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QWidget

from qfluentwidgets import ( PrimaryPushButton, FluentIcon, SingleDirectionScrollArea
)

from Base.Base import Base
from UserInterface.Platform.AddAPIDialog import AddAPIDialog
from UserInterface.Platform.APIItemCard import APIItemCard
from UserInterface.Platform.APIEditPage import APIEditPage
from UserInterface.Platform.ArgsEditPage import ArgsEditPage
from UserInterface.Platform.LimitEditPage import LimitEditPage

class PlatformPage(QFrame, Base):

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "api_settings": {
                "translate": None,
                "polish": None
            }
        }

        self.window = window
        self.api_cards = {}  # 存储所有接口卡片 {api_tag: APIItemCard}

        # 主滚动区域
        self.main_scroll = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("QWidget { background: transparent; }")
        self.container = QVBoxLayout(self.scroll_widget)
        self.container.setSpacing(12)
        self.container.setContentsMargins(24, 24, 24, 24)
        self.main_scroll.setWidget(self.scroll_widget)
        
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_scroll)

        config = self.save_config(self.load_config_from_default())

        # 接口列表区域
        self.add_api_list_widget(self.container, config)

        # 添加底部空白区域，避免悬浮按钮遮挡卡片
        self.bottom_spacer = QWidget()
        self.bottom_spacer.setFixedHeight(100)  # 为悬浮按钮留出空间
        self.bottom_spacer.setStyleSheet("background: transparent;")
        self.container.addWidget(self.bottom_spacer)

        self.container.addStretch(1)
        
        # 创建悬浮添加按钮（在滚动区域之上）
        self.create_floating_add_button()
        
        self.subscribe(Base.EVENT.API_TEST_DONE, self.api_test_done)

    def create_floating_add_button(self):
        """创建悬浮的添加按钮"""
        self.floating_add_btn = PrimaryPushButton(self.tra("添加接口"), self)
        self.floating_add_btn.setIcon(FluentIcon.ADD_TO)
        self.floating_add_btn.setFixedSize(160, 56)
        # 更大字体
        font = self.floating_add_btn.font()
        font.setPointSize(13)
        self.floating_add_btn.setFont(font)

        # 更大的图标
        self.floating_add_btn.setIconSize(QSize(20, 20))

        self.floating_add_btn.clicked.connect(self.on_add_api_clicked)
        
        # 初始位置
        self.update_floating_button_position()
        
        # 延迟刷新样式，解决初始化时样式不显示的问题
        QTimer.singleShot(100, self._refresh_floating_button_style)

    def _refresh_floating_button_style(self):
        """刷新悬浮按钮样式"""
        if hasattr(self, 'floating_add_btn') and self.floating_add_btn:
            # 强制重新应用样式
            self.floating_add_btn.style().unpolish(self.floating_add_btn)
            self.floating_add_btn.style().polish(self.floating_add_btn)
            self.floating_add_btn.update()
            
            # 确保按钮在最上层并可见
            self.floating_add_btn.raise_()
            self.floating_add_btn.show()

    def update_floating_button_position(self):
        """更新悬浮按钮位置"""
        if hasattr(self, 'floating_add_btn'):
            # 放置在右下角，距离边缘一定距离
            margin_right = 40
            margin_bottom = 40
            btn_width = self.floating_add_btn.width()
            btn_height = self.floating_add_btn.height()
            
            x = self.width() - btn_width - margin_right
            y = self.height() - btn_height - margin_bottom
            
            self.floating_add_btn.move(x, y)
            self.floating_add_btn.raise_()  # 确保按钮在最上层

    def resizeEvent(self, event):
        """窗口大小改变时更新悬浮按钮位置"""
        super().resizeEvent(event)
        self.update_floating_button_position()

    def showEvent(self, event):
        """显示时更新悬浮按钮位置并刷新样式"""
        super().showEvent(event)
        self.update_floating_button_position()
        # 显示时也刷新一次样式
        QTimer.singleShot(50, self._refresh_floating_button_style)

    def load_file(self, path: str) -> dict:
        result = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as reader:
                result = json.load(reader)
        else:
            self.error(f"未找到 {path} 文件 ...")
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
            info_cont = self.tra("接口测试结果：成功") + f" {len(data.get('success', []))} " + self.tra("失败") + f" {len(data.get('failure', []))}"
            self.error_toast("", info_cont)
        else:
            info_cont = self.tra("接口测试结果：成功") + f" {len(data.get('success', []))} " + self.tra("失败") + f" {len(data.get('failure', []))}"
            self.success_toast("", info_cont)

    def delete_platform(self, tag: str) -> None:
        config = self.load_config()
        
        # 检查接口是否存在
        if tag not in config.get("platforms", {}):
            self.warning_toast("", self.tra("接口不存在"))
            return
        
        # 检查是否被激活使用，如果是则清除
        api_settings = config.get("api_settings", {})
        if api_settings.get("translate") == tag:
            api_settings["translate"] = None
        if api_settings.get("polish") == tag:
            api_settings["polish"] = None
        
        del config["platforms"][tag]
        self.save_config(config)
        
        # 移除卡片
        if tag in self.api_cards:
            card = self.api_cards.pop(tag)
            card.deleteLater()
            
        self.success_toast("", self.tra("接口已删除"))

    def show_api_edit_page(self, key: str):
        config = self.load_config()
        if key not in config.get("platforms", {}):
            self.warning_toast("", self.tra("接口不存在"))
            return
        APIEditPage(self.window, key).exec()
        self.refresh_card(key)

    def show_args_edit_page(self, key: str):
        config = self.load_config()
        if key not in config.get("platforms", {}):
            self.warning_toast("", self.tra("接口不存在"))
            return
        ArgsEditPage(self.window, key).exec()

    def show_limit_edit_page(self, key: str):
        config = self.load_config()
        if key not in config.get("platforms", {}):
            self.warning_toast("", self.tra("接口不存在"))
            return
        LimitEditPage(self.window, key).exec()
        self.refresh_card(key)

    def refresh_card(self, tag: str):
        """刷新指定卡片的显示"""
        if tag in self.api_cards:
            config = self.load_config()
            api_data = config.get("platforms", {}).get(tag, {})
            if api_data:
                self.api_cards[tag].update_info(api_data)

    def on_add_api_clicked(self):
        """点击添加新接口"""
        # 读取 preset.json 获取所有预设平台
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})
        
        def on_confirm(data):
            self.create_new_api(data)
        
        dialog = AddAPIDialog(self.window, preset_platforms, on_confirm=on_confirm)
        dialog.exec()

    def create_new_api(self, data: dict):
        """创建新接口"""
        config = self.load_config()
        
        # 重新读取 preset.json 以获取纯净的模板数据
        preset_data = self.load_file("./Resource/platforms/preset.json")
        preset_platforms = preset_data.get("platforms", {})
        
        tag = f"custom_{random.randint(100000, 999999)}"
        platform_tag = data.get("platform_tag")
        
        # 基于预设模板创建（无论是 custom 还是 official，都从 preset 中获取基础结构）
        if platform_tag in preset_platforms:
            preset = preset_platforms[platform_tag]
            new_platform = copy.deepcopy(preset)
        else:
            self.error_toast("", self.tra("未找到选定的平台预设"))
            return

        # 更新基础信息
        new_platform["tag"] = tag
        new_platform["group"] = "custom" # 所有用户添加的都被视为 custom 组
        new_platform["name"] = data.get("name")
        new_platform["model"] = data.get("model")

        # 更新用户输入的数据
        if "api_key" in data:
            new_platform["api_key"] = data.get("api_key", "")
        
        if "api_url" in data and data.get("api_url"):
            new_platform["api_url"] = data.get("api_url")
            
        if "api_format" in data:
            new_platform["api_format"] = data.get("api_format")
            
        if "auto_complete" in data:
            new_platform["auto_complete"] = data.get("auto_complete")

        # 处理 Amazon Bedrock 特有字段
        if platform_tag == "amazonbedrock":
            new_platform["region"] = data.get("region", "")
            new_platform["access_key"] = data.get("access_key", "")
            new_platform["secret_key"] = data.get("secret_key", "")
            
        # 确保选定的模型在模型列表中
        if data.get("model") and data.get("model") not in new_platform.get("model_datas", []):
            new_platform["model_datas"].append(data.get("model"))
        
        config["platforms"][tag] = new_platform
        self.save_config(config)
        
        # 添加卡片到界面
        self.add_api_card(tag, new_platform, config.get("api_settings", {}))
        
        self.success_toast("", self.tra("接口添加成功"))

    def add_api_list_widget(self, parent, config):
        """添加接口列表区域"""
        self.api_list_container = QFrame()
        self.api_list_layout = QVBoxLayout(self.api_list_container)
        self.api_list_layout.setContentsMargins(0, 0, 0, 0)
        self.api_list_layout.setSpacing(8)
        
        # 添加所有接口卡片
        platforms = config.get("platforms", {})
        api_settings = config.get("api_settings", {})
        
        for tag, api_data in platforms.items():
            self.add_api_card(tag, api_data, api_settings)
        
        parent.addWidget(self.api_list_container)

    def add_api_card(self, tag: str, api_data: dict, api_settings: dict):
        """添加单个接口卡片"""
        # 确定激活状态
        activate_status = None
        if api_settings.get("translate") == tag:
            activate_status = "translate"
        elif api_settings.get("polish") == tag:
            activate_status = "polish"
        
        card = APIItemCard(tag, api_data, activate_status, self)
        
        # 连接信号
        card.testClicked.connect(self.api_test)
        card.activateChanged.connect(self.on_activate_changed)
        card.editClicked.connect(self.show_api_edit_page)
        card.editLimitClicked.connect(self.show_limit_edit_page)
        card.editArgsClicked.connect(self.show_args_edit_page)
        card.deleteClicked.connect(self.delete_platform)
        
        self.api_cards[tag] = card
        self.api_list_layout.addWidget(card)

    def on_activate_changed(self, api_tag: str, activate_type: str):
        """处理激活状态改变"""
        config = self.load_config()
        
        if "api_settings" not in config:
            config["api_settings"] = {"translate": None, "polish": None}
        
        # 先清除该接口的所有旧状态
        for key in ["translate", "polish"]:
            if config["api_settings"].get(key) == api_tag:
                config["api_settings"][key] = None
        
        # 设置新状态
        if activate_type in ["translate", "polish"]:
            # 清除其他接口的相同状态（确保同一功能只有一个接口激活）
            old_tag = config["api_settings"].get(activate_type)
            if old_tag and old_tag != api_tag and old_tag in self.api_cards:
                self.api_cards[old_tag].set_activate_status(None)
            
            config["api_settings"][activate_type] = api_tag
        
        self.save_config(config)
        
        # 显示提示信息
        if activate_type == "translate":
            self.success_toast("", self.tra("已激活为翻译接口"))
        elif activate_type == "polish":
            self.success_toast("", self.tra("已激活为润色接口"))
        else:
            self.info_toast("", self.tra("已取消激活"))