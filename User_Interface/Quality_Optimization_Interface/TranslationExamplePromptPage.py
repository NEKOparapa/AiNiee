
import os
import json

import openpyxl
from rich import print
from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QTableWidgetItem

from qfluentwidgets import Action
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition
from qfluentwidgets import CommandBar
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import TableWidget

from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard

class TranslationExamplePromptPage(QFrame):
    
    DEFAULT = {
        "translation_example_switch": True,
        "translation_example": {
            "結婚前日、目の前の婚約者はそう言った。": "婚前一日，其婚約者前，如是云。",
        },
    }

    def __init__(self, text: str, parent = None, configurator = None):
        super().__init__(parent = parent)

        self.setObjectName(text.replace(" ", "-"))
        self.configurator = configurator

        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_header(self.container, config)
        self.add_widget_body(self.container, config)
        self.add_widget_footer(self.container, config, parent)

    # 载入配置文件
    def load_config(self) -> dict:
        config = {}

        if os.path.exists(os.path.join(self.configurator.resource_dir, "config.json")):
            with open(os.path.join(self.configurator.resource_dir, "config.json"), "r", encoding = "utf-8") as reader:
                config = json.load(reader)
        
        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:
        path = os.path.join(self.configurator.resource_dir, "config.json")
        
        # 读取配置文件
        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                old = json.load(reader)
        else:
            old = {}

        # 修改配置文件中的条目：如果条目存在，这更新值，如果不存在，则设置默认值
        for k, v in self.DEFAULT.items():
            if not k in new.keys():
                old[k] = v
            else:
                old[k] = new[k]

        # 写入配置文件
        with open(path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(old, indent = 4, ensure_ascii = False))

        return old

    # 头部
    def add_widget_header(self, parent, config):
        def widget_init(widget):
            widget.setChecked(config.get("translation_example_switch"))
            
        def widget_callback(widget, checked: bool):
            config["translation_example_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "自定义翻译风格示例", 
                "启用此功能后，将根据本页中设置的信息构建提示词向模型发送请求，建议在逻辑能力强的模型上启用（不支持 Sakura 模型）",
                widget_init,
                widget_callback,
            )
        )

    # 主体
    def add_widget_body(self, parent, config):
        self.table = TableWidget(self)
        parent.addWidget(self.table)

        # 启用边框并设置圆角
        self.table.setBorderRadius(4)
        self.table.setBorderVisible(True)

        self.table.setWordWrap(False)
        self.table.setRowCount(12)
        self.table.setColumnCount(2)
        self.table.resizeRowsToContents() # 设置行高度自适应内容
        self.table.resizeColumnsToContents() # 设置列宽度自适应内容
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # 撑满宽度

        # 设置水平表头并隐藏垂直表头
        self.table.verticalHeader().hide()
        self.table.setHorizontalHeaderLabels([
            "原文",
            "译文",
        ])

        # 向表格更新数据
        self.update_to_table(self.table, config)

    # 底部
    def add_widget_footer(self, parent, config, window):
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)
        
        # 添加命令
        self.add_command_bar_action_01(self.command_bar_card)
        self.add_command_bar_action_02(self.command_bar_card)
        self.command_bar_card.addSeparator()
        self.add_command_bar_action_03(self.command_bar_card)
        self.add_command_bar_action_04(self.command_bar_card, window)

    # 向表格更新数据
    def update_to_table(self, table, config):
        datas = []
        dictionary = config.get("translation_example", {})
        table.setRowCount(max(12, len(dictionary)))
        for k, v in dictionary.items():
            datas.append(
                [
                    k.strip(),
                    v.strip(),
                ]
            )
        for row, data in enumerate(datas):
            for col, v in enumerate(data):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)

    # 从表格更新数据
    def update_from_table(self, table, config):
        config["translation_example"] = {}
        
        for row in range(table.rowCount()):
            data_0 = table.item(row, 0)
            data_1 = table.item(row, 1)

            # 判断是否有数据
            if data_0 == None or data_1 == None:
                continue
            
            data_0 = data_0.text().strip()
            data_1 = data_1.text().strip()

            # 判断是否有数据
            if data_0 == "" or data_1 == "":
                continue

            config["translation_example"][data_0] = data_1

        return config

    # 添加新行
    def add_command_bar_action_01(self, parent):
        def callback():
            # 添加新行
            self.table.setRowCount(self.table.rowCount() + 1)

            # 弹出提示
            InfoBar.success(
                title = "",
                content = "新行已添加 ...",
                parent = self,
                duration = 2000,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

        parent.addAction(
            Action(FluentIcon.ADD_TO, "添加新行", parent, triggered = callback),
        )

    # 移除空行
    def add_command_bar_action_02(self, parent):
        def callback():
            # 从表格更新数据，生成一个临时的配置文件
            config = self.update_from_table(self.table, {})

            # 清空表格
            self.table.clearContents()

            # 向表格更新数据
            self.update_to_table(self.table, config)

            # 弹出提示
            InfoBar.success(
                title = "",
                content = "空行已移除 ...",
                parent = self,
                duration = 2000,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

        parent.addAction(
            Action(FluentIcon.BROOM, "移除空行", parent, triggered = callback),
        )

    # 保存
    def add_command_bar_action_03(self, parent):
        def callback():
            # 读取配置文件
            config = self.load_config()

            # 从表格更新数据
            config = self.update_from_table(self.table, config)

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            InfoBar.success(
                title = "",
                content = "数据已保存 ...",
                parent = self,
                duration = 2000,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

        parent.addAction(
            Action(FluentIcon.SAVE, "保存", parent, triggered = callback),
        )
        
    # 重置
    def add_command_bar_action_04(self, parent, window):
        def callback():
            message_box = MessageBox("警告", "是否确认重置为默认数据 ... ？", window)
            message_box.yesButton.setText("确认")
            message_box.cancelButton.setText("取消")

            if not message_box.exec():
                return

            # 清空表格
            self.table.clearContents()

            # 读取配置文件
            config = self.load_config()

            # 加载默认设置
            for k, v in self.DEFAULT.items():
                config[k] = v

            # 保存配置文件
            config = self.save_config(config)

            # 向表格更新数据
            self.update_to_table(self.table, config)

            # 弹出提示
            InfoBar.success(
                title = "",
                content = "数据已重置 ...",
                parent = self,
                duration = 2000,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

        parent.addAction(
            Action(FluentIcon.DELETE, "重置", parent, triggered = callback),
        )