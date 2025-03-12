import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QWidget, QVBoxLayout
from qfluentwidgets import ( SingleDirectionScrollArea,Action,RoundMenu,FluentIcon as FIF,TransparentDropDownToolButton)
from Base.Base import Base
from DRWidget.DialogueFragmentCard import DialogueFragmentCard
from DRWidget.CenteredDividerCard import CenteredDividerCard
from DRWidget.TestBreakpointCard import TestBreakpointCard
from DRWidget.EndPhaseCard import EndPhaseCard
from DRWidget.ConfigImportExportCard import ConfigImportExportCard

from DRWidget.TranslationExtractionCard.TranslationExtractionCard import TranslationExtractionCard
from DRWidget.TagExtractionCard.TagExtractionCard import TagExtractionCard
from DRWidget.ThoughtExtractionCard.ThoughtExtractionCard import ThoughtExtractionCard
from DRWidget.ResponseExtractionCard.ResponseExtractionCard import ResponseExtractionCard
from DRWidget.GlossaryExtractionCard.GlossaryExtractionCard import GlossaryExtractionCard
from DRWidget.NoTranslateListExtractionCard.NoTranslateListExtractionCard import NoTranslateListExtractionCard
from DRWidget.RegexExtractionCard.RegexExtractionCard import RegexExtractionCard

import uuid

