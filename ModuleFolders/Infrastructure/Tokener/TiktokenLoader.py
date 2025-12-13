import os
import sys
import time
import shutil
import hashlib
from typing import Optional

try:
    import rich

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# 全局单例
_TIKTOKEN_INITIALIZED = False
_TIKTOKEN_CACHE_DIR = None


def _print_info(msg: str):
    """统一的信息输出"""
    if RICH_AVAILABLE:
        rich.print(f"[[green]INFO[/]] {msg}")
    else:
        print(f"[INFO] {msg}")


def _print_warning(msg: str):
    """统一的警告输出"""
    if RICH_AVAILABLE:
        rich.print(f"[[yellow]WARNING[/]] {msg}")
    else:
        print(f"[WARNING] {msg}")


def _print_error(msg: str):
    """统一的错误输出"""
    if RICH_AVAILABLE:
        rich.print(f"[[red]ERROR[/]] {msg}")
    else:
        print(f"[ERROR] {msg}")


def initialize_tiktoken():
    """
    初始化 tiktoken 编码器缓存目录（全局单例）

    设置 tiktoken 的缓存目录为 Resource/Models/tiktoken，
    避免依赖网络下载和系统临时目录。

    Returns:
        str: 缓存目录路径

    Raises:
        RuntimeError: 如果初始化失败
    """
    global _TIKTOKEN_INITIALIZED, _TIKTOKEN_CACHE_DIR

    if _TIKTOKEN_INITIALIZED:
        return _TIKTOKEN_CACHE_DIR

    _print_info("初始化 tiktoken 编码器缓存...")
    start_time = time.time()

    try:
        # 1. 确定缓存目录
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        cache_dir = os.path.join(script_dir, "Resource", "Models", "tiktoken")

        # 2. 创建目录（如果不存在）
        os.makedirs(cache_dir, exist_ok=True)

        # 3. 设置环境变量（必须在导入 tiktoken 前设置）
        os.environ['TIKTOKEN_CACHE_DIR'] = cache_dir
        _TIKTOKEN_CACHE_DIR = cache_dir

        # 4. ⚠️ 应用 babeldoc 补丁，防止后续导入的包覆盖环境变量
        try:
            from ModuleFolders.Infrastructure.Tokener.BabeldocPatch import apply_patch
            apply_patch(cache_dir)
        except ImportError:
            _print_warning("BabeldocPatch 模块未找到，可能无法防止环境变量被覆盖")

        # 5. 验证目录可写
        test_file = os.path.join(cache_dir, ".test_write")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            raise RuntimeError(f"缓存目录不可写: {cache_dir}") from e

        # 6. 检查必需的编码文件是否存在
        required_encodings = {
            "o200k_base": {
                "url": "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken",
                "size": 3613922,
            },
            "cl100k_base": {
                "url": "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
                "size": 1681126,
            }
        }

        missing_files = []
        for name, info in required_encodings.items():
            cache_key = hashlib.sha1(info["url"].encode()).hexdigest()
            cache_file = os.path.join(cache_dir, cache_key)

            if not os.path.exists(cache_file):
                missing_files.append(name)
            else:
                # 验证文件大小
                actual_size = os.path.getsize(cache_file)
                if abs(actual_size - info["size"]) > 1024:  # 允许 1KB 误差
                    _print_warning(
                        f"{name} 缓存文件大小异常 "
                        f"(预期: {info['size']:,}, 实际: {actual_size:,})"
                    )

        if missing_files:
            _print_warning(
                f"以下编码文件缺失: {', '.join(missing_files)}\n"
                f"首次使用时将尝试从网络下载到: {cache_dir}"
            )

        _TIKTOKEN_INITIALIZED = True

        load_time_ms = (time.time() - start_time) * 1000
        _print_info(f"tiktoken 缓存目录已设置: {cache_dir} ({load_time_ms:.2f} ms)")

        return cache_dir

    except Exception as e:
        _print_error(f"初始化 tiktoken 失败: {e}")
        raise RuntimeError("tiktoken 初始化失败") from e


def get_tiktoken_cache_dir() -> Optional[str]:
    """
    获取 tiktoken 缓存目录路径

    Returns:
        str: 缓存目录路径，如果未初始化则返回 None
    """
    return _TIKTOKEN_CACHE_DIR


def copy_cache_from_system_temp():
    """
    从系统临时目录复制现有的 tiktoken 缓存文件

    用于首次部署时，将开发环境的缓存文件复制到应用目录
    """
    if not _TIKTOKEN_INITIALIZED:
        _print_error("请先调用 initialize_tiktoken()")
        return

    import tempfile

    # 系统临时目录中的缓存
    src_cache_dir = os.path.join(tempfile.gettempdir(), "data-gym-cache")

    if not os.path.exists(src_cache_dir):
        _print_warning(f"系统临时缓存目录不存在: {src_cache_dir}")
        return

    src_files = os.listdir(src_cache_dir)
    if not src_files:
        _print_warning("系统临时缓存目录为空")
        return

    _print_info(f"从系统临时目录复制缓存文件...")

    copied_count = 0
    for filename in src_files:
        src_file = os.path.join(src_cache_dir, filename)
        dst_file = os.path.join(_TIKTOKEN_CACHE_DIR, filename)

        # 跳过已存在的文件
        if os.path.exists(dst_file):
            continue

        try:
            shutil.copy2(src_file, dst_file)
            size = os.path.getsize(dst_file)
            _print_info(f"  已复制: {filename} ({size:,} bytes)")
            copied_count += 1
        except Exception as e:
            _print_warning(f"  复制失败: {filename} - {e}")

    if copied_count > 0:
        _print_info(f"成功复制 {copied_count} 个缓存文件")
    else:
        _print_info("没有需要复制的文件")


def verify_encoding(encoding_name: str = "o200k_base") -> bool:
    """
    验证指定的编码器是否可用

    Args:
        encoding_name: 编码器名称

    Returns:
        bool: 编码器是否可用
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding_name)

        # 测试编码
        test_text = "Hello, 世界"
        tokens = enc.encode(test_text)

        _print_info(f"✓ {encoding_name} 编码器可用 (测试: {len(tokens)} tokens)")
        return True

    except Exception as e:
        _print_error(f"✗ {encoding_name} 编码器不可用: {e}")
        return False
