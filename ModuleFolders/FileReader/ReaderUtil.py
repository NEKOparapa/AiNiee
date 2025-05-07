import os
import pathlib
import re
import sys
import time
from typing import Union

import chardet
import charset_normalizer
import rich
from mediapipe.tasks.python import text, BaseOptions
from mediapipe.tasks.python.text import LanguageDetector

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem

_LANG_DETECTOR_INSTANCE: LanguageDetector | None = None
"""语言检测器单例实现"""
HAS_UNUSUAL_ENG_REGEX = re.compile(
    r"^(?:(?=.*_)(?=.*[a-zA-Z0-9])\S*|(?=.*[a-zA-Z])(?=.*[0-9])[a-zA-Z0-9]*)$"
)
"""预编译正则 匹配包含 至少一个下划线和至少一个字母与数字且没有空白字符 或者 只由字母和数字组成且必须同时包含至少一个字母与数字 的字符串"""

# 加载语言检测器(全局)
def get_lang_detector():
    """获取语言检测器的全局单例实例"""
    global _LANG_DETECTOR_INSTANCE
    if _LANG_DETECTOR_INSTANCE is None:
        rich.print("[[green]INFO[/]] 加载 MediaPipe 文本语言检测器中...")
        # Record start time
        start_time = time.time()

        # 设置模型目录
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        model_path = os.path.join(script_dir, "Resource", "Models", "mediapipe", "language_detector.tflite")

        base_options = BaseOptions(model_asset_path=model_path)
        options = text.LanguageDetectorOptions(base_options=base_options, max_results=1)
        _LANG_DETECTOR_INSTANCE = text.LanguageDetector.create_from_options(options)

        # Calculate load time in milliseconds
        load_time_ms = (time.time() - start_time) * 1000
        rich.print(f"[[green]INFO[/]] MediaPipe 文本语言检测器已加载! ({load_time_ms:.2f} ms)")
    return _LANG_DETECTOR_INSTANCE

# 释放语言检测器
def close_lang_detector():
    """关闭并释放语言检测器的全局单例实例"""
    global _LANG_DETECTOR_INSTANCE
    if _LANG_DETECTOR_INSTANCE is not None:
        # MediaPipe任务通常有close方法用于释放资源
        try:
            _LANG_DETECTOR_INSTANCE.close()
            rich.print("[[green]INFO[/]]  MediaPipe 文本语言检测器已释放!")
        except AttributeError:
            # 如果没有close方法，尝试其他可能的清理方法
            if hasattr(_LANG_DETECTOR_INSTANCE, 'release'):
                _LANG_DETECTOR_INSTANCE.release()
        finally:
            # 无论如何都将实例设置为None，允许垃圾回收
            _LANG_DETECTOR_INSTANCE = None
    return True

# 检测文件编码
def detect_file_encoding(file_path: Union[str, pathlib.Path], min_confidence: float = 0.75) -> str:
    """
    使用`charset_normalizer`与`chardet`检测文件编码

    Args:
        file_path: 要检测的文件路径
        min_confidence: chardet检测编码的最低置信度阈值，低于此值将返回默认编码'utf-8'

    Returns:
        str: 默认/检测失败时返回`utf-8`，否则返回检测到的编码
    """
    # 确保file_path是Path对象
    if isinstance(file_path, str):
        file_path = pathlib.Path(file_path)

    try:
        cn_result = charset_normalizer.from_path(file_path).best()

        # 如果`charset_normalizer`有检测到结果，直接使用结果
        if cn_result:
            detected_encoding = cn_result.encoding
            confidence = 1.0
        else:
            # 如果没有检测到结果，回退到使用`chardet`
            # 读取文件内容
            with open(file_path, 'rb') as f:
                content_bytes = f.read()

            # 文件是文本类型，使用chardet检测编码
            detection_result = chardet.detect(content_bytes)
            detected_encoding = detection_result['encoding']
            confidence = detection_result['confidence']

            rich.print(f"[[red]WARNING[/]] 文件 {file_path} 编码检测失败，回退到使用`chardet`检测: {detected_encoding} - {confidence}")

        # 如果没有检测到编码或置信度低于阈值，返回默认编码'utf-8'
        if not detected_encoding or confidence < min_confidence:
            rich.print(f"[[red]WARNING[/]] 文件 {file_path} 编码检测失败，默认使用`utf-8`编码")
            return 'utf-8'

        return detected_encoding

    except Exception as e:
        print(f"[[red]ERROR[/]] 文件 {file_path} 检测过程出错: {str(e)}")
        return 'utf-8'  # 出错时返回默认编码

# 检测文本语言
def detect_language_with_context(item: CacheItem, index: int, file_data: CacheFile) -> tuple[str, float]:
    """检测语言，为短文本提供上下文支持

    Args:
        item: 当前处理的缓存项
        index: 当前项在items列表中的索引
        file_data: 包含所有项的文件数据

    Returns:
        tuple: (语言代码, 置信度)
    """
    # min_text_length = 6  # 定义短文本的阈值

    # 获取原文并清理
    source_text = item.source_text
    if not source_text:
        return 'no_text', -1.0

    cleaned_text = clean_text(source_text.strip())

    # 检查是否只包含符号
    if is_symbols_only(cleaned_text):
        return 'symbols_only', -1.0

    # Todo: 处理短文本：获取上下文（暂时不采用）
    # if len(cleaned_text) < min_text_length:
    #     # 构建上下文文本
    #     context_texts = []
    #
    #     # 获取前一个项目的文本(如果存在)
    #     if index > 0:
    #         prev_text = clean_text(file_data.items[index - 1].source_text.strip())
    #         context_texts.append(prev_text)
    #
    #     # 添加当前文本
    #     context_texts.append(cleaned_text)
    #
    #     # 获取后一个项目的文本(如果存在)
    #     if index < len(file_data.items) - 1:
    #         next_text = clean_text(file_data.items[index + 1].source_text.strip())
    #         context_texts.append(next_text)
    #
    #     # 用表意换行符连接上下文
    #     detection_text = "\\n".join(context_texts)
    # else:
    #     # 文本长度足够，直接使用当前文本
    #     detection_text = cleaned_text

    # 使用mediapipe的语言检测任务
    lang_result = get_lang_detector().detect(cleaned_text).detections
    if not lang_result:
        return 'un', -1.0
    else:
        probability = lang_result[0].probability
        """获取到的置信度"""
        if HAS_UNUSUAL_ENG_REGEX.match(cleaned_text):
            # 如果匹配到目标字符，则置信度降低0.15
            probability -= 0.15
        return lang_result[0].language_code, lang_result[0].probability

# 辅助函数，用于清理文本
def clean_text(source_text):
    # 步骤1：先将所有换行符替换为一个特殊标记
    text_with_marker = re.sub(r'\r\n|\r|\n', '__NEWLINE__', source_text)

    # 步骤2：正常处理其他空白字符
    cleaned_text = re.sub(r'\s+', ' ', text_with_marker.strip())

    # 步骤3：将标记替换回字面的'\n'
    return cleaned_text.replace('__NEWLINE__', '\\n')

# 辅助函数，用于检查文本是否只包含符号
def is_symbols_only(source_text: str):
    cleaned_text = source_text.strip()
    if not cleaned_text:  # 检查是否为空字符串
        return False
    # 检查每个字符是否都不是字母数字
    return all(not c.isalnum() for c in cleaned_text)


# 检测换行符类型
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
