from collections import Counter, defaultdict
from functools import lru_cache, partial
from pathlib import Path
from typing import Callable, Iterable, Type

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    ReaderInitParams
)


class AutoTypeReader(BaseSourceReader):
    def __init__(
        self, input_config: InputConfig,
        reader_factories: Iterable[Callable[..., BaseSourceReader]],
        reader_init_params_factory: Callable[[str], ReaderInitParams]
    ):
        super().__init__(input_config)
        self.reader_factories = list(reader_factories)
        self.reader_init_params_factory = reader_init_params_factory
        self._readers: dict[str, BaseSourceReader] = {}
        self._active_readers = set()

        self._initialize_readers()

        # 在这里重载是为了避免lru_cache内存泄漏
        self.get_file_project_type = lru_cache(maxsize=1)(self.__get_file_project_type)

    @classmethod
    def get_infer_method_id(cls, reader_class: Type[BaseSourceReader]):
        # 这里未实例化所以用support_file的字节码判断
        # 重载以下任意方法都能避免歧义，但推荐重载support_file和can_read_by_content
        return (
            id(reader_class.can_read),
            reader_class.support_file.fget.__code__.co_code,
            # 常量字符串不包含在co_code中，这里增加常量的判断
            reader_class.support_file.fget.__code__.co_consts,
            id(reader_class.can_read_by_extension),
            id(reader_class.can_read_by_content),
        )

    @classmethod
    def verify_reader_factories(cls, reader_factories: Iterable[Callable[..., BaseSourceReader]]):
        """检验对于同一种后缀的文件的reader是否存在歧义"""
        # 根据
        infer_method_cnts = Counter(
            cls.get_infer_method_id(cls._get_reader_class(reader_factory))
            for reader_factory in reader_factories
        )
        ambiguous_readers = defaultdict(list)
        for reader_factory in reader_factories:
            reader_class = cls._get_reader_class(reader_factory)
            infer_method_id = cls.get_infer_method_id(reader_class)

            if infer_method_cnts[infer_method_id] > 1:
                ambiguous_readers[infer_method_id].append(reader_class)

        if ambiguous_readers:
            ambiguous_readers_msg = '\n'.join(str(reader_class_list) for reader_class_list in ambiguous_readers.values())
            raise ValueError(f"以下reader在识别文件方面存在歧义，请检查是否重载support_file或can_read_by_content方法：\n{ambiguous_readers_msg}")

    @classmethod
    def _get_reader_class(cls, reader_factory) -> Type[BaseSourceReader]:
        if isinstance(reader_factory, partial):
            return reader_factory.func
        elif issubclass(reader_factory, BaseSourceReader):
            return reader_factory
        else:
            raise ValueError(f"不支持的reader工厂`{reader_factory}`")

    def _initialize_readers(self):
        for reader_factory in self.reader_factories:
            reader_class = self._get_reader_class(reader_factory)
            if reader_class is AutoTypeReader:
                continue
            reader_init_params = self.reader_init_params_factory(reader_class.get_project_type())
            reader = reader_factory(**reader_init_params)
            self._readers[reader_class.get_project_type()] = reader
        self._support_files = set(reader.support_file for reader in self._readers.values())

    def __exit__(self, exc_type, exc, exc_tb):
        errors = []
        for project_type in list(self._active_readers):
            try:
                reader = self._readers[project_type]
                reader.__exit__(exc_type, exc, exc_tb)
            except Exception as e:
                errors.append(f"释放{reader}失败: {str(e)}")
            finally:
                self._active_readers.discard(project_type)  # 确保移除
        if errors:
            raise RuntimeError("释放时发生异常:\n" + "\n".join(errors))

    @classmethod
    def get_project_type(cls):
        return 'AutoType'

    @property
    def support_file(self):
        return '*'

    def _get_extension(self, file_path: Path):
        return file_path.suffix.lstrip(".")

    def can_read_by_extension(self, file_path: Path) -> bool:
        return self._get_extension(file_path) in self._support_files

    def can_read_by_content(self, file_path: Path) -> bool:
        return self.get_file_project_type(file_path) is not None

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        project_type = self.get_file_project_type(file_path)
        if not project_type or project_type not in self._readers:
            return []
        reader = self._readers[project_type]
        if reader not in self._active_readers:
            reader.__enter__()  # 实际使用时才申请资源
            self._active_readers.add(reader.get_project_type())
        return reader.read_source_file(file_path, detected_encoding)

    def __get_file_project_type(self, file_path: Path):
        extension = self._get_extension(file_path)
        # reader数量较少，不增加support_file为key的字典，减少代码复杂度
        for reader in self._readers.values():
            if reader.support_file == extension and reader.can_read(file_path, fast=False):
                return reader.get_file_project_type(file_path)
        return None

    @property
    def exclude_rules(self) -> list[str]:
        rules = []
        for reader in self._readers.values():
            rules.extend(reader.exclude_rules)
        return rules
