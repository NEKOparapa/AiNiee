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
CLEAN_TEXT_PATTERN = re.compile(r'\\{1,2}[a-zA-Z]{1,2}\[\d+]|if\(.{0,8}[vs]\[\d+].{0,16}\)|\\n')
"""预编译正则 清理文本使用"""


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

        if not os.path.exists(model_path):
            rich.print(f"[[red]ERROR[/]] 模型文件不存在于: {model_path}")
            # 您可能希望在此处抛出错误或更优雅地处理
            raise FileNotFoundError(f"在预期位置未找到模型文件: {model_path}")

        try:
            # 使用 Python 的 open 函数读取模型文件到缓冲区后加载模型，兼容路径有中文的情况
            with open(model_path, "rb") as f:  # "rb" 表示二进制读取模式
                model_buffer = f.read()

            # 使用 model_asset_buffer 而不是 model_asset_path
            base_options = BaseOptions(model_asset_buffer=model_buffer)
            # 20250504改动：获取最多四个结果用于重新计算置信度
            options = text.LanguageDetectorOptions(base_options=base_options, max_results=4, score_threshold=0.0001)
            _LANG_DETECTOR_INSTANCE = text.LanguageDetector.create_from_options(options)

            # 计算加载时间（毫秒）
            load_time_ms = (time.time() - start_time) * 1000
            rich.print(f"[[green]INFO[/]] MediaPipe 文本语言检测器已加载! ({load_time_ms:.2f} ms)")

        except Exception as e:
            rich.print(f"[[red]ERROR[/]] 加载 MediaPipe 语言检测器失败: {e}")
            # 重新抛出异常，以便调用者知道出了问题
            # 或者根据您的应用程序进行适当处理。
            raise

    return _LANG_DETECTOR_INSTANCE


# 释放语言检测器
def close_lang_detector():
    """关闭并释放语言检测器的全局单例实例"""
    global _LANG_DETECTOR_INSTANCE
    if _LANG_DETECTOR_INSTANCE is not None:
        # MediaPipe任务通常有close方法用于释放资源
        try:
            _LANG_DETECTOR_INSTANCE.close()
            rich.print("[[green]INFO[/]] MediaPipe 文本语言检测器已释放!")
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

            rich.print(
                f"[[red]WARNING[/]] 文件 {file_path} 编码检测失败，回退到使用`chardet`检测: {detected_encoding} - {confidence}"
            )

        # 如果没有检测到编码或置信度低于阈值，返回默认编码'utf-8'
        if not detected_encoding or confidence < min_confidence:
            rich.print(f"[[red]WARNING[/]] 文件 {file_path} 编码检测失败，默认使用`utf-8`编码")
            return 'utf-8'

        return detected_encoding

    except Exception as e:
        print(f"[[red]ERROR[/]] 文件 {file_path} 检测过程出错: {str(e)}")
        return 'utf-8'  # 出错时返回默认编码


# 检测文本语言
def detect_language_with_mediapipe(items: list[CacheItem], _start_index: int, _file_data: CacheFile) -> \
        list[tuple[list[str], float, float]]:
    """批量检测语言（Mediapipe版本）

    Args:
        items: 当前处理的缓存项列表
        _start_index: 批次中第一项在items列表中的起始索引
        _file_data: 包含所有项的文件数据

    Returns:
        list[tuple]: 每项对应的(语言代码, 置信度)列表
    """
    # 初始化结果列表
    results = []

    # 获取语言检测器（只获取一次以提高效率）
    detector = get_lang_detector()

    for item in items:
        # 获取原文并清理
        source_text = item.source_text
        if source_text is None or not source_text.strip():
            results.append((['no_text'], -1.0, -1.0))
            continue

        cleaned_text = clean_text(source_text)

        # 检查是否只包含符号
        if is_symbols_only(cleaned_text):
            results.append((['symbols_only'], -1.0, -1.0))
            continue

        # 使用mediapipe的语言检测任务
        no_symbols_text = remove_symbols(cleaned_text)
        if not no_symbols_text:
            results.append((['no_text'], -1.0, -1.0))
            continue

        lang_result = detector.detect(no_symbols_text).detections
        if not lang_result:
            results.append((['un'], -1.0, -1.0))
        else:
            raw_prob = lang_result[0].probability
            first_prob = raw_prob
            mediapipe_langs = [detection.language_code for detection in lang_result]

            if HAS_UNUSUAL_ENG_REGEX.match(cleaned_text):
                # 如果匹配到目标字符，则最高置信度降低0.15
                first_prob -= 0.15

            # 如果有至少两个识别结果，则使用最高置信度减去第二个
            if len(lang_result) >= 2:
                # 最终的mediapipe置信度
                first_prob -= lang_result[1].probability

            results.append((mediapipe_langs, first_prob, raw_prob))

    return results


