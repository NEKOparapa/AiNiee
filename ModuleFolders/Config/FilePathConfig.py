"""应用里用到的路径都放这里。

这里只管算路径，创建目录和迁移文件放到运行时流程里做。
"""

import os
import platform
import sys
from pathlib import Path


MACOS_APP_NAME = "AiNiee"
WIN_APP_NAME = "AiNiee"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_windows() -> bool:
    return platform.system() == "Windows"


# 源码运行时的仓库根目录。
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


# 程序实际启动的位置。
def executable_root() -> Path:
    # 打包后用可执行文件旁边的位置，别写进 PyInstaller 临时目录。
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return repo_root()


# 普通可写文件默认放这里。
def writable_root() -> Path:
    return executable_root()


def _win_local_app_data() -> Path:
    """Windows %LOCALAPPDATA% (C:\\Users\\<user>\\AppData\\Local)，回落 home/AppData/Local。"""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


# 便携模式：源码运行默认开启；打包版需 portable.txt（Windows zip）或 AINIEE_PORTABLE=1。
# 数据全部放在程序/仓库旁；可用 AINIEE_PORTABLE=0 强制关闭。
_PORTABLE_WRITABLE_CACHE = None


def _portable_marker_present() -> bool:
    if not (getattr(sys, "frozen", False) and _is_windows()):
        return False
    return (executable_root() / "portable.txt").exists()


def _probe_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".ainiee_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _portable_writable() -> bool:
    global _PORTABLE_WRITABLE_CACHE
    if _PORTABLE_WRITABLE_CACHE is None:
        _PORTABLE_WRITABLE_CACHE = _probe_writable(executable_root())
    return _PORTABLE_WRITABLE_CACHE


def _portable_requested() -> bool:
    flag = os.environ.get("AINIEE_PORTABLE")
    if flag == "1":
        return True
    if flag == "0":
        return False
    if not getattr(sys, "frozen", False):
        return True
    return _portable_marker_present()


def _portable_mode() -> bool:
    return _portable_requested() and _portable_writable()


# 想便携但目录不可写 → 已回落标准位置，启动期据此弹一次提示。
def portable_fallback_active() -> bool:
    return _portable_requested() and not _portable_writable()


# 打包后的 Windows 安装版：{app} 下存在安装器（[Files]）写入的 installed.flag。
def is_windows_installer_build() -> bool:
    if not (_is_windows() and getattr(sys, "frozen", False)):
        return False
    # 便携标记优先于可能残留的 installed.flag（便携 zip 自带 portable.txt）。
    if _portable_marker_present():
        return False
    return (executable_root() / "installed.flag").exists()


# 随程序打包的 Resource 目录。
def resource_root() -> Path:
    override = os.environ.get("AINIEE_RESOURCE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "Resource")
        candidates.append(Path(sys._MEIPASS).parent / "Resources" / "Resource")

    app_contents = executable_root().parent
    candidates.extend(
        [
            app_contents / "Resources" / "Resource",
            executable_root() / "Resource",
            repo_root() / "Resource",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


# Resource 里的具体文件。
def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


# 用户自己的配置和数据目录。
def user_data_root() -> Path:
    override = os.environ.get("AINIEE_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos() and not _portable_mode():
        return Path.home() / "Library" / "Application Support" / MACOS_APP_NAME
    if _is_windows() and not _portable_mode():
        return _win_local_app_data() / WIN_APP_NAME
    return writable_root()


def _has_user_data_override() -> bool:
    return bool(os.environ.get("AINIEE_USER_DATA_DIR"))


# 是否走平台标准用户目录（而不是 exe 旁边）。
def _uses_standard_user_dir() -> bool:
    if _has_user_data_override():
        return True
    return (_is_macos() or _is_windows()) and not _portable_mode()


# 应用运行缓存目录。
def cache_root() -> Path:
    override = os.environ.get("AINIEE_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos() and not _portable_mode():
        return Path.home() / "Library" / "Caches" / MACOS_APP_NAME
    if _is_windows() and not _portable_mode():
        return _win_local_app_data() / WIN_APP_NAME / "Cache"
    return writable_root() / "ProjectCache"


# 翻译项目的历史缓存目录。
def project_cache_root() -> Path:
    override = os.environ.get("AINIEE_PROJECT_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if os.environ.get("AINIEE_CACHE_DIR"):
        return cache_root()

    if _uses_standard_user_dir():
        return user_data_root() / "ProjectCache"
    return cache_root()


# tiktoken 实际使用的缓存目录。
def tiktoken_cache_dir() -> Path:
    override = os.environ.get("AINIEE_TIKTOKEN_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos() or _is_windows():
        return cache_root() / "tiktoken"
    return resource_path("Models", "tiktoken")


# 打包自带的 tiktoken 编码文件。
def bundled_tiktoken_cache_dir() -> Path:
    return resource_path("Models", "tiktoken")


# 用户日志目录。
def user_log_dir() -> Path:
    override = os.environ.get("AINIEE_LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos() and not _portable_mode():
        return Path.home() / "Library" / "Logs" / MACOS_APP_NAME
    if _is_windows() and not _portable_mode():
        return _win_local_app_data() / WIN_APP_NAME / "Logs"
    return writable_root() / "Logs"


# 更新包下载目录。
def downloads_dir() -> Path:
    override = os.environ.get("AINIEE_DOWNLOADS_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _uses_standard_user_dir():
        return user_data_root() / "downloads"
    return writable_root() / "downloads"


# 主配置文件。
def config_path() -> Path:
    if _uses_standard_user_dir():
        return user_data_root() / "config.json"
    return writable_root() / "Resource" / "config.json"


# 用户可见的默认输入/输出目录（绝对路径，跨平台）。
def documents_root() -> Path:
    override = os.environ.get("AINIEE_DOCUMENTS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Documents"


def default_input_dir() -> Path:
    if _portable_mode():
        return executable_root() / "input"
    return documents_root() / "AiNiee" / "input"


def default_output_dir() -> Path:
    if _portable_mode():
        return executable_root() / "output"
    return documents_root() / "AiNiee" / "output"


def default_polish_output_dir() -> Path:
    if _portable_mode():
        return executable_root() / "polish_output"
    return documents_root() / "AiNiee" / "polish_output"


# 自动输出目录：输入文件夹的平级 AiNieeOutput。
def auto_output_dir(input_path: str) -> str:
    parent = os.path.dirname(os.path.abspath(input_path))
    return os.path.join(parent, "AiNieeOutput")


# 自动润色输出目录：输入文件夹的平级 AiNieePolishOutput。
def auto_polish_output_dir(input_path: str) -> str:
    parent = os.path.dirname(os.path.abspath(input_path))
    return os.path.join(parent, "AiNieePolishOutput")


# 把存储的路径解析成绝对路径：非字符串、空或相对值回落到可见的默认目录。
def resolve_user_dir(value, fallback: Path) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            candidate = Path(text).expanduser()
            if candidate.is_absolute():
                return str(candidate)
    return str(fallback)


# 接口预设文件。
def platform_preset_path() -> Path:
    return resource_path("platforms", "preset.json")


# 接口图标目录里的文件。
def platform_icon_path(file_name: str) -> Path:
    return resource_path("platforms", "Icon", file_name)


# 提示词模板文件。
def prompt_path(*parts: str) -> Path:
    return resource_path("Prompt", *parts)


# 正则规则文件。
def regex_path(file_name: str) -> Path:
    return resource_path("Regex", file_name)


# 翻译结果检查用的正则规则。
def check_regex_path() -> Path:
    return regex_path("check_regex.json")
