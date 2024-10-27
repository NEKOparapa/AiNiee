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

from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from StevExtraction import jtpp

from Module_Folders.Translator import Translator
from Module_Folders.Configurator.Config import Configurator
from Module_Folders.Request_Tester.Request import Request_Tester

from Plugin_Scripts.Plugin_Manager import Plugin_Manager

from User_Interface.AppFluentWindow import AppFluentWindow

if __name__ == "__main__":
    # 开启子进程支持
    multiprocessing.freeze_support()

    # 启用了高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 设置工作目录为根目录
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))  # 获取
    sys.path.append(script_dir)

    # 创建全局配置器
    configurator = Configurator(script_dir)
    configurator.load_config_file()

    # 创建全局插件管理器
    plugin_manager = Plugin_Manager()
    plugin_manager.load_plugins_from_directory(configurator.plugin_dir)

    # 创建全局应用对象
    app = QApplication(sys.argv)

    # 设置全局字体属性，解决狗牙问题
    font = QFont("Consolas")
    if hasattr(configurator, "font_hinting") and configurator.font_hinting == True:
        font.setHintingPreference(QFont.PreferFullHinting)
    else:
        font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    # 创建全局窗口对象
    app_fluent_window = AppFluentWindow(
        version = "AiNiee v5.1.0 Dev",
        configurator = configurator,
        plugin_manager = plugin_manager,
        jtpp = jtpp,
    )

    # 创建全局测试器对象
    request_tester = Request_Tester()

    # 创建翻译器对象
    translator = Translator(
        configurator = configurator,
        plugin_manager = plugin_manager,
    )

    # 显示全局窗口
    app_fluent_window.show()

    # 进入事件循环，等待用户操作
    sys.exit(app.exec_())