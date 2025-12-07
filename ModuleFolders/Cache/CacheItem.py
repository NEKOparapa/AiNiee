from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional

from ModuleFolders.Cache.BaseCache import ExtraMixin, ThreadSafeCache

# ============================================================
# 条件导入 TiktokenLoader（在文件顶部）
# ============================================================
try:
    from ModuleFolders.TiktokenLoader import get_tiktoken_cache_dir

    TIKTOKEN_LOADER_AVAILABLE = True
except ImportError:
    # 必须在 except 块中也定义这个名字
    get_tiktoken_cache_dir = None  # type: ignore
    TIKTOKEN_LOADER_AVAILABLE = False


class TranslationStatus:
    UNTRANSLATED = 0  # 待翻译
    TRANSLATED = 1  # 已翻译
    POLISHED = 2  # 已润色
    EXCLUDED = 7  # 已排除


@dataclass(repr=False)
class CacheItem(ThreadSafeCache, ExtraMixin):
    # 类级别的 tiktoken 编码器缓存（全局单例）
    _encoding: ClassVar[Optional[Any]] = None
    _encoding_failed: ClassVar[bool] = False
    _encoding_error_msg: ClassVar[str] = ""

    # 实例字段
    text_index: int = 0
    translation_status: int = 0
    model: str = ''
    source_text: str = ''
    translated_text: str = None
    polished_text: str = None
    text_to_detect: str = None
    """处理后的待（语言）检测文本"""
    lang_code: tuple[str, float, list[str]] | None = None
    """当前行的语言代码 格式: [语言代码, 置信度, 除最高置信度外的语言代码列表]"""
    extra: dict[str, Any] = field(default_factory=dict)
    """额外属性，用于存储特定reader产生的原文片段的额外属性，共用属性请加到CacheItem中"""

    def __post_init__(self):
        """初始化后处理，确保字符串字段不为 None"""
        if self.source_text is None:
            self.source_text = ""
        if self.translated_text is None:
            self.translated_text = ""
        if self.polished_text is None:
            self.polished_text = ""

    @property
    def final_text(self) -> str:
        """
        获取最终文本。
        按以下优先级返回：
        1. 润色后的文本 (polished_text)
        2. 翻译后的文本 (translated_text)
        3. 原文 (source_text)
        """
        return self.polished_text or self.translated_text or self.source_text

    @property
    def token_count(self) -> int:
        """获取当前源文本的 token 数量"""
        return self.get_token_count(self.source_text)

    @classmethod
    def _get_cache_dir_info(cls) -> str:
        """
        获取缓存目录信息（独立方法，便于错误处理）

        Returns:
            str: 缓存目录路径或状态信息
        """
        # 检查是否可用（同时检查标志和函数本身）
        if not TIKTOKEN_LOADER_AVAILABLE or get_tiktoken_cache_dir is None:
            return "TiktokenLoader 未导入"

        try:
            cache_dir = get_tiktoken_cache_dir()
            return cache_dir if cache_dir else "未初始化"
        except Exception as e:
            return f"获取失败: {e}"

    @classmethod
    def _get_encoding(cls):
        """
        延迟加载 tiktoken 编码器（全局单例）

        Returns:
            tiktoken.Encoding: 编码器实例

        Raises:
            RuntimeError: 如果编码器加载失败
        """
        # 如果之前加载失败过，直接抛出异常
        if cls._encoding_failed:
            raise RuntimeError(cls._encoding_error_msg)

        # 如果尚未加载，尝试加载
        if cls._encoding is None:
            try:
                import tiktoken
                cls._encoding = tiktoken.get_encoding("o200k_base")

            except ImportError as e:
                cls._encoding_failed = True
                cls._encoding_error_msg = (
                    "tiktoken 库未安装\n\n"
                    "解决方法：\n"
                    "  pip install tiktoken\n"
                    "或在配置中使用「行数限制」而非「Token 限制」"
                )
                raise RuntimeError(cls._encoding_error_msg) from e

            except Exception as e:
                cls._encoding_failed = True

                # 使用独立方法获取缓存目录信息
                cache_dir_info = cls._get_cache_dir_info()

                cls._encoding_error_msg = (
                    f"无法加载 tiktoken 编码器: {e}\n\n"
                    f"缓存目录: {cache_dir_info}\n\n"
                    "可能原因：\n"
                    "1. 编码文件缺失（首次使用需要网络下载）\n"
                    "2. 网络连接问题（无法访问 Azure Blob Storage）\n"
                    "3. 缓存文件损坏\n"
                    "4. tiktoken 初始化未执行\n\n"
                    "解决方法：\n"
                    "1. 在有网络的环境运行 tools/prepare_tiktoken_cache.py\n"
                    "2. 确保 Resource/Models/tiktoken 目录包含编码文件\n"
                    "3. 检查网络连接和代理设置\n"
                    "4. 在配置中使用「行数限制」而非「Token 限制」"
                )
                raise RuntimeError(cls._encoding_error_msg) from e

        return cls._encoding

    @classmethod
    def get_token_count(cls, text: str) -> int:
        """
        计算文本的 token 数量

        Args:
            text: 要计算的文本

        Returns:
            int: token 数量

        Note:
            如果 tiktoken 加载失败，将使用降级估算方法：
            - 英文约 4 字符 = 1 token
            - 中文约 1.5 字符 = 1 token
        """
        # 空文本返回 0
        if not text:
            return 0

        try:
            # 尝试使用 tiktoken 精确计算
            encoding = cls._get_encoding()
            return len(encoding.encode(text))

        except RuntimeError:
            # tiktoken 不可用，使用降级估算方法
            ascii_count = sum(1 for c in text if ord(c) < 128)
            non_ascii_count = len(text) - ascii_count

            # 英文约 4 字符/token，中文约 1.5 字符/token
            estimated_tokens = int(ascii_count / 4 + non_ascii_count / 1.5)

            # 至少返回 1（如果文本非空）
            return max(1, estimated_tokens)

    @classmethod
    def is_tiktoken_available(cls) -> bool:
        """
        检查 tiktoken 编码器是否可用

        Returns:
            bool: 编码器是否可用
        """
        try:
            cls._get_encoding()
            return True
        except RuntimeError:
            return False

    @classmethod
    def reset_encoding_state(cls):
        """
        重置编码器状态（用于测试或重新初始化）

        Warning:
            这会清除已加载的编码器和错误状态，
            下次调用时会重新尝试加载。
        """
        cls._encoding = None
        cls._encoding_failed = False
        cls._encoding_error_msg = ""

    def get_lang_code(self, default_lang=None):
        """
        获取语言代码，可选择使用默认值

        Args:
            default_lang: 默认语言代码

        Returns:
            tuple: (语言代码, 置信度, 其他语言代码列表)
        """
        if self.lang_code is None and default_lang is not None:
            return default_lang, 1.0, []
        return self.lang_code

    def _extra(self) -> dict[str, Any]:
        """
        获取额外属性字典（供 ExtraMixin 使用）

        Returns:
            dict: 额外属性字典
        """
        return self.extra

    def __repr__(self) -> str:
        """自定义字符串表示（用于调试）"""
        status_map = {
            TranslationStatus.UNTRANSLATED: "待翻译",
            TranslationStatus.TRANSLATED: "已翻译",
            TranslationStatus.POLISHED: "已润色",
            TranslationStatus.EXCLUDED: "已排除",
        }
        status_str = status_map.get(self.translation_status, f"未知({self.translation_status})")

        source_preview = (
            self.source_text[:30] + "..."
            if len(self.source_text) > 30
            else self.source_text
        )

        return (
            f"CacheItem(index={self.text_index}, "
            f"status={status_str}, "
            f"source='{source_preview}')"
        )