class FlowDesignPage(QFrame, Base):
    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 界面默认配置
        self.default = {
            "flow_design_list": {
                "test_target_breakpoint_position":"0",
                "actual_running_breakpoint_position":"0",
                #"request_a_response_content":"", # 非保存属性，为测试返回数据
                #"request_a_response_think":"",
                #"request_b_response_content":"",
                #"request_b_response_think":"",
                "request_phase_a": [], #卡片全部组件以列表方式存储，单个卡片以字典方式存储，单个卡片有字段：卡片类型，卡片序号，卡片设置
                "extraction_phase": [],
                "request_phase_b": [],
            },
        }


        # 订阅流程测试完成事件
        self.subscribe(Base.EVENT.NEW_PROCESS_DONE, self.process_done_handler)

        self.cards = {}  # 卡片字典用于快速查找

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        # 滚动容器
        self.scroller = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container.addWidget(self.scroller)

        # 垂直布局容器
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24)
        self.scroller.setWidget(self.vbox_parent)



        # 添加测试控件
        self.CenteredDividerCardA1 = CenteredDividerCard(
            title=self.tra('|  第一请求  |'),
            description=self.tra('根据下面对话的构造，进行第一次请求'),
            url='https://github.com/NEKOparapa/AiNiee/wiki/%E5%8F%8C%E5%AD%90%E6%98%9F%E7%BF%BB%E8%AF%91%E4%BB%8B%E7%BB%8D',
            link_text=self.tra('教程')
        )
        self.vbox.addWidget(self.CenteredDividerCardA1)



        # 创建按钮容器
        self.button_container_A = QWidget()
        self.button_container_A.setMinimumHeight(80)  # 设置最小高度
        self.button_layout_A = QHBoxLayout(self.button_container_A)
        self.button_layout_A.setAlignment(Qt.AlignCenter)  # 居中对齐
        self.button_layout_A.setContentsMargins(0, 0, 0, 0)

        # 添加动态插入按钮到专用容器
        self.add_button_A = TransparentDropDownToolButton(FIF.ADD, self)
        self.menu_A = RoundMenu(parent=self)
        self.add_action_A = Action(self.tra("添加对话卡片"))
        self.menu_A.addAction(self.add_action_A)
        self.add_button_A.setMenu(self.menu_A)
        self.button_layout_A.addWidget(self.add_button_A)
        self.add_action_A.triggered.connect(self.add_dialogue_card_A)
        # 将按钮容器添加到布局
        self.vbox.addWidget(self.button_container_A)




        self.TestBreakpointCardE = TestBreakpointCard(
            title=self.tra('|  提取阶段  |'),
            description=self.tra('根据下面提取器的设置，对第一次回复内容并行提取'),
            breakpoint_position= 1  # 添加位置参数
        )
        self.TestBreakpointCardE.tool_button.clicked.connect(
            lambda: self.start_process_test(self.TestBreakpointCardE.breakpoint_position)
        )
        self.vbox.addWidget(self.TestBreakpointCardE)



        # 创建按钮容器
        self.button_container_E = QWidget()
        self.button_container_E.setMinimumHeight(80)  # 设置最小高度
        self.button_layout_E = QHBoxLayout(self.button_container_E)
        self.button_layout_E.setAlignment(Qt.AlignCenter)  # 居中对齐
        self.button_layout_E.setContentsMargins(0, 0, 0, 0)

        # 添加动态插入按钮到专用容器
        self.add_button_E = TransparentDropDownToolButton(FIF.ADD, self)
        self.menu_E = RoundMenu(parent=self)
        self.add_action_E1 = Action(self.tra("译文提取器"))
        self.add_action_E2 = Action(self.tra("回复提取器"))
        self.add_action_E3 = Action(self.tra("思考提取器"))
        self.add_action_E4 = Action(self.tra("标签提取器"))
        self.add_action_E5 = Action(self.tra("正则提取器"))
        self.add_action_E6 = Action(self.tra("术语表提取器"))
        self.add_action_E7 = Action(self.tra("禁翻表提取器"))
        self.menu_E.addAction(self.add_action_E1)
        self.menu_E.addAction(self.add_action_E2)
        self.menu_E.addAction(self.add_action_E3)
        self.menu_E.addAction(self.add_action_E4)
        self.menu_E.addAction(self.add_action_E5)
        self.menu_E.addAction(self.add_action_E6)
        self.menu_E.addAction(self.add_action_E7)
        self.add_button_E.setMenu(self.menu_E)
        self.button_layout_E.addWidget(self.add_button_E)
        # 按钮连接逻辑
        self.add_action_E1.triggered.connect(lambda: self.add_extraction_card("译文提取器"))
        self.add_action_E2.triggered.connect(lambda: self.add_extraction_card("回复提取器"))
        self.add_action_E3.triggered.connect(lambda: self.add_extraction_card("思考提取器"))
        self.add_action_E4.triggered.connect(lambda: self.add_extraction_card("标签提取器"))
        self.add_action_E5.triggered.connect(lambda: self.add_extraction_card("正则提取器"))
        self.add_action_E6.triggered.connect(lambda: self.add_extraction_card("术语表提取器"))
        self.add_action_E7.triggered.connect(lambda: self.add_extraction_card("禁翻表提取器"))
        # 将按钮容器添加到布局
        self.vbox.addWidget(self.button_container_E)



        # 后续原有组件
        self.TestBreakpointCardB = TestBreakpointCard(
            title=self.tra('|  第二请求  |'),
            description=self.tra('根据下面对话的构造，进行第二次请求'),
            breakpoint_position= 2  # 添加位置参数
        )
        self.TestBreakpointCardB.tool_button.clicked.connect(
            lambda: self.start_process_test(self.TestBreakpointCardB.breakpoint_position)
        )
        self.vbox.addWidget(self.TestBreakpointCardB)





        # 创建按钮容器
        self.button_container_B = QWidget()
        self.button_container_B.setMinimumHeight(80)  # 设置最小高度
        self.button_layout_B = QHBoxLayout(self.button_container_B)
        self.button_layout_B.setAlignment(Qt.AlignCenter)  # 居中对齐
        self.button_layout_B.setContentsMargins(0, 0, 0, 0)

        # 添加动态插入按钮到专用容器
        self.add_button_B = TransparentDropDownToolButton(FIF.ADD, self)
        self.menu_B = RoundMenu(parent=self)
        self.add_action_B = Action(self.tra("添加对话卡片"))
        self.menu_B.addAction(self.add_action_B)
        self.add_button_B.setMenu(self.menu_B)
        self.button_layout_B.addWidget(self.add_button_B)
        self.add_action_B.triggered.connect(self.add_dialogue_card_B)
        # 将按钮容器添加到布局
        self.vbox.addWidget(self.button_container_B)


        # 结束阶段后续步骤
        self.TestBreakpointCardG = TestBreakpointCard(
            title=self.tra('|  提取翻译结果  |'),
            description=self.tra('从第二次请求回复内容里以textarea标签提取译文'),
            breakpoint_position= 3  # 添加位置参数
        )
        self.TestBreakpointCardG.tool_button.clicked.connect(
            lambda: self.start_process_test(self.TestBreakpointCardG.breakpoint_position)
        )
        self.vbox.addWidget(self.TestBreakpointCardG)

        # 结束阶段卡片
        self.EndPhaseCard = EndPhaseCard(
            title=self.tra('录入翻译结果'),
            description=self.tra('自动检查翻译结果，并录入到缓存中'),
        )
        self.vbox.addWidget(self.EndPhaseCard)

        # 配置导入导出卡片
        self.ConfigImportExportCard = ConfigImportExportCard()
        self.vbox.addWidget(self.ConfigImportExportCard)
        # 连接导入导出按钮
        self.ConfigImportExportCard.left_button.clicked.connect(self.import_config)
        self.ConfigImportExportCard.right_button.clicked.connect(self.export_config)

        # 填充
        self.vbox.addStretch(1)


        # 载入用户配置合并类默认配置，并重新保存配置
        config = self.save_config(self.load_config_from_default())
        # 同步配置，持久化保存
        self.default["flow_design_list"] = config.get("flow_design_list", {})
        # 初始化完成后，根据用户配置加载卡片
        self.initialize_cards_from_config(self.default["flow_design_list"])  


    def initialize_cards_from_config(self, config):
        """根据配置初始化所有卡片"""
        self._load_dialogue_cards(config.get("request_phase_a", []), "request_phase_a", self.button_container_A)
        self._load_phase_cards(config.get("extraction_phase", []), "extraction_phase", self.button_container_E)
        self._load_dialogue_cards(config.get("request_phase_b", []), "request_phase_b", self.button_container_B)


    def _load_dialogue_cards(self, card_configs, phase_key, button_container):
        """加载对话卡片"""
        for card_data in card_configs:
            card = DialogueFragmentCard(self)
            card.card_id = card_data.get("id", str(uuid.uuid4()))
            settings = card_data.get("settings", {})

            # 调用卡片的初始化方法，设置卡片属性
            if hasattr(card, 'load_config'):
                card.load_config(settings)

            # 将卡片存入字典，方便后面查找
            self.cards[card.card_id] = card  

            # 插入布局并连接信号
            self._insert_card_to_layout(card, button_container)
            self._connect_card_signals(card, phase_key)

    def _load_phase_cards(self, card_configs, phase_key, button_container):
        """加载提取阶段卡片"""
        card_map = {
            "TagExtractionCard": TagExtractionCard,
            "ThoughtExtractionCard": ThoughtExtractionCard,
            "TranslationExtractionCard": TranslationExtractionCard,
            "ResponseExtractionCard": ResponseExtractionCard,
            "RegexExtractionCard": RegexExtractionCard,
            "GlossaryExtractionCard": GlossaryExtractionCard,
            "NoTranslateListExtractionCard": NoTranslateListExtractionCard
        }
        
        for card_data in card_configs:
            card_type = card_data.get("type")
            card_class = card_map.get(card_type)
            if not card_class:
                continue
                
            card = card_class(self)
            card.card_id = card_data.get("id", str(uuid.uuid4()))
            settings = card_data.get("settings", {})
            
            # 调用卡片的初始化方法
            if hasattr(card, 'load_config'):
                card.load_config(settings)
            
            # 将卡片存入字典，方便后面查找
            self.cards[card.card_id] = card  

            # 插入布局并连接信号
            self._insert_card_to_layout(card, button_container)
            self._connect_card_signals(card, phase_key)


    def add_dialogue_card_A(self):
        """添加请求阶段A的对话卡片"""
        phase_key = "request_phase_a"
        new_card = DialogueFragmentCard(self)   # 创建卡片
        self._setup_new_card(new_card, phase_key) # 赋予卡片基础属性
        self._insert_card_to_layout(new_card, self.button_container_A) # 添加进布局
        self._connect_card_signals(new_card, phase_key) # 连接卡片的删除与更新信号

    def add_extraction_card(self, extractor_type):
        """添加提取阶段的卡片"""
        phase_key = "extraction_phase"
        new_card = self._create_card_by_type(extractor_type)
        
        self._setup_new_card(new_card, phase_key)
        self._insert_card_to_layout(new_card, self.button_container_E)
        self._connect_card_signals(new_card, phase_key)


    def add_dialogue_card_B(self):
        """添加请求阶段B的对话卡片"""
        phase_key = "request_phase_b"
        new_card = DialogueFragmentCard(self)
        self._setup_new_card(new_card, phase_key)
        self._insert_card_to_layout(new_card, self.button_container_B)
        self._connect_card_signals(new_card, phase_key)


    def _create_card_by_type(self, extractor_type):
        """根据类型创建对应卡片"""
        card_map = {
            "标签提取器": TagExtractionCard,
            "思考提取器": ThoughtExtractionCard,
            "译文提取器": TranslationExtractionCard,
            "回复提取器": ResponseExtractionCard, 
            "正则提取器": RegexExtractionCard,
            "术语表提取器": GlossaryExtractionCard,
            "禁翻表提取器": NoTranslateListExtractionCard
        }
        return card_map[extractor_type](self)

    def _get_card_initial_config(self, card):
        """统一获取卡片配置：默认配置 + 动态字段"""
        config = getattr(card, 'default_config', {}).copy()
        
        # 对话卡片需要补充动态字段
        if isinstance(card, DialogueFragmentCard):
            config.update({
                "role": card.role_combo.currentText(),
                "content": card.content(),
                "system_info": card.system_label.text()
            })
        return config
            
    def _connect_card_signals(self, card, phase_key):
        """连接卡片信号"""
        # 链接卡片的删除信号
        card.delete_requested.connect(
            lambda: self._handle_card_deletion(phase_key, card.card_id))
        
        # 链接卡片的配置更新信号
        if hasattr(card, 'config_changed'):
            card.config_changed.connect(
                lambda config: self._update_card_config(phase_key, card.card_id, config))

    def _insert_card_to_layout(self, card, button_container):
        """将卡片插入布局"""
        container_index = self.vbox.indexOf(button_container)
        self.vbox.insertWidget(container_index, card)


    def _setup_new_card(self, card, phase_key):
        """初始化卡片属性"""
        card.phase_key = phase_key
        card.card_id = str(uuid.uuid4())
        card_config = {
            "type": card.__class__.__name__,
            "id": card.card_id,
            "settings": self._get_card_initial_config(card)
        }
        self.default["flow_design_list"][phase_key].append(card_config)
        self.cards[card.card_id] = card  # 将卡片存入字典
        self.save_config(self.default)

    def _handle_card_deletion(self, phase_key, card_id):
        """处理卡片删除"""
        # 从界面移除
        for i in reversed(range(self.vbox.count())):
            widget = self.vbox.itemAt(i).widget()
            if widget and getattr(widget, "card_id", None) == card_id:
                widget.deleteLater()
                self.vbox.removeWidget(widget)
                break
        # 从配置移除
        phase_list = self.default["flow_design_list"][phase_key]
        self.default["flow_design_list"][phase_key] = [
            item for item in phase_list if item["id"] != card_id
        ]
        self.cards.pop(card_id, None)  # 从字典移除
        self.save_config(self.default)

    def _update_card_config(self, phase_key, card_id, new_config):
        """更新卡片配置"""
        for item in self.default["flow_design_list"][phase_key]:
            if item["id"] == card_id:
                item["settings"].update(new_config)
                self.save_config(self.default)
                break
        

    def start_process_test(self, breakpoint_position):
        """启动测试流程"""
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.NEW_PROCESS_TEST
            
            # 创建深拷贝避免修改原始数据
            import copy
            test_params = copy.deepcopy(self.default["flow_design_list"])
            
            # 清理测试参数中的四个字段
            test_params.pop("request_a_response_content", "")
            test_params.pop("request_a_response_think", "")
            test_params.pop("request_b_response_content", "")
            test_params.pop("request_b_response_think", "")
            
            # 清空所有卡片的system_info
            phases = ["request_phase_a", "extraction_phase", "request_phase_b"]
            for phase in phases:
                for card in test_params.get(phase, []):
                    card["settings"]["system_info"] = ""
            
            # 设置断点位置并发送
            test_params["test_target_breakpoint_position"] = breakpoint_position
            self.emit(Base.EVENT.NEW_PROCESS_START, test_params)
        else:
            self.warning_toast("", self.tra("已有测试进行中"))

    def process_done_handler(self, event: int, data: dict):
        """处理测试完成"""
        # 改变应用状态
        Base.work_status = Base.STATUS.IDLE
        # 提取测试消息
        self.default["flow_design_list"] = data.get('result', {})
        success = data.get('success', False)
        
        # 显示消息条
        if success:
            self.success_toast("", self.tra("流程测试成功"))
        else:
            self.error_toast("", self.tra("流程测试失败"))

        # 更新所有卡片的系统提示
        phases = ["request_phase_a", "extraction_phase", "request_phase_b"]
        for phase in phases:
            for card_config in self.default["flow_design_list"].get(phase, []):
                if card := self.cards.get(card_config["id"]):
                    if system_info := card_config["settings"].get("system_info"):
                        card.set_system_info(system_info)
        
        # 处理特殊响应内容
        request_a_content = self.default["flow_design_list"].get("request_a_response_content")
        request_b_content = self.default["flow_design_list"].get("request_b_response_content")
        
        # 更新第一阶段最后一个卡片
        if request_a_content:
            if phase_a := self.default["flow_design_list"].get("request_phase_a"):
                if last_card := self.cards.get(phase_a[-1]["id"]):
                    new_system = self.tra("[INFO] 第一次AI回复内容:") +"\n" + request_a_content
                    last_card.set_response_info(new_system)
        
        # 更新第三阶段最后一个卡片
        if request_b_content:
            if phase_b := self.default["flow_design_list"].get("request_phase_b"):
                if last_card := self.cards.get(phase_b[-1]["id"]):
                    new_system = self.tra("[INFO] 第二次AI回复内容:") +"\n" + request_b_content
                    last_card.set_response_info(new_system)
        
        # 持久化保存
        self.save_config(self.default)


    def export_config(self):
        """导出配置到运行目录"""
        config_data = self.default["flow_design_list"]
        
        info_cont = self.tra("导出_流程设计配置") + ".json"
        with open(info_cont, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(config_data, indent = 4, ensure_ascii = False))

        # 弹出提示
        self.success_toast("", self.tra("数据已导出到应用根目录"))


    def import_config(self):
        """从文件导入配置"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, self.tra("选择配置文件"), "",
            "JSON文件 (*.json)", options=QFileDialog.Options()
        )
        
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                imported_data = json.load(f)
            
            # 验证配置格式
            if not self._validate_config(imported_data):
                return

            # 清除现有界面
            self.clear_interface()
            
            # 更新配置数据
            self.default["flow_design_list"] = imported_data
            
            # 重新初始化界面
            self.initialize_cards_from_config(imported_data)
            self.save_config(self.default)
            
            # 弹出提示
            self.success_toast("", self.tra("已导入配置文件"))

        except Exception as e:
            pass

    def _validate_config(self, config):
        """验证配置结构"""
        required_keys = {
            "test_target_breakpoint_position", 
            "actual_running_breakpoint_position",
            "request_phase_a",
            "extraction_phase",
            "request_phase_b"
        }
        return required_keys.issubset(config.keys())

    def clear_interface(self):
        """清除所有动态生成的卡片"""
        # 删除所有卡片部件
        for card_id in list(self.cards.keys()):
            card = self.cards.pop(card_id)
            card.deleteLater()
        
        # 清空配置数据
        phases = ["request_phase_a", "extraction_phase", "request_phase_b"]
        for phase in phases:
            self.default["flow_design_list"][phase].clear()