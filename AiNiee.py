#
#                        _oo0oo_
#                       o8888888o
#                       88" . "88
#                       (| -_- |)
#                       0\  =  /0
#                     ___/`---"\___
#                   ." \\|     |// ".
#                  / \\|||  :  |||// \
#                 / _||||| -:- |||||- \
#                |   | \\\  -  /// |   |
#                | \_|  ""\---/""  |_/ |
#                \  .-\__  "-"  ___/-. /
#              ___". ."  /--.--\  `. ."___
#           ."" "<  `.___\_<|>_/___." >" "".
#          | | :  `- \`.;`\ _ /`;.`/ - ` : | |
#          \  \ `_.   \_ __\ /__ _/   .-` /  /
#      =====`-.____`.___ \_____/___.-`___.-"=====
#                        `=---="
#
#
#      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#             赛博佛祖光耀照，程序运行永无忧。
#             翻译之路顺畅通，字字珠玑无误漏。

import os
import sys
import multiprocessing
import warnings

import rapidjson as json
from bs4 import MarkupResemblesLocatorWarning
from rich import print
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QSplashScreen


# 过滤protobuf的警告信息
warnings.filterwarnings(
    action='ignore',
    message=r'.*SymbolDatabase\.GetPrototype\(\) is deprecated.*',  # 使用正则表达式匹配警告消息
    category=UserWarning,
    module=r'google\.protobuf\.symbol_database'  # 警告来源的模块 (正则)
)
# 过滤pBeautiful Soup的警告信息
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

def display_banner():
    print(" █████   ██  ███    ██  ██  ███████  ███████ ")
    print("██   ██  ██  ████   ██  ██  ██       ██      ")
    print("███████  ██  ██ ██  ██  ██  █████    █████   ")
    print("██   ██  ██  ██  ██ ██  ██  ██       ██      ")
    print("██   ██  ██  ██   ████  ██  ███████  ███████ ")
    print("                                        ")
    print("                                        ")

# 载入配置文件
def load_config() -> dict:
    config = {}
    config_path = os.path.join(".", "Resource", "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as reader:
            config = json.load(reader)
    return config

# 启动画面消息
def update_splash_message(splash, message, app, font_size=10, font_weight=QFont.Bold):
    font = QFont("Microsoft YaHei")
    font.setPointSize(font_size)
    font.setWeight(font_weight)
    
    # 创建淡粉红色
    text_color = QColor(255, 182, 193)
    
    splash.setFont(font)
    
    # 应用淡粉红颜色到文本
    splash.showMessage(message, Qt.AlignBottom | Qt.AlignCenter, text_color)
    
    app.processEvents()

if __name__ == "__main__":
    # 开启子进程支持
    multiprocessing.freeze_support()

    # 启用了高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 设置工作目录
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(script_dir) # 确保工作目录在脚本所在目录
    sys.path.append(script_dir)

    # 加载配置文件
    config = load_config()

    # 设置全局缩放比例
    scale_factor_str = config.get("scale_factor", "")
    if scale_factor_str == "50%":
        os.environ["QT_SCALE_FACTOR"] = "0.50"
    elif scale_factor_str == "75%":
        os.environ["QT_SCALE_FACTOR"] = "0.75"
    elif scale_factor_str == "125%":
        os.environ["QT_SCALE_FACTOR"] = "1.25"
    elif scale_factor_str == "150%":
        os.environ["QT_SCALE_FACTOR"] = "1.50"
    elif scale_factor_str == "200%":
        os.environ["QT_SCALE_FACTOR"] = "2.00"

    # 创建全局应用对象
    app = QApplication(sys.argv)

    display_banner()
    print(f"[[green]INFO[/]] Current working directory is {script_dir}")

    # 启动页面
    logo_path = os.path.join(".", "Resource", "Logo", "Logo.png")
    icon = QIcon(logo_path)  # 使用QIcon加载logo
    pixmap = icon.pixmap(400, 200)  # 从QIcon获取指定大小的QPixmap
    # 跟随缩放比例
    if "QT_SCALE_FACTOR" in os.environ:
        scale_factor = float(os.environ["QT_SCALE_FACTOR"])
        pixmap = pixmap.scaled(
            int(pixmap.width() * scale_factor),
            int(pixmap.height() * scale_factor),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.setEnabled(False)  # 禁用用户交互，可能改善渲染

    # 显示启动页面
    splash.show()
    update_splash_message(splash, "正在初始化...", app)  # 显示初始化消息



    # 设置全局字体属性，解决狗牙问题
    font = QFont("Consolas")
    if config.get("font_hinting", True):
        font.setHintingPreference(QFont.PreferFullHinting)
    else:
        font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    # 创建全局插件管理器
    update_splash_message(splash, "正在加载插件管理器... (10%)", app) # 更新启动页消息
    from Base.PluginManager import PluginManager
    plugin_manager = PluginManager()
    plugin_path = os.path.join(".", "PluginScripts")
    plugin_manager.load_plugins_from_directory(plugin_path)

    # 创建全局缓存器
    update_splash_message(splash, "正在加缓存器... (15%)", app)
    from ModuleFolders.Cache.CacheManager import CacheManager
    cache_manager = CacheManager()

    # 创建全局文件读写器(高性能消耗)
    update_splash_message(splash, "正在加载文件读写器... (25%)", app) 
    from ModuleFolders.FileReader.FileReader import FileReader
    file_reader = FileReader()
    from ModuleFolders.FileOutputer.FileOutputer import FileOutputer
    file_writer = FileOutputer()


    # 创建窗口对象(高性能消耗)
    update_splash_message(splash, "正在加载核心组件... (50%)", app)
    from UserInterface.AppFluentWindow import AppFluentWindow
    app_fluent_window = AppFluentWindow(
        version="AiNiee7.0.6 dev",
        plugin_manager=plugin_manager,
        cache_manager=cache_manager,
        file_reader =file_reader,
    )

    # 创建简易执行器对象，并初始化订阅事件
    update_splash_message(splash, "正在加载简易执行器... (60%)", app)
    from ModuleFolders.SimpleExecutor.SimpleExecutor import SimpleExecutor
    simple_executor = SimpleExecutor()

    # 创建任务执行器，并初始化订阅事件(高性能消耗)
    update_splash_message(splash, "正在加载任务执行器... (75%)", app)
    from ModuleFolders.TaskExecutor.TaskExecutor import TaskExecutor
    task_executor = TaskExecutor(
        plugin_manager=plugin_manager,
        cache_manager=cache_manager,
        file_reader=file_reader, 
        file_writer=file_writer
    )


    update_splash_message(splash, "启动完成，正在打开应用... (100%)", app)

    # 显示全局窗口
    app_fluent_window.show()

    # 隐藏启动页面
    splash.finish(app_fluent_window)

    # 进入事件循环，等待用户操作
    sys.exit(app.exec_())