from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn, TimeRemainingColumn

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.FileReader.ReaderUtil import detect_file_encoding, detect_language_with_mediapipe


@dataclass
class InputConfig:
    input_root: Path


@dataclass
class PreReadMetadata:
    encoding: str = "utf-8"


class ReaderInitParams(TypedDict):
    """reader的初始化参数，必须包含input_config，其他参数随意"""
    input_config: InputConfig


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

    # 读取原文文件的处理流程（改进点：非自动检测语言情况下不使用检测器）
    def read_source_file(self, file_path: Path) -> CacheFile:
        """读取文件内容，并检测各种信息"""
        # 模板流程
        pre_read_metadata = self.pre_read_source(file_path)  # 读取文件之前的操作，可以放文件编码方法或其他
        file_data = self.on_read_source(file_path, pre_read_metadata)  # 读取单个文件中所有原文文本，由各个reader实现不同的专属的方法
        if not file_data or not file_data.items: #判断文件为空
            return None          
        file_data.encoding = pre_read_metadata.encoding  # 设置文件编码
        file_data.storage_path = file_path  # 临时设置一个路径
        post_file_data = self.post_read_source(file_data)  # 读取文件之后的操作，可以是语言检测等

        return post_file_data

    # 读取文件之前的操作
    def pre_read_source(self, file_path: Path) -> PreReadMetadata:
        """读取文件之前的操作，可以是检测文件编码等"""

        # 限定文件类型，只检测txt，srt，vtt，lrc等文件编码，检测大型文件编码会很慢，例如epub，trans
        if file_path.suffix in [".txt", ".srt", ".vtt", ".lrc"]:
            # 检测文件编码
            metadata = PreReadMetadata(encoding=detect_file_encoding(file_path))
        else:
            # 固定编码
            metadata = PreReadMetadata(encoding="utf-8")

        return metadata

    # 读取文件原文，由各个reader实现方法
    @abstractmethod
    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        """接收pre_read_source的结果，读取文件内容，并返回原文(译文)片段"""
        pass

    # 读取文件之后的操作
    def post_read_source(self, file_data: CacheFile) -> CacheFile:
        """对原文(译文)片段做统一处理，使用批处理方式"""
        batch_size = 128
        items = file_data.items
        total_items = len(items)
        _num_batches = (total_items + batch_size - 1) // batch_size

        # 保存需要使用cld2再次检查的文本
        # items_for_cld2 = []
        # 使用Rich显示双层进度条
        with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                "•",
                TimeRemainingColumn(),
                expand=True
        ) as progress:

            # 总体进度
            main_task = progress.add_task(
                f"MediaPipe语言检测中...\n目标文件 -> {file_data.file_name}\n",
                total=total_items
            )

            # 批次进度
            # batch_task = progress.add_task(
            #     "批次进度",
            #     total=num_batches
            # )

            processed_items = 0

            for batch_idx, batch_start in enumerate(range(0, total_items, batch_size)):
                batch_end = min(batch_start + batch_size, total_items)
                batch_items = items[batch_start:batch_end]
                # end_index = min(batch_start + batch_size, total_items)

                # 更新批次描述
                # progress.update(
                #     batch_task,
                #     description=f"批次 {batch_idx + 1}/{num_batches} - 项目: {batch_start + 1}-{end_index}",
                #     advance=0
                # )

                # 批量检测语言
                batch_results = detect_language_with_mediapipe(batch_items, batch_start, file_data)
                # batch_results = detect_language_with_onnx(batch_items, batch_start, file_data)
                # batch_results = detect_language_with_pycld2(batch_items, batch_start, file_data)

                # 将检测结果保存回对应的item
                for i, (mp_langs, mp_score, _) in enumerate(batch_results):
                    cur_item = items[batch_start + i]

                    # 初始化使用mediapipe结果（如果有效）
                    if mp_score > 0.0:
                        # 创建除了主要语言外的其他语言列表
                        other_langs = mp_langs[1:] if len(mp_langs) > 1 else []

                        cur_item.lang_code = (mp_langs[0], mp_score, other_langs)
                    else:
                        # 低于0分的直接标记为排除翻译
                        cur_item.translation_status = TranslationStatus.EXCLUDED

                    processed_items += 1

                    # 更新主进度
                    progress.update(main_task, completed=processed_items)

                # 完成一个批次
                # progress.update(batch_task, advance=1)

        return file_data

    # 验证文件是否由该reader读取
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
