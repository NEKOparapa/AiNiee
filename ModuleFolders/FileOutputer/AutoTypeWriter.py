from functools import partial
from pathlib import Path
from typing import Callable, Iterable, Type

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    BaseTranslationWriter,
    OutputConfig,
    PreWriteMetadata
)


class AutoTypeWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(
        self, output_config: OutputConfig,
        writer_factories: Iterable[Callable[..., BaseTranslationWriter]],
        writer_init_params_factory: Callable[[str], OutputConfig]
    ):
        super().__init__(output_config)
        self.writer_factories = list(writer_factories)
        self.writer_init_params_factory = writer_init_params_factory
        self._writers: dict[str, BaseTranslationWriter] = {}
        self._active_writers = set()

        self._initialize_writers()

    def _initialize_writers(self):
        for writer_factory in self.writer_factories:
            writer_class = self._get_writer_class(writer_factory)
            if writer_class is AutoTypeWriter:
                continue
            writer_init_params = self.writer_init_params_factory(writer_class.get_project_type())
            writer = writer_factory(**writer_init_params)
            self._writers[writer_class.get_project_type()] = writer

    @classmethod
    def _get_writer_class(cls, writer_factory) -> Type[BaseTranslationWriter]:
        if isinstance(writer_factory, partial):
            return writer_factory.func
        elif issubclass(writer_factory, BaseTranslationWriter):
            return writer_factory
        else:
            raise ValueError(f"不支持的writer工厂`{writer_factory}`")

    def __exit__(self, exc_type, exc, exc_tb):
        errors = []
        for project_type in list(self._active_writers):
            try:
                writer = self._writers[project_type]
                writer.__exit__(exc_type, exc, exc_tb)
            except Exception as e:
                errors.append(f"释放{writer}失败: {str(e)}")
            finally:
                self._active_writers.discard(project_type)  # 确保移除
        if errors:
            raise RuntimeError("释放时发生异常:\n" + "\n".join(errors))

    def write_bilingual_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file, source_file_path, BaseTranslationWriter.TranslationMode.BILINGUAL
        )

    def write_translated_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file, source_file_path, BaseTranslationWriter.TranslationMode.TRANSLATED
        )

    def _write_translation_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        source_file_path: Path,
        translation_mode: BaseTranslationWriter.TranslationMode
    ):
        file_project_type = cache_file.file_project_type
        if file_project_type not in self._writers:
            return
        writer = self._writers[file_project_type]
        if writer.can_write(translation_mode):
            write_translation_file = getattr(writer, translation_mode.write_method)
            if file_project_type not in self._active_writers:
                writer.__enter__()
                self._active_writers.add(file_project_type)
            write_translation_file(translation_file_path, cache_file, source_file_path)

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        # 重载抽象方法，实际不需要使用
        raise NotImplementedError

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        # 重载抽象方法，实际不需要使用
        raise NotImplementedError

    @classmethod
    def get_project_type(self):
        return ProjectType.AUTO_TYPE
