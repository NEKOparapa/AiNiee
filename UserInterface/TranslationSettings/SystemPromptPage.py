import uuid
from PyQt5.QtWidgets import ( QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame)
from PyQt5.QtCore import Qt,  pyqtSignal
from qfluentwidgets import CaptionLabel, CardWidget, FluentWindow, HorizontalSeparator, IconWidget, LineEdit, MessageBoxBase, PrimaryPushButton, PushButton as FluentPushButton, ScrollArea, StrongBodyLabel, TextEdit, FluentIcon


from Base.Base import Base
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum

# 提示词卡片
class PromptCard(Base,CardWidget):
    prompt_selected = pyqtSignal(dict) # 信号：提示词卡片被点击
    delete_requested = pyqtSignal(str) # 信号：请求删除提示词
    edit_requested = pyqtSignal(dict) # 信号：请求编辑提示词

    def __init__(self, prompt_data, parent=None):
        super().__init__(parent)
        self.prompt_data = prompt_data
        self.is_system = prompt_data.get("type") == "system"
        self.setObjectName("PromptCard")
        self.init_ui()

    def init_ui(self):
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(120)
        self.setMaximumHeight(180)
        self.setMinimumWidth(200)

        main_v_layout = QVBoxLayout(self)
        main_v_layout.setContentsMargins(10, 10, 10, 10)
        main_v_layout.setSpacing(5)

        name_label = StrongBodyLabel(self.prompt_data["name"])
        name_label.setWordWrap(True)

        # 让其自动换行并填充可用空间
        content_preview = CaptionLabel(self.prompt_data["content"][:130] + "...")
        content_preview.setWordWrap(True)

        main_v_layout.addWidget(name_label)
        main_v_layout.addWidget(content_preview)
        main_v_layout.addStretch(1)

        bottom_h_layout = QHBoxLayout()
        bottom_h_layout.setContentsMargins(0, 0, 0, 0)

        if not self.is_system:
            button_container = QHBoxLayout()
            button_container.addStretch(1)

            edit_button = FluentPushButton(self.tra("编辑"))
            edit_button.clicked.connect(self.on_edit_requested)
            edit_button.setFocusPolicy(Qt.NoFocus)
            button_container.addWidget(edit_button)

            delete_button = FluentPushButton(self.tra("删除"))
            delete_button.clicked.connect(self.on_delete_requested)
            delete_button.setFocusPolicy(Qt.NoFocus)
            button_container.addWidget(delete_button)
            bottom_h_layout.addLayout(button_container)
        else:
            bottom_h_layout.addStretch(1)
            system_tag = CaptionLabel(self.tra("系统预设"))
            bottom_h_layout.addWidget(system_tag, alignment=Qt.AlignRight)

        main_v_layout.addLayout(bottom_h_layout)
        self.setAutoFillBackground(True)

    # 设置默认样式
    def set_default_style(self):
        self.setStyleSheet("")

    # 设置选中样式
    def set_selected_style(self):
        self.setStyleSheet(f"""
            PromptCard#PromptCard {{
                border: 2px solid #0078D4; /* 蓝色边框 */
                background-color: rgba(0, 120, 212, 0.1); /* 半透明背景 */
                border-radius: 8px;
            }}
        """)

    # 响应删除请求
    def on_delete_requested(self):
        self.delete_requested.emit(self.prompt_data["id"])

    # 响应编辑请求
    def on_edit_requested(self):
        self.edit_requested.emit(self.prompt_data)

    # 鼠标点击事件处理
    def mousePressEvent(self, event):
        child_widget = self.childAt(event.pos())
        is_on_button = False
        if child_widget:
            parent = child_widget
            while parent is not None:
                if isinstance(parent, FluentPushButton):
                    is_on_button = True
                    break
                parent = parent.parent()

        if not is_on_button and event.button() == Qt.LeftButton:
            self.prompt_selected.emit(self.prompt_data)

# 提示词编辑对话框
class AddEditPromptDialog(Base,MessageBoxBase):
    def __init__(self, prompt_data=None, parent=None):
        super().__init__(parent)
        self.prompt_data = prompt_data
        self.is_edit_mode = prompt_data is not None
        self.init_ui()

        self.yesButton.setText(self.tra('保存'))
        self.cancelButton.setText(self.tra('取消'))

    def init_ui(self):
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        # 调整对话框尺寸
        self.widget.setMinimumWidth(900)
        self.widget.setMinimumHeight(600)

        name_label = StrongBodyLabel(self.tra("卡片名称:"), container)
        self.name_edit = LineEdit(container)
        if self.is_edit_mode:
            self.name_edit.setText(self.prompt_data["name"])

        content_label = StrongBodyLabel(self.tra("提示词内容:"), container)
        self.content_edit = TextEdit(container)

        if self.is_edit_mode:
            self.content_edit.setPlainText(self.prompt_data["content"])

        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(content_label)
        layout.addWidget(self.content_edit)

        self.viewLayout.addWidget(container)

    def get_data(self):
        name = self.name_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        if not name or not content:
            return None

        if self.is_edit_mode:
            return {"id": self.prompt_data["id"], "name": name, "content": content, "type": "user"}
        else:
            return {"id": str(uuid.uuid4()), "name": name, "content": content, "type": "user"}

