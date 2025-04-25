from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QFrame, QLabel, QStackedWidget, QHBoxLayout, QWidget
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtSvg import QSvgWidget
from qfluentwidgets import (FluentIcon, SegmentedWidget, StrongBodyLabel,
                           BodyLabel, PrimaryPushButton, ComboBox)

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.LineEditCard import LineEditCard
from Widget.PushButtonCard import PushButtonCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.FolderDropCard import FolderDropLabel

class ProjectSettingsPage(QFrame, Base):

    def __init__(self, text: str, window, support_project_types: set[str]) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))


        self.pivot = SegmentedWidget(self)  # 创建一个 SegmentedWidget 实例，分段式导航栏
        self.stackedWidget = QStackedWidget(self)  # 创建一个 QStackedWidget 实例，堆叠式窗口
        self.vBoxLayout = QVBoxLayout(self)  # 创建一个垂直布局管理器

        self.A_settings = ProjectSettingsPage_A('A_settings', window)  # 创建实例，指向界面
        self.B_settings = ProjectSettingsPage_B('B_settings', window, support_project_types)  # 创建实例，指向界面

        # 添加子界面到分段式导航栏
        self.addSubInterface(self.A_settings, 'A_settings', '快速设置')
        self.addSubInterface(self.B_settings, 'B_settings', '详细设置')

        # 将分段式导航栏和堆叠式窗口添加到垂直布局中
        self.vBoxLayout.addWidget(self.pivot)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.vBoxLayout.setContentsMargins(5, 5, 5, 0)  # 分别设置左、上、右、下的边距

        # 连接堆叠式窗口的 currentChanged 信号到槽函数 onCurrentIndexChanged
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.A_settings)  # 设置默认显示的子界面为xxx界面
        self.pivot.setCurrentItem(self.A_settings.objectName())  # 设置分段式导航栏的当前项为xxx界面

    def addSubInterface(self, widget: QLabel, objectName, text):
        """
        添加子界面到堆叠式窗口和分段式导航栏
        """
        widget.setObjectName(objectName)
        #widget.setAlignment(Qt.AlignCenter) # 设置 widget 对象的文本（如果是文本控件）在控件中的水平对齐方式
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def onCurrentIndexChanged(self, index):
        """
        槽函数：堆叠式窗口的 currentChanged 信号的槽函数
        """
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())


