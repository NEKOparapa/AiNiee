import re
from pathlib import Path
from typing import Callable

from PyQt5.QtWidgets import QFileDialog

from ModuleFolders.Infrastructure.Platform.PlatformPaths import (
    MACOS_APP_NAME,
    config_path,
    ensure_user_dirs,
    is_macos,
    user_data_root,
)


MACOS_PROJECT_URL = "https://github.com/NEKOparapa/AiNiee"


def command_shortcut(key: str) -> str:
    """Return a shortcut string that Qt renders as Command on macOS."""
    return f"Ctrl+{key}"


def semantic_version(raw_version: str) -> str:
    match = re.search(r"\d+(?:\.\d+){1,3}", raw_version)
    return match.group(0) if match else "0.0.0"


def configure_application_metadata(app, version: str) -> None:
    app.setApplicationName("AiNiee")
    app.setApplicationVersion(semantic_version(version))
    app.setOrganizationName("NEKOparapa")
    app.setOrganizationDomain("github.com/NEKOparapa")
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName("AiNiee")


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


def dialog_start_directory(directory: str | Path | None = "") -> str:
    if directory:
        return str(Path(directory).expanduser())
    if is_macos():
        ensure_user_dirs()
        return str(user_data_root())
    return ""


def get_existing_directory(parent, title: str, directory: str | Path | None = "") -> str:
    return QFileDialog.getExistingDirectory(
        parent,
        title,
        dialog_start_directory(directory),
        QFileDialog.ShowDirsOnly,
    )


def get_open_file_name(parent, title: str, directory: str | Path | None = "", file_filter: str = ""):
    return QFileDialog.getOpenFileName(parent, title, dialog_start_directory(directory), file_filter)


def get_save_file_name(parent, title: str, directory: str | Path | None = "", file_filter: str = ""):
    return QFileDialog.getSaveFileName(parent, title, dialog_start_directory(directory), file_filter)


def input_folder_button_text(tra: Callable[[str], str] = lambda text: text) -> str:
    if is_macos():
        return tra("选择输入文件夹")
    return tra("拖拽/选择输入文件夹")


def choose_input_folder_title(tra: Callable[[str], str] = lambda text: text) -> str:
    return tra("选择输入文件夹") if is_macos() else tra("选择文件夹")


def choose_output_folder_title(tra: Callable[[str], str] = lambda text: text) -> str:
    return tra("选择输出文件夹") if is_macos() else tra("选择文件夹")


def auto_output_path_description(tra: Callable[[str], str] = lambda text: text) -> str:
    if is_macos():
        return tra(
            "启用后，输出文件夹会设置为输入文件夹的同级目录。例如输入文件夹为 ~/Documents/Input，"
            "输出文件夹将设置为 ~/Documents/AiNieeOutput"
        )
    return tra("启用此功能后，设置为输入文件夹的平级目录，比如输入文件夹为D:/Test/Input，输出文件夹将设置为D:/Test/AiNieeOutput")


def app_menu_title() -> str:
    return MACOS_APP_NAME
