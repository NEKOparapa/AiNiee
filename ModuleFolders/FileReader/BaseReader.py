import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Union

import chardet

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.ReaderDetection import (
    decode_content_bytes,
    detect_file_encoding,
    detect_newlines
)


@dataclass
class InputConfig:
    input_root: Path


class ReaderInitParams(TypedDict):
    """reader的初始化参数，必须包含input_config，其他参数随意"""
    input_config: InputConfig


@dataclass
class PreReadMetadata:
    encoding: str = "utf-8"


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

    def read_source_file(self, file_path: Path) -> CacheFile:
        """读取文件内容，并返回原文(译文)片段"""
        # 模板方法
        pre_read_metadata = self.pre_read_source(file_path)
        file_data = self.on_read_source(file_path, pre_read_metadata)
        file_data.encoding = pre_read_metadata.encoding
        return self.post_read_source(file_data)

    def pre_read_source(self, file_path: Path) -> PreReadMetadata:
        """读取文件之前的操作，可以是检测文件编码"""
        # 猜测的文件编码
        return PreReadMetadata()

    @abstractmethod
    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        """接收pre_read_source的结果，读取文件内容，并返回原文(译文)片段"""
        pass

    def post_read_source(self, file_data: CacheFile) -> CacheFile:
        """对原文(译文)片段做统一处理"""
        return file_data

    def can_read(self, file_path: Path, fast=True) -> bool:
        """验证文件兼容性，返回False则不会读取该文件"""
        if fast:
            return self.can_read_by_extension(file_path)
        try:
            return self.can_read_by_content(file_path)
        except Exception:
            return False

    @classmethod
    def is_environ_supported(cls) -> bool:
        """用于判断当前环境是否支持该reader"""
        return True

    def can_read_by_extension(self, file_path: Path):
        """根据文件后缀判断是否可读"""
        return file_path.suffix.replace('.', '', 1) == self.support_file

    def can_read_by_content(self, file_path: Path) -> bool:
        """根据文件内容判断是否可读"""
        # 默认实现用后缀判断
        return self.can_read_by_extension(file_path)

    def get_file_project_type(self, file_path: Path) -> str:
        """根据文件判断项目类型，无法判断时返回None"""
        return self.get_project_type()

    @property
    def exclude_rules(self) -> list[str]:
        """用于排除缓存文件/目录"""
        return []


# UNUSED: 暂时不使用之前这个读取文件的函数
def _read_file_safely(file_path: Union[str, pathlib.Path], cache_project: CacheProject) -> str:
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
