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

import rapidjson as json
from rich import print
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from Base.PluginManager import PluginManager
from Module_Folders.Translator.Translator import Translator
from Module_Folders.Request_Tester.Request import Request_Tester
from User_Interface.AppFluentWindow import AppFluentWindow

# 载入配置文件
def load_config() -> dict:
    config = {}

    if os.path.exists("./Resource/config.json"):
        with open("./Resource/config.json", "r", encoding = "utf-8") as reader:
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
    sys.path.append(script_dir)
    print(f"[[green]INFO[/]] 当前工作目录为 {script_dir}")

    # 创建全局插件管理器
    plugin_manager = PluginManager()
    plugin_manager.load_plugins_from_directory("./Plugin_Scripts")

    # 载入配置文件
    config = load_config()

    # 设置全局缩放比例
    if config.get("scale_factor", "") == "50%":
        os.environ["QT_SCALE_FACTOR"] = "0.50"
    elif config.get("scale_factor", "") == "75%":
        os.environ["QT_SCALE_FACTOR"] = "0.75"
    elif config.get("scale_factor", "") == "150%":
        os.environ["QT_SCALE_FACTOR"] = "1.50"
    elif config.get("scale_factor", "") == "200%":
        os.environ["QT_SCALE_FACTOR"] = "2.00"

    # 创建全局应用对象
    app = QApplication(sys.argv)

    # 设置全局字体属性，解决狗牙问题
    font = QFont("Consolas")
    if config.get("font_hinting", True) == True:
        font.setHintingPreference(QFont.PreferFullHinting)
    else:
        font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    # 创建全局窗口对象
    app_fluent_window = AppFluentWindow(
        version = "AiNiee v5.2.3",
        plugin_manager = plugin_manager,
    )

    # 创建全局测试器对象
    request_tester = Request_Tester()

    # 创建翻译器对象
    translator = Translator(plugin_manager = plugin_manager)

    # 显示全局窗口
    app_fluent_window.show()

    # 进入事件循环，等待用户操作
    sys.exit(app.exec_())