import os
import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import chardet

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject


@dataclass
class InputConfig:
    input_root: Path


class BaseSourceReader(ABC):
    """Reader基类，在其生命周期内可以输入多个文件"""
    def __init__(self, input_config: InputConfig) -> None:
        self.input_config = input_config

    def __enter__(self):
        """申请整个Reader生命周期用到的耗时资源，单个文件的资源则在read_source_file方法中申请释放"""
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """释放耗时资源"""
        pass

    @classmethod
    @abstractmethod
    def get_project_type(cls) -> str:
        """获取Reader对应的项目类型标识符（用于动态实例化），如 Mtool"""
        pass

    @property
    @abstractmethod
    def support_file(self) -> str:
        """该读取器支持处理的文件扩展名（不带点），如 json"""
        pass

    @abstractmethod
    def read_source_file(self, file_path: Path, cache_project: CacheProject) -> list[CacheItem]:
        """读取文件内容，并返回原文(译文)片段"""
        pass

    def can_read(self, file_path: Path) -> bool:
        """验证文件兼容性，返回False则不会读取该文件"""
        if file_path.suffix.replace('.', '', 1) != self.support_file:
            return False
        return True


# 存储文本对及翻译状态信息
def text_to_cache_item(source_text, translated_text: str = None):
    item = CacheItem({})
    item.set_source_text(source_text)
    if translated_text is None:
        translated_text = source_text
    item.set_translated_text(translated_text)
    item.set_translation_status(CacheItem.STATUS.UNTRANSLATED)
    return item


def detect_newlines(content: str) -> str:
    """
    检测文本内容中使用的换行符类型

    Args:
        content: 文本内容（字符串类型）

    Returns:
        str: 检测到的换行符（'\r\n', '\n', 或 '\r'）
    """
    crlf_count = content.count('\r\n')  # Windows: \r\n
    lf_count = content.count('\n') - crlf_count  # Unix/Linux/macOS: \n (减去CRLF中的\n)
    cr_count = content.count('\r') - crlf_count  # 旧Mac: \r (减去CRLF中的\r)

    # 判断主要使用的换行符
    if crlf_count > lf_count and crlf_count > cr_count:
        # Windows 系统的换行符
        return "\r\n"
    elif lf_count > crlf_count and lf_count > cr_count:
        # Unix/Linux 系统的换行符
        return "\n"
    elif cr_count > crlf_count and cr_count > lf_count:
        # 早期 Mac OS 的换行符
        return "\r"
    else:
        # 默认使用系统对应的换行符
        return os.linesep


def read_file_safely(file_path: Union[str, pathlib.Path], cache_project: CacheProject) -> str:
    """
    安全地读取文本文件，自动检测并使用正确的编码和换行符格式，并将这些信息保存到cache_project中。
    结合BOM检测和chardet库进行编码识别

    Args:
        file_path: 文件路径，可以是字符串或Path对象
        cache_project: 缓存项目对象，用于存储文件的编码和换行符信息

    Returns:
        str: 文件内容

    Raises:
        UnicodeDecodeError: 当无法用任何可靠的编码读取文件时
        FileNotFoundError: 当文件不存在时
        PermissionError: 当没有权限读取文件时
    """
    # 确保file_path是Path对象
    if isinstance(file_path, str):
        file_path = pathlib.Path(file_path)

    # 读取文件内容
    with open(file_path, 'rb') as f:
        content_bytes = f.read()

    # 优先使用chardet检测编码
    detection_result = chardet.detect(content_bytes)
    # 检测到的编码
    detected_encoding = detection_result['encoding']
    # 置信度
    confidence = detection_result['confidence']

    # 如果置信度太低，尝试原来的编码列表
    if not detected_encoding or confidence < 0.75:
        content, detected_encoding = decode_content_bytes(content_bytes)
    else:
        # 使用chardet检测到的编码
        try:
            content = content_bytes.decode(detected_encoding)
        except UnicodeDecodeError:
            # 即使chardet也失败了，尝试您的编码列表
            content, detected_encoding = decode_content_bytes(content_bytes)

    # 检测换行符格式
    detected_line_ending = detect_newlines(content)

    # 将检测到的编码和换行符格式保存到cache_project中
    cache_project.set_file_encoding(detected_encoding)
    cache_project.set_line_ending(detected_line_ending)

    return content


def decode_content_bytes(content_bytes):
    detected_encoding = None
    content = ""

    encodings = ['utf-8', 'utf-16-le', 'utf-16-be', 'gbk', 'gb2312', 'big5', 'shift-jis']
    decode_errors = []
    for encoding in encodings:
        try:
            content = content_bytes.decode(encoding)
            detected_encoding = encoding
            break
        except UnicodeDecodeError as e:
            decode_errors.append((encoding, str(e)))
    # 如果所有尝试都失败，抛出详细的异常
    if not detected_encoding:
        error_details = '\n'.join([f"{enc}: {err}" for enc, err in decode_errors])
        raise UnicodeDecodeError(
            "unknown",
            content_bytes,
            0,
            len(content_bytes),
            f"无法使用任何可靠的编码读取文件。尝试了chardet和以下编码:\n{error_details}"
        )
    return content, detected_encoding
