import threading

class CacheProject():

    def __init__(self, args: dict) -> None:
        super().__init__()

        # 默认值
        self.project_id: str = ""
        self.project_type: str = ""
        self.data: dict = {}
        # 新增值，用于保存文件编码与换行符类型
        self.file_encoding: str = ""  # 默认为空表示无特定reader编码需求
        self.line_ending: str = ""  # 默认为空表示无特定reader编码需求
        # 用于保存文件实际项目类型，用于插件的判断
        self.file_project_types = []

        # 初始化
        for k, v in args.items():
            setattr(self, k, v)

        # 线程锁
        self.lock = threading.Lock()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self.get_vars()})"
        )

    def get_vars(self) -> dict:
        return {
            k:v
            for k, v in vars(self).items()
            if isinstance(v, (int, str, bool, float, list, dict, tuple))
        }

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

    # 获取文件实际项目类型
    def get_file_project_types(self) -> frozenset:
        with self.lock:
            return self.file_project_types

    # 设置文件实际项目类型
    def set_file_project_types(self, file_project_types: frozenset) -> None:
        with self.lock:
            self.file_project_types = file_project_types
