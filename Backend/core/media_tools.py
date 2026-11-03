"""Resolve the release's FFmpeg tools without depending on cwd or system PATH."""
from pathlib import Path
import shutil
import sys


def bundled_media_tools_dir():
    # PyInstaller exposes both onedir files and macOS Frameworks/Resources
    # symlinks beneath _MEIPASS, independently of AINIEE_APP_ROOT/user data.
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) / "media-tools" if bundle else None


def find_media_tool(name):
    if name not in ("ffmpeg", "ffprobe"):
        raise ValueError(f"Unknown media tool: {name}")
    directory = bundled_media_tools_dir()
    if directory is not None:
        candidate = directory / (name + (".exe" if sys.platform == "win32" else ""))
        if candidate.is_file():
            return str(candidate.resolve())
    return shutil.which(name)


def missing_media_tool_message(name):
    return f"未找到 {name}，请重新解压完整发布包；源码运行请安装 FFmpeg 并加入 PATH"
