from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import PlainTextEdit

from Base.Base import Base
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard

class FormatReferencePage(QFrame, Base):

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "format_reference_switch": False,
            "format_reference_content": (
"""## 模板参考
1. 此模板覆盖 AI 响应所需**95%+ 的排版场景**
2. 重点优先级：  
   ✅ 代码块 > 表格 > 分段标题  
   ⚠️ 避免复杂嵌套表格
3. 响应长度控制：  
   - 简单问题：1-3 段落  
   - 复杂解答：启用折叠区块

建议搭配以下符号体系：
- ✅ 正确操作  
- ⚠️ 注意事项  
- ❌ 错误示例  
- 💡 进阶技巧"""
            ),
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

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
            widget.set_checked(config.get("format_reference_switch"))

        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["format_reference_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自定义排版参考"),
                self.tra("启用此功能后，将根据本页中设置的内容构建排版参考提示，并补充到基础提示词中"),
                widget_init,
                widget_callback,
            )
        )

    # 主体
    def add_widget_body(self, parent, config):
        self.plain_text_edit = PlainTextEdit(self)
        self.plain_text_edit.setPlainText(config.get("format_reference_content"))
        parent.addWidget(self.plain_text_edit)

    # 底部
    def add_widget_footer(self, parent, config, window):
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        # 添加命令
        self.add_command_bar_action_01(self.command_bar_card)
        self.add_command_bar_action_02(self.command_bar_card, window)
    # 保存
    def add_command_bar_action_01(self, parent):
        def callback():
            # 读取配置文件
            config = self.load_config()

            # 从表格更新数据
            config["format_reference_content"] = self.plain_text_edit.toPlainText().strip()

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            info_cont = self.tra("数据已保存") + " ..."
            self.success_toast("", info_cont)

        parent.add_action(
            Action(FluentIcon.SAVE, self.tra("保存"), parent, triggered = callback),
        )

    # 重置
    def add_command_bar_action_02(self, parent, window):
        def callback():
            info_cont1 = self.tra("是否确认重置为默认数据")  + " ... ？"
            message_box = MessageBox("Warning", info_cont1, window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))

            if not message_box.exec():
                return

            # 清空控件
            self.plain_text_edit.setPlainText("")

            # 读取配置文件
            config = self.load_config()

            # 加载默认设置
            config["format_reference_content"] = self.default.get("format_reference_content")

            # 保存配置文件
            config = self.save_config(config)

            # 向控件更新数据
            self.plain_text_edit.setPlainText(config.get("format_reference_content"))

            # 弹出提示
            info_cont2 = self.tra("数据已重置")  + " ... "
            self.success_toast("", info_cont2)

        parent.add_action(
            Action(FluentIcon.DELETE, self.tra("重置"), parent, triggered = callback),
        )