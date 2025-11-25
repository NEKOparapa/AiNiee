from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileAccessor.BabeldocPdfAccessor import BabeldocPdfAccessor
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class BabeldocPdfReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, tmp_directory='babeldoc_cache'):
        super().__init__(input_config)
        self.tmp_directory = tmp_directory
        
        # 获取输入路径
        root_path = input_config.input_root
        # 如果输入路径是文件（例如用户直接选择了 .pdf 文件），则使用该文件所在的文件夹作为缓存根目录
        if root_path.is_file():
            root_path = root_path.parent
            
        abs_tmp_directory = root_path / self.tmp_directory

        self.file_accessor = BabeldocPdfAccessor(abs_tmp_directory, None)

    @classmethod
    def get_project_type(self):
        return ProjectType.BABELDOC_PDF

    @property
    def support_file(self):
        return 'pdf'

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        source_texts = self.file_accessor.read_content(file_path)
        return CacheFile(items=[
            CacheItem(source_text=line) for line in source_texts
        ])

    @property
    def exclude_rules(self):
        return [f"{self.tmp_directory}/*"]