#
#                        _oo0oo_
#                       o8888888o
#                       88" . "88
#                       (| -_- |)
#                       0\  =  /0
#                     ___/`---'\___
#                   .' \\|     |// '.
#                  / \\|||  :  |||// \
#                 / _||||| -:- |||||- \
#                |   | \\\  -  /// |   |
#                | \_|  ''\---/''  |_/ |
#                \  .-\__  '-'  ___/-. /
#              ___'. .'  /--.--\  `. .'___
#           ."" '<  `.___\_<|>_/___.' >' "".
#          | | :  `- \`.;`\ _ /`;.`/ - ` : | |
#          \  \ `_.   \_ __\ /__ _/   .-` /  /
#      =====`-.____`.___ \_____/___.-`___.-'=====
#                        `=---='
#
#
#      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#             赛博佛祖光耀照，程序运行永无忧。
#             翻译之路顺畅通，字字珠玑无误漏。

from Frontend.core.log_system import install as _install_log_system

def display_banner():
    print(" █████   ██  ███    ██  ██  ███████  ███████ ")
    print("██   ██  ██  ████   ██  ██  ██       ██      ")
    print("███████  ██  ██ ██  ██  ██  █████    █████   ")
    print("██   ██  ██  ██  ██ ██  ██  ██       ██      ")
    print("██   ██  ██  ██   ████  ██  ███████  ███████ ")
    print("                                        ")
    print("                                        ")

import logging
import os
import sys

from Frontend.platform.app_metadata import configure_application_metadata
from Frontend.core.resources import frontend_resource_path
from Frontend.core.paths import executable_root
from Frontend.platform.platform_paths import (
    monospace_font_family,
)
from Frontend.platform.runtime_setup import prepare_working_directory
from Frontend.platform.process import RESTART_EXIT_CODE, launch_desktop
from Frontend.platform.single_instance import acquire_app_mutex, release_app_mutex

import multiprocessing
import warnings

import rapidjson as json
from bs4 import MarkupResemblesLocatorWarning

from Frontend.core.log import LogMixin


class _BootstrapLogger(LogMixin):
    def _logger(self):
        return logging.getLogger("AiNiee.bootstrap")


_log = _BootstrapLogger()
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox


# 过滤protobuf的警告信息
warnings.filterwarnings(
    action='ignore',
    message=r'.*SymbolDatabase\.GetPrototype\(\) is deprecated.*',  # 使用正则表达式匹配警告消息
    category=UserWarning,
    module=r'google\.protobuf\.symbol_database'  # 警告来源的模块 (正则)
)
# 过滤pBeautiful Soup的警告信息
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# 载入配置文件
def load_config() -> dict:
    from Frontend.core.config import ConfigMixin
    return ConfigMixin().load_config()

# 载入版本信息函数
def load_version() -> str:
    """从 Frontend/resources/version/version.json 加载版本信息"""
    version_path = frontend_resource_path("version", "version.json")
    default_version = "Unknown Version"
    if os.path.exists(version_path):
        try:
            with open(version_path, "r", encoding="utf-8") as f:
                version_data = json.load(f)
                # 使用 .get() 方法安全地获取值，如果 "version" 键不存在，则返回默认值
                return version_data.get("version", default_version)
        except (json.JSONDecodeError, IOError) as e:
            _log.error("读取版本文件失败", error=e)
            return default_version
    else:
        _log.warning(f"版本文件 {version_path} 未找到, 将使用默认版本号")
        return default_version

def prepare_runtime_environment() -> str:
    # macOS 打包后资源和用户数据分离，这里只做入口层的工作目录准备。
    working_root = prepare_working_directory()
    os.chdir(working_root)
    for path in (working_root, executable_root()):
        if str(path) not in sys.path:
            sys.path.append(str(path))
    return str(working_root)


