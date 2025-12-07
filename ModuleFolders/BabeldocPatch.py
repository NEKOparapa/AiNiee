"""
Babeldoc 补丁模块

用途：阻止 babeldoc 包覆盖 TIKTOKEN_CACHE_DIR 环境变量

原理：
1. 保护模式会拦截 os.environ 的赋值操作
2. 当检测到 babeldoc 尝试修改 TIKTOKEN_CACHE_DIR 时，忽略该操作
3. 保留我们自己设置的缓存路径

使用方法：
    在导入任何可能使用 babeldoc 的模块之前调用 apply_patch()
"""

import os
from typing import Optional

# 全局状态
_PATCH_APPLIED = False
_PROTECTED_CACHE_DIR: Optional[str] = None
_ORIGINAL_SETITEM = None


def apply_patch(custom_cache_dir: str) -> None:
    """
    应用 babeldoc 补丁，保护 TIKTOKEN_CACHE_DIR 不被覆盖

    Args:
        custom_cache_dir: 我们自定义的缓存目录路径
    """
    global _PATCH_APPLIED, _PROTECTED_CACHE_DIR, _ORIGINAL_SETITEM

    if _PATCH_APPLIED:
        # 已经应用过补丁，避免重复
        return

    # 保存我们的缓存路径
    _PROTECTED_CACHE_DIR = custom_cache_dir

    # 保存原始的 __setitem__ 方法
    _ORIGINAL_SETITEM = os.environ.__setitem__

    def protected_setitem(self, key: str, value: str) -> None:
        """
        替换 os.environ 的 __setitem__ 方法

        拦截对 TIKTOKEN_CACHE_DIR 的修改，如果调用者是 babeldoc 则忽略
        """
        if key == "TIKTOKEN_CACHE_DIR":
            # 检查调用栈，判断是否来自 babeldoc
            import inspect

            frame = inspect.currentframe()
            try:
                caller_frame = frame.f_back.f_back  # 跳过两层（自己和 __setitem__ 的包装）

                # 向上遍历调用栈
                while caller_frame:
                    caller_filename = caller_frame.f_code.co_filename
                    # caller_function = caller_frame.f_code.co_name

                    # 检查是否来自 babeldoc 包
                    if "babeldoc" in caller_filename:
                        # print(f"[BabeldocPatch] 检测到 babeldoc 尝试修改 TIKTOKEN_CACHE_DIR")
                        # print(f"  来源: {caller_filename}:{caller_frame.f_lineno} in {caller_function}")
                        # print(f"  babeldoc 尝试设置: {value}")
                        # print(f"  保持我们的设置: {_PROTECTED_CACHE_DIR}")
                        # 忽略 babeldoc 的设置，直接返回
                        return

                    caller_frame = caller_frame.f_back

            finally:
                # 清理 frame 引用，避免内存泄漏
                del frame

        # 其他情况，使用原始方法正常设置
        _ORIGINAL_SETITEM(self, key, value)

    # 替换 os.environ 的 __setitem__ 方法
    # 使用 type() 获取 os.environ 的类型，然后设置其方法
    environ_class = type(os.environ)
    environ_class.__setitem__ = protected_setitem

    _PATCH_APPLIED = True

    print(f"[BabeldocPatch] 补丁已应用")
    print(f"  保护的缓存目录: {_PROTECTED_CACHE_DIR}")


def remove_patch() -> None:
    """
    移除补丁，恢复原始行为（通常用于测试）
    """
    global _PATCH_APPLIED, _ORIGINAL_SETITEM

    if not _PATCH_APPLIED or _ORIGINAL_SETITEM is None:
        return

    # 恢复原始方法
    environ_class = type(os.environ)
    environ_class.__setitem__ = _ORIGINAL_SETITEM

    _PATCH_APPLIED = False
    print("[BabeldocPatch] 补丁已移除")


def is_patch_applied() -> bool:
    """
    检查补丁是否已应用

    Returns:
        bool: 补丁是否已应用
    """
    return _PATCH_APPLIED


def get_protected_cache_dir() -> Optional[str]:
    """
    获取受保护的缓存目录路径

    Returns:
        str: 缓存目录路径，如果未应用补丁则返回 None
    """
    return _PROTECTED_CACHE_DIR
