import threading
from typing import Dict, List
from ModuleFolders.Cache.CacheItem import CacheItem
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
        self.files: Dict[str, CacheFile] = {}  # 使用storage_path作为键
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        return f"CacheProject({self.project_id}, files={len(self.files)})"

    def get_vars(self) -> dict:
        """获取可序列化属性（不包含文件和锁）"""
        with self._lock:
            # 排除 files 和 _lock
            return {k: v for k, v in vars(self).items() if not k.startswith('_') and k != 'files'}

    # 添加文件
    def add_file(self, file: CacheFile) -> None:
        """线程安全添加文件"""
        with self._lock:
            self.files[file.storage_path] = file

    # 根据相对路径获取文件
    def get_file(self, storage_path: str) -> CacheFile:
        """线程安全获取文件"""
        with self._lock:
            return self.files.get(storage_path)

    # 获取全部文件
    def get_all_files(self) -> List[CacheFile]:
        """获取全部文件副本"""
        with self._lock:
            return list(self.files.values())

    # 获取项目 ID
    def get_project_id(self) -> str:
        with self._lock:
            return self.project_id

    # 设置项目 ID
    def set_project_id(self, project_id: str) -> None:
        with self._lock:
            self.project_id = project_id

    # 获取项目类型
    def get_project_type(self) -> str:
        with self._lock:
            return self.project_type

    # 设置项目类型
    def set_project_type(self, project_type: str) -> None:
        with self._lock:
            self.project_type = project_type

