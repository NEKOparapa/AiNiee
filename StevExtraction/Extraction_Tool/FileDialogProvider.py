from pathlib import Path

from PyQt5.QtWidgets import QFileDialog

from ModuleFolders.Infrastructure.Platform.PlatformPaths import ensure_user_dirs, is_macos, user_data_root


def _dialog_start_directory(directory: str | Path | None = "") -> str:
    if directory:
        return str(Path(directory).expanduser())
    if is_macos():
        # 旧提取工具保持独立 provider，避免直接依赖主界面的文件选择实现。
        ensure_user_dirs()
        return str(user_data_root())
    return ""


def get_existing_directory(parent, title: str, directory: str | Path | None = "") -> str:
    return QFileDialog.getExistingDirectory(
        parent,
        title,
        _dialog_start_directory(directory),
        QFileDialog.ShowDirsOnly,
    )
