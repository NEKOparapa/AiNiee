import uuid
from PyQt5.QtWidgets import ( QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame)
from PyQt5.QtCore import Qt,  pyqtSignal
from qfluentwidgets import CaptionLabel, CardWidget, FluentWindow, HorizontalSeparator, IconWidget, LineEdit, MessageBoxBase, PrimaryPushButton, PushButton as FluentPushButton, ScrollArea, StrongBodyLabel, TextEdit, FluentIcon

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin

# 提取提示词卡片 (复用 PromptCard 逻辑)
class ExtractionPromptCard(ConfigMixin, Base, CardWidget):
    prompt_selected = pyqtSignal(dict) # 信号：提示词卡片被点击
    delete_requested = pyqtSignal(str) # 信号：请求删除提示词
    edit_requested = pyqtSignal(dict) # 信号：请求编辑提示词

    def __init__(self, prompt_data, parent=None):
        super().__init__(parent)
        self.prompt_data = prompt_data
        self.is_system = prompt_data.get("type") == "system"
        self.setObjectName("ExtractionPromptCard")
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

    def set_default_style(self):
        self.setStyleSheet("")

    def set_selected_style(self):
        self.setStyleSheet(f"""
            ExtractionPromptCard#ExtractionPromptCard {{
                border: 2px solid #0078D4; /* 蓝色边框 */
                background-color: rgba(0, 120, 212, 0.1); /* 半透明背景 */
                border-radius: 8px;
            }}
        """)

    def on_delete_requested(self):
        self.delete_requested.emit(self.prompt_data["id"])

    def on_edit_requested(self):
        self.edit_requested.emit(self.prompt_data)

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
class AddEditExtractionPromptDialog(ConfigMixin, Base, MessageBoxBase):
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

        self.widget.setMinimumWidth(900)
        self.widget.setMinimumHeight(600)

        name_label = StrongBodyLabel(self.tra("卡片名称:"), container)
        self.name_edit = LineEdit(container)
        if self.is_edit_mode:
            self.name_edit.setText(self.prompt_data["name"])

        content_label = StrongBodyLabel(self.tra("提示词内容 (请确保大模型输出的 JSON 结构包含 characters, terms, non_translate):"), container)
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

