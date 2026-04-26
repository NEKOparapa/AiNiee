"""应用里用到的路径都放这里。

这里只管算路径，创建目录和迁移文件放到运行时流程里做。
"""

import os
import platform
import sys
from pathlib import Path


MACOS_APP_NAME = "AiNiee"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


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

    if _is_macos():
        return Path.home() / "Library" / "Application Support" / MACOS_APP_NAME
    return writable_root()


# 应用运行缓存目录。
def cache_root() -> Path:
    override = os.environ.get("AINIEE_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return Path.home() / "Library" / "Caches" / MACOS_APP_NAME
    return writable_root() / "ProjectCache"


# 翻译项目的历史缓存目录。
def project_cache_root() -> Path:
    override = os.environ.get("AINIEE_PROJECT_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return user_data_root() / "ProjectCache"
    return writable_root() / "ProjectCache"


# tiktoken 实际使用的缓存目录。
def tiktoken_cache_dir() -> Path:
    override = os.environ.get("AINIEE_TIKTOKEN_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return cache_root() / "tiktoken"
    return resource_path("Models", "tiktoken")


# 打包自带的 tiktoken 编码文件。
def bundled_tiktoken_cache_dir() -> Path:
    return resource_path("Models", "tiktoken")


# 更新包下载目录。
def downloads_dir() -> Path:
    override = os.environ.get("AINIEE_DOWNLOADS_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return user_data_root() / "downloads"
    return writable_root() / "downloads"


# 主配置文件。
def config_path() -> Path:
    if _is_macos():
        return user_data_root() / "config.json"
    return writable_root() / "Resource" / "config.json"


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
