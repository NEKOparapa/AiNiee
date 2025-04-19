import threading
from typing import Dict, List
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.Cache.CacheFile import CacheFile

class CacheProject:
    """项目级缓存容器"""
    def __init__(self, project_args: dict):
        # 项目元数据
        self.project_id: str = ""
        self.project_type: str = ""
        
        # 初始化项目属性
        for k, v in project_args.items():
            setattr(self, k, v)
        
        # 文件存储
        self._files: Dict[str, CacheFile] = {}  # 使用storage_path作为键
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        return f"CacheProject({self.project_id}, files={len(self._files)})"

    def add_file(self, file: CacheFile) -> None:
        """线程安全添加文件"""
        with self._lock:
            self._files[file.storage_path] = file

    def get_file(self, storage_path: str) -> CacheFile:
        """线程安全获取文件"""
        with self._lock:
            return self._files.get(storage_path)

    def get_all_files(self) -> List[CacheFile]:
        """获取全部文件副本"""
        with self._lock:
            return list(self._files.values())

    # 获取项目 ID
    def get_project_id(self) -> str:
        with self.lock:
            return self.project_id

    # 设置项目 ID
    def set_project_id(self, project_id: str) -> None:
        with self.lock:
            self.project_id = project_id

    # 获取项目类型
    def get_project_type(self) -> str:
        with self.lock:
            return self.project_type

    # 设置项目类型
    def set_project_type(self, project_type: str) -> None:
        with self.lock:
            self.project_type = project_type

    # 获取翻译状态
    def get_translation_status(self) -> int:
        with self.lock:
            return self.translation_status

    # 设置翻译状态
    def set_translation_status(self, translation_status: int) -> None:
        with self.lock:
            self.translation_status = translation_status

    # 获取数据
    def get_data(self) -> dict:
        with self.lock:
            return self.data

    # 设置数据
    def set_data(self, data: dict) -> None:
        with self.lock:
            self.data = data

    # 获取文件编码
    def get_file_encoding(self) -> str:
        with self.lock:
            return self.file_encoding

    # 设置文件编码
    def set_file_encoding(self, encoding: str) -> None:
        with self.lock:
            self.file_encoding = encoding

    # 获取换行符类型
    def get_line_ending(self) -> str:
        with self.lock:
            return self.line_ending

    # 设置换行符类型
    def set_line_ending(self, line_ending: str) -> None:
        with self.lock:
            self.line_ending = line_ending

