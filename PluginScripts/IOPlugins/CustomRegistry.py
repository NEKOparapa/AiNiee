from typing import TYPE_CHECKING, Any, Self

from ModuleFolders.FileOutputer.BaseWriter import BaseTranslationWriter
from ModuleFolders.FileReader.BaseReader import BaseSourceReader

if TYPE_CHECKING:
    from ModuleFolders.FileOutputer.FileOutputer import FileOutputer
    from ModuleFolders.FileReader.FileReader import FileReader


class CustomWriter(BaseTranslationWriter):
    """插件式Writer，继承后可自动注册"""
    _writers: list[Self] = []

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # import 发生在 PluginManager 中
        CustomWriter._writers.append(cls)

    @classmethod
    def register_writers(cls, register: "FileOutputer"):
        for writer in CustomWriter._writers:
            register.register_writer(writer, **writer.get_default_init_args())

    @classmethod
    def get_default_init_args(cls) -> dict[str, Any]:
        return {}


class CustomReader(BaseSourceReader):
    """插件式Reader，继承后可自动注册"""
    _readers: list[Self] = []

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # import 发生在 PluginManager 中
        CustomReader._readers.append(cls)

    @classmethod
    def register_readers(cls, register: "FileReader"):
        for reader in CustomReader._readers:
            register.register_reader(reader, **reader.get_default_init_args())

    @classmethod
    def get_default_init_args(cls) -> dict[str, Any]:
        return {}