# 快速设置
class ProjectSettingsPage_A(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "target_platform": "deepseek",
            "label_input_path": "./input",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 顶部区域 - 接口平台选择
        self.header_widget = QWidget(self)
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        self.title_label = StrongBodyLabel(self.tra("接口平台"), self)
        self.header_layout.addWidget(self.title_label)

        # 填充
        self.header_layout.addStretch(1)

        # 下拉菜单
        self.platform_combo = ComboBox(self)
        self.platform_combo.setMinimumWidth(150)
        self.header_layout.addWidget(self.platform_combo)

        # 添加到主容器
        self.container.addWidget(self.header_widget)

         # 添加间距
        self.spacer = QWidget(self)
        self.spacer.setFixedHeight(5)
        self.container.addWidget(self.spacer)

        # 添加分割线
        self.separator = QWidget(self)
        self.separator.setFixedHeight(2)
        self.separator.setStyleSheet("background-color: #3A3A3A;")
        self.container.addWidget(self.separator)

        self.spacer = QWidget(self)
        self.spacer.setFixedHeight(10)
        self.container.addWidget(self.spacer)
       

        # 文件拖放区域
        self.file_drop_area = QWidget(self)
        self.file_drop_layout = QVBoxLayout(self.file_drop_area)
        self.file_drop_layout.setContentsMargins(0, 0, 0, 0)
        self.file_drop_layout.setSpacing(15)
        self.file_drop_layout.setAlignment(Qt.AlignCenter)

        # 创建虚线边框容器
        self.drop_container = QWidget(self)
        self.drop_container.setObjectName("dropContainer")
        self.drop_container.setMinimumHeight(400)  
        self.drop_container.setMinimumWidth(400) 
        self.drop_container.setStyleSheet("""
            #dropContainer {
                border: 1px dashed #6a6a6a;
                border-radius: 8px;
                background-color: rgba(60, 60, 60, 0.3);
            }

            #dropContainer:hover {
                border-color: #8a8aff;
                background-color: rgba(80, 80, 95, 0.5);
            }
        """)

        self.drop_layout = QVBoxLayout(self.drop_container)
        self.drop_layout.setContentsMargins(0, 0, 0, 0)  # 移除内边距
        self.drop_layout.setSpacing(5)
        self.drop_layout.setAlignment(Qt.AlignCenter)

        # 创建一个容器来居中放置图标和文本
        self.icon_text_container = QWidget(self)
        self.icon_text_layout = QVBoxLayout(self.icon_text_container)
        self.icon_text_layout.setContentsMargins(0, 8, 0, 8)  # 上下添加间距
        self.icon_text_layout.setSpacing(10)  # 图标和文本之间的间距
        self.icon_text_layout.setAlignment(Qt.AlignCenter)

        # 上传图标 (使用SVG)
        self.upload_icon = QSvgWidget(self)
        self.upload_icon.setFixedSize(48, 48)

        # 上传图标的SVG内容
        upload_svg = """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#AAAAAA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        """

        # 创建临时文件来存储SVG内容
        import tempfile
        self.temp_svg_file = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
        self.temp_svg_file.write(upload_svg.encode('utf-8'))
        self.temp_svg_file.close()

        # 加载SVG文件
        self.upload_icon.load(self.temp_svg_file.name)

        # 创建文件拖放标签
        self.folder_drop_label = FolderDropLabel(self.tra("将输入文件夹拖拽到此处"), self)
        self.folder_drop_label.pathDropped.connect(self.on_path_dropped)
        self.folder_drop_label.pathChanged.connect(self.on_path_changed)
        self.folder_drop_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: #FFFFFF;
            font-size: 16px;
        """)
        self.folder_drop_label.setFixedHeight(30)
        self.folder_drop_label.setAlignment(Qt.AlignCenter)

        # 添加图标和文本到容器
        self.icon_text_layout.addWidget(self.upload_icon, 0, Qt.AlignCenter)
        self.icon_text_layout.addWidget(self.folder_drop_label, 0, Qt.AlignCenter)

        # 将容器添加到拖放区域
        self.drop_layout.addWidget(self.icon_text_container)

        # 获取配置文件中的初始路径
        initial_path = config.get("label_input_path", "")
        if initial_path and initial_path != "./input":
            self.folder_drop_label.set_path(initial_path)

        # 添加到布局
        self.drop_layout.addWidget(self.folder_drop_label)

        

        # 创建底部容器
        self.bottom_container = QWidget(self)
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(0, 10, 0, 0)
        self.bottom_layout.setSpacing(10)
        self.bottom_layout.setAlignment(Qt.AlignCenter)

        # 或者文本
        self.or_label = BodyLabel(self.tra("或者"), self)
        self.or_label.setAlignment(Qt.AlignCenter)
        self.or_label.setStyleSheet("""
            color: #AAAAAA;
            font-size: 12px;
        """)
        self.bottom_layout.addWidget(self.or_label)

        # 选择文件夹按钮 - 使用绿色风格
        self.select_folder_button = PrimaryPushButton(FluentIcon.FOLDER,self.tra("选择输入文件夹") ,self)
        self.select_folder_button.setFixedSize(150, 36)
        self.select_folder_button.clicked.connect(self.select_folder)

        # 按钮容器用于居中
        self.button_container = QWidget(self)
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setAlignment(Qt.AlignCenter)
        self.button_layout.addWidget(self.select_folder_button)

        self.bottom_layout.addWidget(self.button_container)

        # 添加底部容器到主布局
        self.drop_layout.addWidget(self.bottom_container)

        # 添加虚线边框容器到主布局
        self.file_drop_layout.addWidget(self.drop_container)
        # 显示当前路径
        path_text = initial_path if initial_path and initial_path != "./input" else ""
        self.path_label = BodyLabel(path_text, self)
        self.path_label.setAlignment(Qt.AlignCenter)
        self.path_label.setStyleSheet("""
            color: #6A9BFF;
            font-size: 12px;
            margin-top: 5px;
        """)
        self.bottom_layout.addWidget(self.path_label)

        # 添加到主容器
        self.container.addWidget(self.file_drop_area)

        # 初始化接口平台下拉菜单
        self.init_platform_combo(config)

        # 填充
        self.container.addStretch(1)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        # 更新接口平台列表
        config = self.load_config()
        self.update_platform_combo(config)

    # 清理临时文件
    def __del__(self):
        try:
            if hasattr(self, 'temp_svg_file') and self.temp_svg_file:
                import os
                if os.path.exists(self.temp_svg_file.name):
                    os.unlink(self.temp_svg_file.name)
        except Exception:
            pass

    def init_platform_combo(self, config):
        """初始化接口平台下拉菜单"""
        self.update_platform_combo(config)
        # 连接信号
        self.platform_combo.currentTextChanged.connect(self.on_platform_changed)

    def update_platform_combo(self, config):
        """更新接口平台下拉菜单"""
        # 保存当前选中的文本
        current_text = self.platform_combo.currentText()

        # 清空并重新添加项目
        self.platform_combo.clear()
        items = self.get_items(config)
        self.platform_combo.addItems(items)

        # 设置当前选中项
        current_platform = self.find_name_by_tag(config, config.get("target_platform"))
        if current_platform in items:
            self.platform_combo.setCurrentText(current_platform)
        elif current_text in items:
            self.platform_combo.setCurrentText(current_text)
        elif items:
            self.platform_combo.setCurrentIndex(0)

    def on_platform_changed(self, text):
        """接口平台变更回调"""
        if not text:
            return

        config = self.load_config()
        config["target_platform"] = self.find_tag_by_name(config, text)
        self.save_config(config)

    def select_folder(self):
        """选择文件夹按钮点击回调"""
        path = QFileDialog.getExistingDirectory(self, self.tra("选择输入文件夹"), "")
        if not path:
            return

        # 更新UI
        self.folder_drop_label.set_path(path)
        self.path_label.setText(path)

        # 更新配置
        config = self.load_config()
        config["label_input_path"] = path
        self.save_config(config)

    def on_path_dropped(self, path):
        """路径拖放回调"""
        if not path:
            return

        # 更新UI
        self.path_label.setText(path)

        # 更新配置
        config = self.load_config()
        config["label_input_path"] = path
        self.save_config(config)

    def on_path_changed(self, path):
        """路径变更回调"""
        if not path:
            self.path_label.setText("")
            return

        # 更新UI
        # self.path_label.setText(path)

    # 获取接口列表
    def get_items(self, config) -> list:
        return [v.get("name") for k, v in config.get("platforms").items()]

    # 通过接口名字获取标签
    def find_tag_by_name(self, config, name: str) -> str:
        results = [v.get("tag") for k, v in config.get("platforms").items() if v.get("name") == name]

        if len(results) > 0:
            return results[0]
        else:
            return ""

    # 通过接口标签获取名字
    def find_name_by_tag(self, config, tag: str) -> str:
        results = [v.get("name") for k, v in config.get("platforms").items() if v.get("tag") == tag]

        if len(results) > 0:
            return results[0]
        else:
            return ""


# 详细设置
class ProjectSettingsPage_B(QFrame, Base):

    def __init__(self, text: str, window, support_project_types: set[str]) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))
        self.support_project_types = support_project_types

        # 默认配置
        self.default = {
            "translation_project": "AutoType",
            "source_language": "japanese",
            "target_language": "chinese_simplified",
            "label_input_exclude_rule": "",
            "label_output_path": "./output",
            "auto_set_output_path": True
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_02(self.container, config)
        self.add_widget_03(self.container, config)
        self.add_widget_04(self.container, config)
        self.add_widget_exclude_rule(self.container, config)
        self.add_widget_06(self.container, config)
        self.add_widget_07(self.container, config)

        # 填充
        self.container.addStretch(1)


    # 项目类型
    def add_widget_02(self, parent, config) -> None:
        # 定义项目类型与值的配对列表（显示文本, 存储值）
        project_pairs = [
            (self.tra("Txt小说文件"), "Txt"),
            (self.tra("Epub小说文件"), "Epub"),
            (self.tra("Docx文档文件"), "Docx"),
            (self.tra("Srt字幕文件"), "Srt"),
            (self.tra("Vtt字幕文件"), "Vtt"),
            (self.tra("Lrc音声文件"), "Lrc"),
            (self.tra("Md文档文件"), "Md"),
            (self.tra("T++导出文件"), "Tpp"),
            (self.tra("Trans工程文件"), "Trans"),
            (self.tra("Mtool导出文件"), "Mtool"),
            (self.tra("Renpy导出文件"), "Renpy"),
            (self.tra("VNText导出文件"), "Vnt"),
            (self.tra("Ainiee缓存文件"), "Ainiee_cache"),
            (self.tra("ParaTranz导出文件"), "Paratranz"),
            (self.tra('Pdf文档文件 (需要Microsoft Office)'), "OfficeConversionPdf"),
            (self.tra('Doc文档文件 (需要Microsoft Office)'), "OfficeConversionDoc"),
            (self.tra("自动识别文件类型"), "AutoType")

        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in project_pairs if value in self.support_project_types]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "AutoType")

            # 旧配置兼容层转换(后续版本再删除)
            if current_value == "Txt小说文件":
                current_value = "Txt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Srt字幕文件":
                current_value = "Srt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Vtt字幕文件":
                current_value = "Vtt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Lrc音声文件":
                current_value = "Lrc"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Epub小说文件":
                current_value = "Epub"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Docx文档文件":
                current_value = "Docx"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Mtool导出文件":
                current_value = "Mtool"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "T++导出文件":
                current_value = "Tpp"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "VNText导出文件":
                current_value = "Vnt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "ParaTranz导出文件":
                current_value = "Paratranz"
                current_config["translation_project"] = current_value
                self.save_config(current_config)

            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "AutoType"  # 默认值
            )

            config = self.load_config()
            config["translation_project"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, value in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("项目类型"),
                self.tra("设置当前翻译项目所使用的原始文本的格式，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 原文语言
    def add_widget_03(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        source_language_pairs = [
            (self.tra("日语"), "japanese"),
            (self.tra("英语"), "english"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in source_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("source_language", "japanese")


            # 旧配置兼容层转换(后续版本再删除)
            if current_value == "日语":
                current_value = "japanese"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "英语":
                current_value = "english"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "韩语":
                current_value = "korean"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "俄语":
                current_value = "russian"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "德语":
                current_value = "german"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "法语":
                current_value = "french"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "简中":
                current_value = "chinese_simplified"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "繁中":
                current_value = "chinese_traditional"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "西班牙语":
                current_value = "spanish"
                current_config["source_language"] = current_value
                self.save_config(current_config)


            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "japanese"  # 默认值
            )

            config = self.load_config()
            config["source_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("原文语言"),
                self.tra("设置当前翻译项目所使用的原始文本的语言，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 译文语言
    def add_widget_04(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        target_language_pairs = [
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("英语"), "english"),
            (self.tra("日语"), "japanese"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in target_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("target_language", "chinese_simplified")

            # 旧配置兼容层转换(后续版本再删除)
            if current_value == "日语":
                current_value = "japanese"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "英语":
                current_value = "english"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "韩语":
                current_value = "korean"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "俄语":
                current_value = "russian"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "德语":
                current_value = "german"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "法语":
                current_value = "french"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "简中":
                current_value = "chinese_simplified"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "繁中":
                current_value = "chinese_traditional"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "西班牙语":
                current_value = "spanish"
                current_config["target_language"] = current_value
                self.save_config(current_config)


            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "chinese_simplified"  # 默认值
            )

            config = self.load_config()
            config["target_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("译文语言"),
                self.tra("设置当前翻译项目所期望的译文文本的语言，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 输入的文件/目录排除规则
    def add_widget_exclude_rule(self, parent, config) -> None:

        def init(widget) -> None:
            widget.set_text(config.get("label_input_exclude_rule"))
            widget.set_fixed_width(256)
            widget.set_placeholder_text(self.tra("*.log,aaa/*"))

        def text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["label_input_exclude_rule"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("输入文件/目录排除规则"),
                self.tra("*.log 表示排除所有结尾为 .log 的文件，aaa/* 表示排除输入文件夹下整个 aaa 目录，多个规则用英文逗号分隔"),
                init=init,
                text_changed=text_changed,
            )
        )

    # 输出文件夹
    def add_widget_06(self, parent, config) -> None:
        def widget_init(widget):
            info_cont = self.tra("当前输出文件夹为") + f" {config.get("label_output_path")}"
            widget.set_description(info_cont)
            widget.set_text(self.tra("选择文件夹"))
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget) -> None:
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
            if path is None or path == "":
                return

            # 更新UI
            info_cont = self.tra("当前输出文件夹为") + f" {path.strip()}"
            widget.set_description(info_cont)

            # 更新并保存配置
            config = self.load_config()
            config["label_output_path"] = path.strip()
            self.save_config(config)

        # 拖拽文件夹回调
        def drop_callback(widget, dropped_text) -> None:
            if not dropped_text:
                return

            # 更新UI
            info_cont = self.tra("当前输出文件夹为") + f" {dropped_text.strip()}"
            widget.set_description(info_cont)

            # 更新并保存配置
            config = self.load_config()
            config["label_output_path"] = dropped_text.strip()
            self.save_config(config)


        parent.addWidget(
            PushButtonCard(
                self.tra("输出文件夹(不能与输入文件夹相同)"),
                "",
                widget_init,
                widget_callback,
                drop_callback,
            )
        )

    # 自动设置输出文件夹开关
    def add_widget_07(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_set_output_path"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_set_output_path"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动设置输出文件夹"),
                self.tra("启用此功能后，设置为输入文件夹的平级目录，比如输入文件夹为D:/Test/Input，输出文件夹将设置为D:/Test/AiNieeOutput"),
                widget_init,
                widget_callback,
            )
        )