# def detect_language_with_onnx(items: list[CacheItem], _start_index: int, _file_data: CacheFile) -> \
#         list[tuple[list[str], float, float]]:
#     """批量检测语言（ONNX版本）
#
#     Args:
#         items: 当前处理的缓存项列表
#         _start_index: 批次中第一项在items列表中的起始索引
#         _file_data: 包含所有项的文件数据
#
#     Returns:
#         list[tuple]: 每项对应的(语言代码, 置信度)列表
#     """
#     # 初始化结果列表
#     results = []
#
#     # 准备有效文本的列表和对应的清理后文本
#     valid_texts = []
#     valid_indices = []
#     cleaned_texts = []
#
#     for i, item in enumerate(items):
#         # 获取原文并清理
#         source_text = item.source_text
#         if source_text is None or not source_text.strip():
#             results.append((['no_text'], -1.0, -1.0))
#             continue
#
#         cleaned_text = clean_text(source_text)
#
#         # 检查是否只包含符号
#         if is_symbols_only(cleaned_text):
#             results.append((['symbols_only'], -1.0, -1.0))
#             continue
#
#         no_symbols_text = remove_symbols(cleaned_text)
#         if not no_symbols_text:
#             results.append((['no_text'], -1.0, -1.0))
#             continue
#
#         valid_texts.append(no_symbols_text)
#         valid_indices.append(len(results))
#         cleaned_texts.append(cleaned_text)
#         results.append(None)  # 添加占位符
#
#     if valid_texts:
#         # 使用批量预测方法
#         batch_results = LanguageDetectorONNX().predict_batch(valid_texts)
#
#         if batch_results:
#             # 处理预测结果
#             for i, result in enumerate(batch_results):
#                 if result is None or i >= len(valid_indices):
#                     continue
#
#                 _, lang_code, raw_prob, top_scores = result
#                 result_idx = valid_indices[i]
#                 cleaned_text = cleaned_texts[i]
#                 onnx_langs = [top_3_score[0] for top_3_score in top_scores]
#
#                 final_prob = raw_prob
#                 if HAS_UNUSUAL_ENG_REGEX.match(cleaned_text):
#                     # 如果匹配到目标字符，则最高置信度降低0.15
#                     final_prob -= 0.15
#
#                 # 如果有至少两个识别结果，则使用最高置信度减去第二个
#                 if len(top_scores) >= 2:
#                     # 最终的置信度
#                     final_prob -= top_scores[1][1]  # 第二高分数
#
#                 results[result_idx] = (onnx_langs, final_prob, raw_prob)
#
#     # 处理未成功预测的项
#     for i in range(len(results)):
#         if results[i] is None:
#             results[i] = (['un'], -1.0, -1.0)
#
#     return results


# def detect_language_with_pycld2(items: list[CacheItem], _start_index: int, _file_data: CacheFile) -> \
#         list[tuple[list[str], float, float]]:
#     """批量检测语言（pycld2版本）
#
#     Args:
#         items: 当前处理的缓存项列表
#         _start_index: 批次中第一项在items列表中的起始索引
#         _file_data: 包含所有项的文件数据
#
#     Returns:
#         list[tuple]: 每项对应的(语言代码列表, 调整后置信度, 原始置信度)列表
#     """
#     # 初始化结果列表
#     results = []
#
#     for item in items:
#         # 获取原文并清理
#         source_text = item.source_text
#         if source_text is None or not source_text.strip():
#             results.append((['no_text'], -1.0, -1.0))
#             continue
#
#         cleaned_text = clean_text(source_text)
#
#         # 检查是否只包含符号
#         if is_symbols_only(cleaned_text):
#             results.append((['symbols_only'], -1.0, -1.0))
#             continue
#
#         try:
#             # 使用pycld2进行语言检测
#             no_symbols_text = remove_symbols(cleaned_text)
#             if not no_symbols_text:
#                 results.append((['no_text'], -1.0, -1.0))
#                 continue
#
#             is_reliable, _, details = pycld2.detect(no_symbols_text, bestEffort=True, isPlainText=True)
#
#             if not is_reliable or not details:
#                 results.append((['un'], -1.0, -1.0))
#                 continue
#
#             # 提取语言代码和置信度（使用langcode标准化）
#             language_codes = [Language.get(lang[1]).language for lang in details]
#
#             # 计算置信度 - 从percent转换为0-1范围的概率
#             probabilities = [lang[2] / 100.0 for lang in details]
#
#             raw_prob = probabilities[0] if probabilities else 0.0
#             first_prob = raw_prob
#
#             if HAS_UNUSUAL_ENG_REGEX.match(cleaned_text):
#                 # 如果匹配到目标字符，则最高置信度降低0.15
#                 first_prob -= 0.15
#
#             # 如果有至少两个识别结果，则使用最高置信度减去第二个
#             if len(probabilities) >= 2:
#                 first_prob -= probabilities[1]
#
#             results.append((language_codes, first_prob, raw_prob))
#
#         except pycld2.error as _e:
#             # 处理文本太短或无法处理的情况
#             results.append((['detection_error'], -1.0, -1.0))
#         except Exception as _e:
#             # 处理其他异常情况
#             results.append((['error'], -1.0, -1.0))
#
#     return results


# 辅助函数，用于清理文本
# 20250504改动：取消清理文本中的空白字符
def clean_text(source_text):
    # 步骤1：先将所有换行符替换为一个特殊标记
    text_with_marker = re.sub(r'\r\n|\r|\n', '__NEWLINE__', source_text)

    # 步骤2：处理一些特殊标记
    cleaned_text = CLEAN_TEXT_PATTERN.sub(' ', text_with_marker.strip())

    # 步骤3：将标记替换回一个空格
    return cleaned_text.replace('__NEWLINE__', r'\n')


# 辅助函数，用于检查文本是否只包含符号
def is_symbols_only(source_text: str):
    cleaned_text = source_text.strip()
    if not cleaned_text:  # 检查是否为空字符串
        return False
    # 检查每个字符是否都不是字母数字
    return all(not c.isalnum() for c in cleaned_text)


def remove_symbols(source_text):
    # 去除标点和特殊字符(根据需要保留部分符号)
    source_text = re.sub(r'[^\w\s「」『』，。、〜！？,.]', '', source_text)

    # 去除多余空格
    source_text = re.sub(r'\s+', ' ', source_text).strip()

    return source_text


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
