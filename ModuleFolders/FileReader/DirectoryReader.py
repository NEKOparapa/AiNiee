from pathlib import Path
from typing import Callable

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import BaseSourceReader


class DirectoryReader:
    def __init__(self, create_reader: Callable[[], BaseSourceReader]):
        self.create_reader = create_reader

    def read_source_directory(self, source_directory: Path) -> tuple[CacheProject, list[CacheItem]]:
        cache_project = CacheProject({})
        text_index = 1
        items = []
        with self.create_reader() as reader:
            cache_project.set_project_type(reader.get_project_type())
            for root, _, files in source_directory.walk():
                for file in files:
                    file_path = root / file
                    if reader.can_read(file_path):
                        for item in reader.read_source_file(file_path):
                            item.set_text_index(text_index)
                            item.set_model('none')
                            item.set_storage_path(str(file_path.relative_to(source_directory)))
                            item.set_file_name(file_path.name)
                            items.append(item)
                            text_index += 1
        return (cache_project, items)
