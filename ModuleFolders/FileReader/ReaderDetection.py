
import os
from pathlib import Path

import chardet
from magika.types import OverwriteReason

# 全局单例
_MAGIKA_INSTANCE = None


def get_magika():
    global _MAGIKA_INSTANCE
    if _MAGIKA_INSTANCE is None:
        from magika import Magika
        _MAGIKA_INSTANCE = Magika()
    return _MAGIKA_INSTANCE


def detect_file_encoding(file_path: str | Path, min_confidence: float = 0.75) -> str:
    """
    使用Magika检测文件类型，如果是非纯文本则返回'non_text/{label}'，
    如果是纯文本则使用chardet检测编码。

    Args:
        file_path: 要检测的文件路径
        min_confidence: chardet检测编码的最低置信度阈值，低于此值将返回默认编码'utf-8'

    Returns:
        str: 对于非文本文件返回'non_text/{label}'，对于文本文件返回检测到的编码
    """
    # 确保file_path是Path对象
    if isinstance(file_path, str):
        file_path = Path(file_path)

    # 使用Magika检测文件类型
    result = get_magika().identify_path(file_path)
    non_text = not result.output.is_text
    is_low_confidence = result.prediction.overwrite_reason == OverwriteReason.LOW_CONFIDENCE

    # 如果文件为非文本类型且没有触发`is_low_confidence`条件。则返回non_text/xxx
    # 否则继续使用chardet检查编码
    if non_text and not is_low_confidence:
        # 非文本文件，返回non_text前缀加上检测到的标签
        return f"non_text/{result.output.label}"

    # 读取文件内容
    with open(file_path, 'rb') as f:
        content_bytes = f.read()

    # 文件是文本类型，使用chardet检测编码
    detection_result = chardet.detect(content_bytes)
    detected_encoding = detection_result['encoding']
    confidence = detection_result['confidence']

    # 如果没有检测到编码或置信度低于阈值，返回默认编码'utf-8'
    if not detected_encoding or confidence < min_confidence:
        return 'utf-8'

    return detected_encoding


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