def _setup_qt_high_dpi():
    """固定使用 AUTO 跟随系统 DPI；必须在 QApplication 创建前调用。"""
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="AiNiee desktop client")
    parser.add_argument("--backend-url", default=os.environ.get("AINIEE_BACKEND_URL", "http://127.0.0.1:33888"), help="FastAPI 后端地址，本机未运行时自动启动（默认 http://127.0.0.1:33888）")
    args = parser.parse_args(argv)
    _log_path = _install_log_system()
    display_banner()
    # 开启子进程支持
    multiprocessing.freeze_support()

    # 启用了高 DPI 缩放
    _setup_qt_high_dpi()

    # 设置工作目录
    script_dir = prepare_runtime_environment()

    if not acquire_app_mutex() and os.environ.get("AINIEE_ALLOW_MULTI_INSTANCE") != "1":
        _log.warning("AiNiee 已在运行，本次启动退出（设 AINIEE_ALLOW_MULTI_INSTANCE=1 可绕过）")
        sys.exit(0)

    if _log_path is not None:
        _log.info(f"Log file: {_log_path}")

    from Frontend.app.startup_splash import StartupSplash
    with StartupSplash() as splash:
        return _run_application(args, script_dir, splash)


def _run_application(args, script_dir, splash):
    import atexit
    from Frontend.app.backend_connection import connect_backend
    from Frontend.core.config import ConfigMixin
    backend_client = None
    try:
        backend_client = connect_backend(args.backend_url, on_status=splash.show_message)
        ConfigMixin.remote_client = backend_client
        atexit.register(backend_client.close)
        splash.show_message("正在读取应用配置...")
        load_config()
    except Exception as error:
        _log.error("无法启动或连接 FastAPI 后端", error=error)
        if backend_client is not None:
            backend_client.close()
        splash.close()
        error_app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "无法连接后端", f"请检查后端依赖、服务地址和访问令牌。\n\n{error}")
        return 1
    
    # 加载版本信息
    app_version = load_version()

    # 创建全局应用对象
    app = QApplication(sys.argv)
    from Frontend.app.event_bridge import QtEventBridge
    event_bridge = QtEventBridge(app)
    configure_application_metadata(app, app_version)

    _log.info(f"Application Version: {app_version}")
    _log.info(f"Current working directory is {script_dir}")
    _log.info("Starting AiNiee Application...")

    splash.show_message("正在初始化界面...")

    # 设置全局字体属性，解决狗牙问题
    font = QFont(monospace_font_family())
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    # 创建全局缓存器
    splash.show_message("正在加载项目缓存...")
    from Frontend.services.project_state import RemoteCacheManager, RemoteFileReader
    cache_manager = RemoteCacheManager(backend_client)
    file_reader = RemoteFileReader(backend_client)
    event_bridge.cache = cache_manager

    # 创建窗口对象(高性能消耗)
    splash.show_message("正在加载核心组件...")
    from Frontend.app.window import AppFluentWindow
    app_fluent_window = AppFluentWindow(
        version=app_version,
        cache_manager=cache_manager,
        file_reader =file_reader,
    )

    splash.show_message("正在连接实时事件...")
    event_bridge.window = app_fluent_window
    backend_client.start_events(event_bridge.message.emit)

    splash.show_message("启动完成，正在打开应用...")

    # 显示全局窗口
    app_fluent_window.show()

    from Frontend.core.paths import portable_fallback_active
    if portable_fallback_active():
        from qfluentwidgets import InfoBar, InfoBarPosition
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(
            800,
            lambda: InfoBar.warning(
                title="便携模式",
                content="当前文件夹不可写，已改用系统目录保存数据。建议把程序解压到可写位置（文档 / 桌面 / U盘）。",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=-1,
                parent=app_fluent_window,
            ),
        )

    # 隐藏启动页面
    app.processEvents()
    splash.close()

    # 进入事件循环，等待用户操作
    exit_code = app.exec_()
    if exit_code != RESTART_EXIT_CODE:
        return exit_code

    # Keep the service running. The replacement reconnects to the same backend.
    backend_client.close()
    try:
        release_app_mutex()
        launch_desktop()
    except OSError as error:
        _log.error("配置导入后无法自动重启桌面端", error=error)
        QMessageBox.critical(None, app_fluent_window.tra("重启失败"),
                             app_fluent_window.tra("配置已导入，请手动重新打开 AiNiee。"))
        return 1
    return 0
