import threading

import tiktoken

class Status():

    UNTRANSLATED = 0        # 待翻译
    TRANSLATED = 1          # 已翻译
    TRANSLATING = 2         # 翻译中（弃用）
    EXCLUED = 7             # 已排除

class CacheItem():

    STATUS = Status()
    TYPE_FILTER = (int, str, bool, float, list, dict, tuple)

    def __init__(self, args: dict) -> None:
        super().__init__()

        # 默认值
        self.row_index: int = 0
        self.text_index: int = 0
        self.translation_status: int = 0
        self.model: str = ""
        self.source_text: str = ""
        self.translated_text: str = ""
        self.file_name: str = ""
        self.storage_path: str = ""

        # 初始化
        for k, v in args.items():
            setattr(self, k, v)

        # 线程锁
        self.lock = threading.Lock()

        # 类变量
        CacheItem.cache = {} if not hasattr(CacheItem, "cache") else CacheItem.cache

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self.get_vars()})"
        )

    def get_vars(self) -> dict:
        return {
            k:v
            for k, v in vars(self).items()
            if isinstance(v, CacheItem.TYPE_FILTER)
        }

    # 获取行号
    def get_row_index(self) -> int:
        with self.lock:
            return self.row_index

    # 设置行号
    def set_row_index(self, row_index: int) -> None:
        with self.lock:
            self.row_index = row_index

    # 获取文本序号
    def get_text_index(self) -> int:
        with self.lock:
            return self.text_index

    # 设置文本序号
    def set_text_index(self, text_index: int) -> None:
        with self.lock:
            self.text_index = text_index

    # 获取翻译状态
    def get_translation_status(self) -> int:
        with self.lock:
            return self.translation_status

    # 设置翻译状态
    def set_translation_status(self, translation_status: int) -> None:
        with self.lock:
            self.translation_status = translation_status

    # 获取翻译模型
    def get_model(self) -> str:
        with self.lock:
            return self.model

    # 设置翻译模型
    def set_model(self, model: str) -> None:
        with self.lock:
            self.model = model

    # 获取原文
    def get_source_text(self) -> str:
        with self.lock:
            return self.source_text

    # 设置原文
    def set_source_text(self, source_text: str) -> None:
        with self.lock:
            self.source_text = source_text

    # 获取译文
    def get_translated_text(self) -> str:
        with self.lock:
            return self.translated_text

    # 设置译文
    def set_translated_text(self, translated_text: str) -> None:
        with self.lock:
            # 有时候模型的回复反序列化以后会是 int 等非字符类型，所以这里要强制转换成字符串
            # TODO:可能需要更好的处理方式
            if isinstance(translated_text, (int, float)):
                self.translated_text = str(translated_text)
            else:
                self.translated_text = translated_text

    # 获取文件名
    def get_file_name(self) -> str:
        with self.lock:
            return self.file_name

    # 设置文件名
    def set_file_name(self, file_name: str) -> None:
        with self.lock:
            self.file_name = file_name

    # 获取文件路径
    def get_storage_path(self) -> str:
        with self.lock:
            return self.storage_path

    # 设置文件路径
    def set_storage_path(self, storage_path: str) -> None:
        with self.lock:
            self.storage_path = storage_path

    # 获取 Token 数量
    def get_token_count(self) -> int:
        with self.lock:
            if self.source_text not in CacheItem.cache:
                CacheItem.cache[self.source_text] = len(tiktoken.get_encoding("cl100k_base").encode(self.source_text))

            return CacheItem.cache[self.source_text]