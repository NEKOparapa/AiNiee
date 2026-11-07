"""Validate a desktop release before shutting down its backend."""
from pathlib import PurePosixPath
from zipfile import ZipFile


def validate_windows_update(path):
    with ZipFile(path) as archive:
        names = set()
        for entry in archive.infolist():
            name = entry.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or any(":" in part for part in parts):
                raise ValueError("更新包包含不安全的文件路径")
            if not entry.is_dir():
                names.add(name.lower())
        roots = [name[:-len("ainiee.exe")] for name in names
                 if PurePosixPath(name).name == "ainiee.exe"]
        if len(roots) != 1:
            raise ValueError("更新包必须包含唯一的 AiNiee.exe")
        root = roots[0]
        required = ("backend/ainieebackend.exe",)
        if (any(root + name not in names for name in required)
                or not any(name.startswith(root + "_internal/") for name in names)
                or not any(name.startswith(root + "backend/_internal/") for name in names)):
            raise ValueError("更新包缺少配套的前端或后端，请下载完整的 Windows 发布包")
