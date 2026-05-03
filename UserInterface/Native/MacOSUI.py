from typing import Callable

from ModuleFolders.Config.FilePathConfig import MACOS_APP_NAME, config_path


MACOS_PROJECT_URL = "https://github.com/NEKOparapa/AiNiee"


def command_shortcut(key: str) -> str:
    """Qt 会在 macOS 上把 Ctrl 显示成 Command。"""
    return f"Ctrl+{key}"


def about_message(version: str, tra: Callable[[str], str] = lambda text: text) -> str:
    return "\n".join(
        [
            tra("AiNiee"),
            version,
            "",
            tra("AiNiee macOS 支持"),
            f"GitHub: {MACOS_PROJECT_URL}",
            f"{tra('配置目录')}: {config_path()}",
        ]
    )


def app_menu_title() -> str:
    return MACOS_APP_NAME