# 主界面
class SystemPromptPage(QFrame, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "translation_prompt_selection":{"last_selected_id": PromptBuilderEnum.COMMON,"prompt_content": ""},
            "translation_user_prompt_data": [],
        }

        # 载入并合并配置
        config = self.save_config(self.load_config_from_default())

        # 载入配置文件
        config = self.load_config()

        # 获取用户配置
        self.default_prompt = self.get_default_prompt(config)
        selected_prompt = config.get("translation_prompt_selection",{})
        self.user_prompts = config.get("translation_user_prompt_data",[])
        self.all_prompts = self.default_prompt + self.user_prompts
        last_selected_id = selected_prompt.get("last_selected_id","")

        # 组装界面并初步显示
        self.init_ui()
        self.update_prompt_cards()

        # 启动时恢复上次选择
        self.selected_prompt_card = None
        initial_prompt_to_display = None

        # 在所有提示词中查找与保存的ID匹配的项
        if last_selected_id:
            for p in self.all_prompts:
                if p['id'] == last_selected_id:
                    initial_prompt_to_display = p
                    break
        
        # 如果没有找到，则默认显示第一个
        if not initial_prompt_to_display and self.all_prompts:
            initial_prompt_to_display = self.all_prompts[0]
            
        # 如果存在可显示的提示词，则显示它
        if initial_prompt_to_display:
            self.display_prompt_details(initial_prompt_to_display)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 10, 0, 0) 

        # 设置顶部卡片
        self.top_display_card = CardWidget(self)
        top_card_layout = QVBoxLayout(self.top_display_card)
        top_card_layout.setContentsMargins(20, 15, 20, 15)
        top_card_layout.setSpacing(12)

        # 设置顶部卡片标题
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        pin_icon = IconWidget(FluentIcon.PIN, self.top_display_card)
        pin_icon.setFixedSize(18, 18)
        
        title_label = StrongBodyLabel(self.tra("当前提示词"), self.top_display_card)

        header_layout.addWidget(pin_icon)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        top_card_layout.addLayout(header_layout)

        # 添加分割线
        top_card_layout.addWidget(HorizontalSeparator())

        # 设置顶部卡片内容显示
        name_layout = QHBoxLayout()
        name_label_title = StrongBodyLabel(self.tra("名称："), self.top_display_card)
        self.selected_prompt_name_label = StrongBodyLabel("")
        name_layout.addWidget(name_label_title)
        name_layout.addWidget(self.selected_prompt_name_label)
        name_layout.addStretch(1)
        top_card_layout.addLayout(name_layout)
        
        # 设置顶部卡片内容文本框
        self.selected_prompt_content_text = TextEdit()
        self.selected_prompt_content_text.setReadOnly(True)
        self.selected_prompt_content_text.setMinimumHeight(200)
        #self.selected_prompt_content_text.setMaximumHeight(200)

        top_card_layout.addWidget(self.selected_prompt_content_text)
        
        # 将顶部卡片添加到主布局
        main_layout.addWidget(self.top_display_card, 1)

        # 设置底部卡片
        self.bottom_grid_card = CardWidget(self)
        bottom_card_layout = QVBoxLayout(self.bottom_grid_card)
        bottom_card_layout.setContentsMargins(20, 15, 20, 15) # 统一边距风格
        bottom_card_layout.setSpacing(12) # 统一间距风格

        header_layout = QHBoxLayout()
        card_square_label = StrongBodyLabel(self.tra("提示词广场"))
        header_layout.addWidget(card_square_label)
        header_layout.addStretch(1)
        self.add_new_prompt_button =  PrimaryPushButton(FluentIcon.ADD, self.tra("创建新提示词"), self)
        self.add_new_prompt_button.clicked.connect(self.open_add_prompt_dialog)
        header_layout.addWidget(self.add_new_prompt_button)
        bottom_card_layout.addLayout(header_layout)

        self.scroll_area = ScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")

        self.card_container_widget = QWidget()
        self.card_container_widget.setStyleSheet("background-color: transparent;")
        self.card_grid_layout = QGridLayout(self.card_container_widget)
        self.card_grid_layout.setSpacing(15)
        self.card_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.card_container_widget)
        bottom_card_layout.addWidget(self.scroll_area)

        main_layout.addWidget(self.bottom_grid_card, 3)
        self.setLayout(main_layout)

    # 获取系统提示词
    def get_default_prompt(self, config):

        # 获取系统预设提示词内容
        conmon_name = self.tra("通用")
        common_id = PromptBuilderEnum.COMMON
        common_prompt_content = PromptBuilder.get_system_default(config,PromptBuilderEnum.COMMON)

        cot_name = self.tra("思维链")
        cot_id = PromptBuilderEnum.COT
        coT_prompt_content = PromptBuilder.get_system_default(config,PromptBuilderEnum.COT)

        think_name = self.tra("推理模型")
        think_id = PromptBuilderEnum.THINK
        think_prompt_content = PromptBuilder.get_system_default(config,PromptBuilderEnum.THINK)

        # 组装默认提示词列表
        default_prompt = [
            {
                "id": common_id,
                "name": conmon_name,
                "content": common_prompt_content,
                "type": "system"
            },
            {
                "id": cot_id,
                "name": cot_name,
                "content": coT_prompt_content,
                "type": "system"
            },
            {
                "id": think_id,
                "name": think_name,
                "content": think_prompt_content,
                "type": "system"
            }
        ]

        return default_prompt

    # 保存当前选择
    def save_last_selection(self, prompt_id,prompt_content):

        config = self.load_config()
        config["translation_prompt_selection"] = {"last_selected_id": prompt_id,"prompt_content": prompt_content}
        self.save_config(config)

    # 保存新的用户提示词
    def save_user_prompts(self):
        config = self.load_config()
        config["translation_user_prompt_data"] = self.user_prompts
        self.save_config(config)

    # 清楚界面
    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())

    # 更新提示词广场的卡片
    def update_prompt_cards(self):
        self.clear_layout(self.card_grid_layout)
        self.all_prompts = self.default_prompt + self.user_prompts

        prompts_to_display = self.all_prompts[:]

        num_cols = 3
        row, col = 0, 0
        for i, prompt_data in enumerate(prompts_to_display):
            card = PromptCard(prompt_data)
            card.prompt_selected.connect(self.display_prompt_details)

            if prompt_data.get("type") != "system":
                card.delete_requested.connect(self.delete_user_prompt)
                card.edit_requested.connect(self.handle_edit_request)

            self.card_grid_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

    # 查找指定ID的提示词卡片
    def find_card_widget(self, prompt_id):
        for i in range(self.card_grid_layout.count()):
            item = self.card_grid_layout.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, PromptCard) and widget.prompt_data["id"] == prompt_id:
                    return widget
        return None
    
    # 高亮显示指定的提示词卡片
    def highlight_card(self, card_to_highlight_widget):
        if self.selected_prompt_card and self.selected_prompt_card != card_to_highlight_widget:
            self.selected_prompt_card.set_default_style()

        if card_to_highlight_widget:
            card_to_highlight_widget.set_selected_style()
            self.selected_prompt_card = card_to_highlight_widget
        else:
            self.selected_prompt_card = None

    # 显示选中的提示词详情
    def display_prompt_details(self, prompt_data):
        self.selected_prompt_name_label.setText(f"{prompt_data['name']}")
        self.selected_prompt_content_text.setPlainText(prompt_data['content'])

        card_widget_to_select = self.find_card_widget(prompt_data["id"])
        self.highlight_card(card_widget_to_select)

        self.save_last_selection(prompt_data['id'],prompt_data['content'])

    # 处理编辑请求
    def handle_edit_request(self, prompt_data_to_edit):
        self.open_add_prompt_dialog(prompt_data_to_edit)

    # 打开添加或编辑提示词对话框
    def open_add_prompt_dialog(self, prompt_to_edit=None):
        actual_prompt_to_edit = prompt_to_edit
        if isinstance(prompt_to_edit, bool) and not prompt_to_edit:
            actual_prompt_to_edit = None

        dialog = AddEditPromptDialog(actual_prompt_to_edit, self)

        if dialog.exec_():
            data = dialog.get_data()
            if data:
                is_new_prompt = not actual_prompt_to_edit

                if not is_new_prompt and actual_prompt_to_edit:
                    for i, p in enumerate(self.user_prompts):
                        if p["id"] == data["id"]:
                            self.user_prompts[i] = data
                            break
                else:
                    self.user_prompts.append(data)

                self.save_user_prompts()
                self.update_prompt_cards()

                newly_added_or_edited_card_instance = self.find_card_widget(data["id"])
                if newly_added_or_edited_card_instance:
                    self.display_prompt_details(data)
                elif self.all_prompts:
                    self.display_prompt_details(self.all_prompts[0])


    # 删除用户提示词
    def delete_user_prompt(self, prompt_id_to_delete):
        id_of_currently_selected = None
        if self.selected_prompt_card:
            id_of_currently_selected = self.selected_prompt_card.prompt_data["id"]

        self.user_prompts = [p for p in self.user_prompts if p["id"] != prompt_id_to_delete]
        self.save_user_prompts()

        self.update_prompt_cards()

        if id_of_currently_selected == prompt_id_to_delete:
            self.selected_prompt_name_label.setText("")
            self.selected_prompt_content_text.clear()
            self.selected_prompt_card = None
            if self.all_prompts:
                self.display_prompt_details(self.all_prompts[0])
        elif id_of_currently_selected:
            card_to_reselect = self.find_card_widget(id_of_currently_selected)
            if card_to_reselect:
                self.display_prompt_details(card_to_reselect.prompt_data)
            elif self.all_prompts:
                self.display_prompt_details(self.all_prompts[0])
            else:
                self.selected_prompt_name_label.setText("")
                self.selected_prompt_content_text.clear()
                self.selected_prompt_card = None