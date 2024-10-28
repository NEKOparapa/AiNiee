from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QTableWidgetItem

from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import TableWidget

from Base.Base import Base
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard

class CharacterizationPromptPage(QFrame, Base):

    DEFAULT = {
        "characterization_switch": False,
        "characterization_dictionary": {
            "遠坂凛": {
                "original_name": "遠坂凛",
                "translated_name": "远坂凛",
                "gender": "女",
                "age": "少女",
                "personality": "高傲，自满",
                "speech_style": "大小姐，严厉",
                "additional_info": "在人前言谈举止高雅，对所有人都用敬语，但在熟人面前本性其实是个爱恶作剧和捉弄自己喜欢的人的小恶魔。"
            },
        },
    }

    # 设置默认值填充模式为普通模式
    DEFAULT_FILL = Base.DEFAULT_FILL
    DEFAULT_FILL.SELECT_MODE = DEFAULT_FILL.MODE_NORMAL

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_header(self.container, config)
        self.add_widget_body(self.container, config)
        self.add_widget_footer(self.container, config, window)

    # 头部
    def add_widget_header(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("characterization_switch"))

        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["characterization_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "自定义角色介绍",
                "启用此功能后，将根据本页中设置的信息构建提示词向模型发送请求，仅在逻辑能力强的模型上有效（不支持 Sakura 模型）",
                widget_init,
                widget_callback,
            )
        )

    # 主体
    def add_widget_body(self, parent, config):

        def item_changed(item):
            item.setTextAlignment(Qt.AlignCenter)

        self.table = TableWidget(self)
        parent.addWidget(self.table)

        # 设置表格属性
        self.table.setBorderRadius(4)
        self.table.setBorderVisible(True)
        self.table.setWordWrap(False)
        self.table.setColumnCount(7)
        self.table.resizeRowsToContents() # 设置行高度自适应内容
        self.table.resizeColumnsToContents() # 设置列宽度自适应内容
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # 撑满宽度
        self.table.itemChanged.connect(item_changed)

        # 设置水平表头并隐藏垂直表头
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setHorizontalHeaderLabels([
            "原名",
            "译名",
            "性别",
            "年龄",
            "性格",
            "说话风格",
            "补充信息",
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
        self.command_bar_card.add_separator()
        self.add_command_bar_action_03(self.command_bar_card)
        self.add_command_bar_action_04(self.command_bar_card, window)

    # 向表格更新数据
    def update_to_table(self, table, config):
        datas = []
        dictionary = config.get("characterization_dictionary", {})

        # 构建表格数据
        for k, v in dictionary.items():
            datas.append(
                [
                    v.get("original_name", "").strip(),
                    v.get("translated_name", "").strip(),
                    v.get("gender", "").strip(),
                    v.get("age", "").strip(),
                    v.get("personality", "").strip(),
                    v.get("speech_style", "").strip(),
                    v.get("additional_info", "").strip(),
                ]
            )

        # 向表格中填充数据
        table.setRowCount(max(12, len(dictionary)))
        for row in range(len(datas)):
            for col in range(table.columnCount()):
                table.setItem(row, col, QTableWidgetItem(datas[row][col]))

    # 从表格更新数据
    def update_from_table(self, table, config):
        config["characterization_dictionary"] = {}

        for row in range(table.rowCount()):
            data_0 = table.item(row, 0)
            data_1 = table.item(row, 1)
            data_2 = table.item(row, 2)
            data_3 = table.item(row, 3)
            data_4 = table.item(row, 4)
            data_5 = table.item(row, 5)
            data_6 = table.item(row, 6)

            # 判断是否有数据
            if data_0 == None:
                continue

            data_0 = data_0.text().strip()
            data_1 = data_1.text().strip() if data_1 != None else ""
            data_2 = data_2.text().strip() if data_2 != None else ""
            data_3 = data_3.text().strip() if data_3 != None else ""
            data_4 = data_4.text().strip() if data_4 != None else ""
            data_5 = data_5.text().strip() if data_5 != None else ""
            data_6 = data_6.text().strip() if data_6 != None else ""

            # 判断是否有数据
            if data_0 == "":
                continue

            config["characterization_dictionary"][data_0] = {
                "original_name": data_0,
                "translated_name": data_1,
                "gender": data_2,
                "age": data_3,
                "personality": data_4,
                "speech_style": data_5,
                "additional_info": data_6,
            }

        return config

    # 添加新行
    def add_command_bar_action_01(self, parent):
        def callback():
            # 添加新行
            self.table.setRowCount(self.table.rowCount() + 1)

            # 弹出提示
            self.success_toast("", "新行已添加 ...")

        parent.add_action(
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

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            self.success_toast("", "空行已移除 ...")

        parent.add_action(
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
            self.success_toast("", "数据已保存 ...")

        parent.add_action(
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
            config["characterization_dictionary"] = self.DEFAULT.get("characterization_dictionary")

            # 保存配置文件
            config = self.save_config(config)

            # 向表格更新数据
            self.update_to_table(self.table, config)

            # 弹出提示
            self.success_toast("", "数据已重置 ...")

        parent.add_action(
            Action(FluentIcon.DELETE, "重置", parent, triggered = callback),
        )