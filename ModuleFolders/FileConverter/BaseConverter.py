from abc import ABC, abstractmethod
from pathlib import Path


class BaseFileConverter(ABC):
    def __enter__(self):
        """申请整个converter生命周期用到的耗时资源，单个文件的资源则在convert_file方法中申请释放"""
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """释放耗时资源"""
        pass

    @abstractmethod
    def can_convert(self, output_file_path: Path) -> bool:
        pass

    @abstractmethod
    def convert_file(self, input_file_path: Path, output_file_path: Path):
        """把文件从 input_file_path 转换成 output_file_path"""
        pass