# 提取提示词主界面
class ExtractionSystemPromptPage(QFrame, ConfigMixin, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "extraction_prompt_selection": {"last_selected_id": "extraction_academic", "prompt_content": ""},
            "extraction_user_prompt_data": [],
        }

        # 载入并合并配置
        config = self.save_config(self.load_config_from_default())

        # 重新加载
        config = self.load_config()

        # 获取用户配置
        self.default_prompt = self.get_default_prompt(config)
        selected_prompt = config.get("extraction_prompt_selection", {})
        self.user_prompts = config.get("extraction_user_prompt_data", [])
        self.all_prompts = self.default_prompt + self.user_prompts
        last_selected_id = selected_prompt.get("last_selected_id", "")

        # 组装界面并初步显示
        self.init_ui()
        self.update_prompt_cards()

        # 恢复上次选择
        self.selected_prompt_card = None
        initial_prompt_to_display = None

        if last_selected_id:
            for p in self.all_prompts:
                if p['id'] == last_selected_id:
                    initial_prompt_to_display = p
                    break
        
        if not initial_prompt_to_display and self.all_prompts:
            initial_prompt_to_display = self.all_prompts[0]
            
        if initial_prompt_to_display:
            self.display_prompt_details(initial_prompt_to_display)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 10, 0, 0) 

        # 顶部卡片
        self.top_display_card = CardWidget(self)
        top_card_layout = QVBoxLayout(self.top_display_card)
        top_card_layout.setContentsMargins(20, 15, 20, 15)
        top_card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        pin_icon = IconWidget(FluentIcon.PIN, self.top_display_card)
        pin_icon.setFixedSize(18, 18)
        
        title_label = StrongBodyLabel(self.tra("当前提取提示词"), self.top_display_card)

        header_layout.addWidget(pin_icon)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        top_card_layout.addLayout(header_layout)

        top_card_layout.addWidget(HorizontalSeparator())

        name_layout = QHBoxLayout()
        name_label_title = StrongBodyLabel(self.tra("名称："), self.top_display_card)
        self.selected_prompt_name_label = StrongBodyLabel("")
        name_layout.addWidget(name_label_title)
        name_layout.addWidget(self.selected_prompt_name_label)
        name_layout.addStretch(1)
        top_card_layout.addLayout(name_layout)
        
        self.selected_prompt_content_text = TextEdit()
        self.selected_prompt_content_text.setReadOnly(True)
        self.selected_prompt_content_text.setMinimumHeight(200)

        top_card_layout.addWidget(self.selected_prompt_content_text)
        main_layout.addWidget(self.top_display_card, 1)

        # 底部卡片
        self.bottom_grid_card = CardWidget(self)
        bottom_card_layout = QVBoxLayout(self.bottom_grid_card)
        bottom_card_layout.setContentsMargins(20, 15, 20, 15)
        bottom_card_layout.setSpacing(12)

        bottom_header_layout = QHBoxLayout()
        card_square_label = StrongBodyLabel(self.tra("提示词广场"))
        bottom_header_layout.addWidget(card_square_label)
        bottom_header_layout.addStretch(1)
        self.add_new_prompt_button = PrimaryPushButton(FluentIcon.ADD, self.tra("创建新提示词"), self)
        self.add_new_prompt_button.clicked.connect(self.open_add_prompt_dialog)
        bottom_header_layout.addWidget(self.add_new_prompt_button)
        bottom_card_layout.addLayout(bottom_header_layout)

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

    # 获取系统预设提取提示词
    def get_default_prompt(self, config):
        academic_prompt_content = (
            "你是一个专业的科技文献与学术文本分析专家。你的唯一任务是从给定的文本中提取出：研究人员/科学家名字、学术专有名词（术语）以及不需要翻译的代码/标记/公式。\n"
            "【严格执行以下规则】\n"
            "1. 原样提取：提取的 `source` 必须与原文一字不差，绝对不要修改大小写或标点。\n"
            "2. 拒绝脑补：只提取文本中实际出现的实体，不要联想或创造。\n"
            "3. 尽可能多提：请尽量提取出所有对保持专业翻译一致性、双语对齐有帮助的专业术语、行业词汇、高频词及特定名词，宁多勿漏。\n"
            "4. 缩写规范：对于提取出的包含英文缩写（如 SAD, MAD, CNN, FDA 等）的术语，其推荐译名 `recommended_translation` 必须直接保留其英文缩写本身，或采用公认的最简学术汉译。严禁将其脑补并还原翻译为非缩写的英文长句全称（例如：`SAD` 对应的推荐译名应当直接填 `SAD`，严禁脑补翻译为 `Sum of Absolute Differences` 类似全称）。\n"
            "5. 分类规范：\n"
            "   - characters(角色): 文本中出现的重要人物姓名（如科学家、研究人员、历史人物等）。gender 属性可填男性/女性，如果不适用或不明确则留空。\n"
            "   - terms(术语): 学术名词、核心概念、技术指标、算法/模型名、物理/化学/生物实体、专业缩写、学术机构等。category_path 建议分类: 算法/模型/核心概念/学术名词/机构/专业缩写/化学物质/物理量/其他。\n"
            "   - non_translate(不翻译项): 必须保留的机器代码、Latex控制符、占位符、变量名或独立数学公式（如 $L_{loss}$）。category 建议分类: 数学公式/代码/变量/标签/占位符/控制符/其他。\n"
            "【输出格式】\n"
            "必须输出合法的 JSON 代码块，严格遵守以下结构：\n"
            "```json\n"
            "{\n"
            "  \"characters\": [{\"source\": \"原文\", \"recommended_translation\": \"推荐译名\", \"gender\": \"\", \"note\": \"\"}],\n"
            "  \"terms\": [{\"source\": \"原文\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"\", \"note\": \"\"}],\n"
            "  \"non_translate\": [{\"marker\": \"代码或标记\", \"category\": \"\", \"note\": \"\"}]\n"
            "}\n"
            "```"
        )

        game_prompt_content = (
            "你是一个专业的游戏与本地化文本分析专家。你的唯一任务是从给定的文本中提取出：角色名、专有名词（术语）以及不需要翻译的代码/标记。\n"
            "【严格执行以下规则】\n"
            "1. 原样提取：提取的 `source` 必须与原文一字不差，绝对不要修改大小写或标点。\n"
            "2. 拒绝脑补：只提取文本中实际出现的实体，不要联想或创造。\n"
            "3. 宁缺毋滥：对于普通词汇（如“苹果”、“跑”、“明天”），不要提取。如果没有值得提取的内容，返回空列表。\n"
            "4. 分类规范：\n"
            "   - characters(角色): 文本中出现的具体人物、怪物、神明等名字。gender 建议分类: 男性/女性/其他。\n"
            "   - terms(术语): 身份称谓、地名、组织、物品名、技能名、种族名、独特概念、游戏机制、特殊动词/形容词、概念性短语等。category_path 建议分类: 身份/物品/组织/地名/技能/种族/游戏机制/特殊属性/动作/其他。\n"
            "   - non_translate(不翻译项): 必须保留的机器代码，如 HTML标签(<b>)、占位符(%s)、变量({{name}})。category 建议分类: 标签/变量/占位符/标记符/转义控制符/资源标识/数值公式/其他。\n"
            "【输出格式】\n"
            "必须输出合法的 JSON 代码块，严格遵守以下结构：\n"
            "```json\n"
            "{\n"
            "  \"characters\": [{\"source\": \"原文\", \"recommended_translation\": \"推荐译名\", \"gender\": \"\", \"note\": \"\"}],\n"
            "  \"terms\": [{\"source\": \"原文\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"\", \"note\": \"\"}],\n"
            "  \"non_translate\": [{\"marker\": \"代码或标记\", \"category\": \"\", \"note\": \"\"}]\n"
            "}\n"
            "```"
        )

        return [
            {
                "id": "extraction_academic",
                "name": self.tra("学术文献模式 (默认)"),
                "content": academic_prompt_content,
                "type": "system"
            },
            {
                "id": "extraction_game",
                "name": self.tra("通用游戏小说"),
                "content": game_prompt_content,
                "type": "system"
            }
        ]

    def save_last_selection(self, prompt_id, prompt_content):
        config = self.load_config()
        config["extraction_prompt_selection"] = {"last_selected_id": prompt_id, "prompt_content": prompt_content}
        self.save_config(config)

    def save_user_prompts(self):
        config = self.load_config()
        config["extraction_user_prompt_data"] = self.user_prompts
        self.save_config(config)

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())

    def update_prompt_cards(self):
        self.clear_layout(self.card_grid_layout)
        self.all_prompts = self.default_prompt + self.user_prompts

        prompts_to_display = self.all_prompts[:]
        num_cols = 3
        row, col = 0, 0
        for i, prompt_data in enumerate(prompts_to_display):
            card = ExtractionPromptCard(prompt_data)
            card.prompt_selected.connect(self.display_prompt_details)

            if prompt_data.get("type") != "system":
                card.delete_requested.connect(self.delete_user_prompt)
                card.edit_requested.connect(self.handle_edit_request)

            self.card_grid_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

    def find_card_widget(self, prompt_id):
        for i in range(self.card_grid_layout.count()):
            item = self.card_grid_layout.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, ExtractionPromptCard) and widget.prompt_data["id"] == prompt_id:
                    return widget
        return None
    
    def highlight_card(self, card_to_highlight_widget):
        if self.selected_prompt_card and self.selected_prompt_card != card_to_highlight_widget:
            self.selected_prompt_card.set_default_style()

        if card_to_highlight_widget:
            card_to_highlight_widget.set_selected_style()
            self.selected_prompt_card = card_to_highlight_widget
        else:
            self.selected_prompt_card = None

    def display_prompt_details(self, prompt_data):
        self.selected_prompt_name_label.setText(f"{prompt_data['name']}")
        self.selected_prompt_content_text.setPlainText(prompt_data['content'])

        card_widget_to_select = self.find_card_widget(prompt_data["id"])
        self.highlight_card(card_widget_to_select)

        self.save_last_selection(prompt_data['id'], prompt_data['content'])

    def handle_edit_request(self, prompt_data_to_edit):
        self.open_add_prompt_dialog(prompt_data_to_edit)

    def open_add_prompt_dialog(self, prompt_to_edit=None):
        actual_prompt_to_edit = prompt_to_edit
        if isinstance(prompt_to_edit, bool) and not prompt_to_edit:
            actual_prompt_to_edit = None

        dialog = AddEditExtractionPromptDialog(actual_prompt_to_edit, self)

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
