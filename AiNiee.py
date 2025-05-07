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
from rich import print
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QSplashScreen 


# 过滤protobuf的警告信息
warnings.filterwarnings(
    action='ignore',
    message=r'.*SymbolDatabase\.GetPrototype\(\) is deprecated.*',  # 使用正则表达式匹配警告消息
    category=UserWarning,
    module=r'google\.protobuf\.symbol_database'  # 警告来源的模块 (正则)
)

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

    # 创建全局应用对象
    app = QApplication(sys.argv)

    display_banner()
    print(f"[[green]INFO[/]] Current working directory is {script_dir}")

    # 启动页面
    logo_path = os.path.join(".", "Resource", "Logo", "logo.png")
    icon = QIcon(logo_path)  # 使用QIcon加载logo
    pixmap = icon.pixmap(400, 200)  # 从QIcon获取指定大小的QPixmap
    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.setEnabled(False)  # 禁用用户交互，可能改善渲染


    # 显示启动页面
    splash.show()
    app.processEvents() # 处理事件，确保启动画面能立即显示和更新

    # 加载配置文件
    config = load_config()

    # 设置全局缩放比例
    scale_factor_str = config.get("scale_factor", "")
    if scale_factor_str == "50%":
        os.environ["QT_SCALE_FACTOR"] = "0.50"
    elif scale_factor_str == "75%":
        os.environ["QT_SCALE_FACTOR"] = "0.75"
    elif scale_factor_str == "150%":
        os.environ["QT_SCALE_FACTOR"] = "1.50"
    elif scale_factor_str == "200%":
        os.environ["QT_SCALE_FACTOR"] = "2.00"

    # 设置全局字体属性，解决狗牙问题
    font = QFont("Consolas")
    if config.get("font_hinting", True):
        font.setHintingPreference(QFont.PreferFullHinting)
    else:
        font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    # 创建全局插件管理器
    from Base.PluginManager import PluginManager
    plugin_manager = PluginManager()
    plugin_path = os.path.join(".", "PluginScripts")
    plugin_manager.load_plugins_from_directory(plugin_path)

    app.processEvents() # 启动画面更新
    # 创建全局文件读写器(高性能消耗)
    from ModuleFolders.FileReader.FileReader import FileReader
    file_reader = FileReader()
    from ModuleFolders.FileOutputer.FileOutputer import FileOutputer
    file_writer = FileOutputer()

    app.processEvents() # 启动画面更新
    # 创建全局窗口对象(高性能消耗)
    from UserInterface.AppFluentWindow import AppFluentWindow
    app_fluent_window = AppFluentWindow(
        version="AiNiee6.5",
        plugin_manager=plugin_manager,
        support_project_types=file_reader.get_support_project_types(),
    )

    # 创建全局接口测试器对象，并初始化订阅事件
    from ModuleFolders.RequestTester.RequestTester import RequestTester
    request_tester = RequestTester()

    # 创建全局流程测试器对象，并初始化订阅事件
    from ModuleFolders.RequestTester.ProcessTester import ProcessTester
    process_tester = ProcessTester()

    # 创建翻译器对象，并初始化订阅事件(高性能消耗)
    from ModuleFolders.Translator.Translator import Translator
    translator = Translator(
        plugin_manager=plugin_manager, file_reader=file_reader, file_writer=file_writer
    )

    # 显示全局窗口
    app_fluent_window.show()

    # 隐藏启动页面
    splash.finish(app_fluent_window) 

    # 进入事件循环，等待用户操作
    sys.exit(app.exec_())