import os
import time
import threading
import rapidjson as json
from typing import List, Tuple

from Base.Base import Base
from ModuleFolders.Cache.CacheItem import CacheItem, Status
from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import CacheProject

class CacheManager(Base):
    SAVE_INTERVAL = 8  # 缓存保存间隔（秒）

    def __init__(self) -> None:
        super().__init__()

        # 默认值
        self.project: CacheProject = CacheProject({})

        # 线程锁
        self.file_lock = threading.Lock()

        # 注册事件
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

        # 定时器
        threading.Thread(target=self.save_to_file_tick, daemon=True).start()

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        self.save_to_file_stop_flag = True

    # 保存缓存到文件
    def save_to_file(self) -> None:
        """保存缓存到文件"""
        path = os.path.join(self.save_to_file_require_path, "cache", "AinieeCacheData.json")
        with self.file_lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(self._serialize_data(), ensure_ascii=False))

    def _serialize_data(self) -> list:
        """生成序列化数据：包含Project、Files及其Items"""
        data = [self.project.get_vars()]
        for file in self.project.get_all_files():
            data.append(file.get_vars())
            data.extend([item.get_vars() for item in file.get_all_items()])
        return data

    # 保存缓存到文件的定时任务
    def save_to_file_tick(self) -> None:
        """定时保存任务"""
        while not self.save_to_file_stop_flag:
            time.sleep(self.SAVE_INTERVAL)
            if getattr(self, "save_to_file_require_flag", False):
                self.save_to_file()
                self.emit(Base.EVENT.CACHE_FILE_AUTO_SAVE, {})
                self.save_to_file_require_flag = False

    # 请求保存缓存到文件
    def require_save_to_file(self, output_path: str) -> None:
        """请求保存缓存"""
        self.save_to_file_require_path = output_path
        self.save_to_file_require_flag = True

    # 重置数据
    def reset(self) -> None:
        """重置数据"""
        self.project = CacheProject({})

    # 从列表读取缓存数据
    def load_from_list(self, data: list) -> None:
        """从列表加载数据"""
        self.reset()
        if not data:
            return
        try:
            self.project = CacheProject(data[0])
            current_file = None
            for entry in data[1:]:
                if "file_encoding" in entry or "line_ending" in entry:  # 识别为CacheFile
                    current_file = CacheFile(entry)
                    self.project.add_file(current_file)
                else:  # 识别为CacheItem
                    if not current_file or current_file.storage_path != entry.get("storage_path"):
                        self._create_file_from_item(entry)
                        current_file = self.project.get_file(entry["storage_path"])
                    current_file.add_item(CacheItem(entry))
        except Exception as e:
            self.debug("加载列表数据失败", e)

    def _create_file_from_item(self, item_data: dict) -> None:
        """根据Item数据创建CacheFile"""
        storage_path = item_data.get("storage_path")
        if not storage_path or self.project.get_file(storage_path):
            return
        file_args = {
            "file_name": item_data.get("file_name", ""),
            "storage_path": storage_path,
            "file_encoding": item_data.get("file_encoding", "utf-8"),
            "line_ending": item_data.get("line_ending", "\n")
        }
        self.project.add_file(CacheFile(file_args))

    # 从元组中读取缓存数据
    def load_from_tuple(self, data: tuple[CacheProject, list[CacheItem]]):
        self.reset()
        try:
            self.project = data[0] # 项目头信息
            self.items = data[1] # 文本对信息
        except Exception as e:
            self.debug("从元组读取缓存数据失败 ...", e)

    # 从缓存文件读取数据
    def load_from_file(self, output_path: str) -> None:
        """从文件加载数据"""
        path = os.path.join(output_path, "cache", "AinieeCacheData.json")
        with self.file_lock:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as reader:
                    self.load_from_list(json.load(reader))

    # 获取缓存内全部文本对数量
    def get_item_count(self) -> int:
        """获取总缓存项数量"""
        return sum(len(file.get_all_items()) for file in self.project.get_all_files())

    # 获取某翻译状态的条目数量
    def get_item_count_by_status(self, status: int) -> int:
        """按状态统计缓存项"""
        count = 0
        for file in self.project.get_all_files():
            count += sum(1 for item in file.get_all_items() if item.get_translation_status() == status)
        return count

    # 检测是否存在需要翻译的条目
    def get_continue_status(self) -> bool:
        """检查是否存在可继续翻译的状态"""
        has_translated = False
        has_untranslated = False
        for file in self.project.get_all_files():
            for item in file.get_all_items():
                status = item.get_translation_status()
                if status == Status.TRANSLATED:
                    has_translated = True
                elif status == Status.UNTRANSLATED:
                    has_untranslated = True
                if has_translated and has_untranslated:
                    return True
        return has_translated and has_untranslated

    # 生成上文数据条目片段
    def generate_previous_chunks(self, start_item: CacheItem, previous_line_count: int) -> List[CacheItem]:
        """生成上文片段"""
        file = self.project.get_file(start_item.get_storage_path())
        if not file:
            return []
        items = sorted(file.get_all_items(), key=lambda x: x.get_text_index())
        try:
            start_idx = next(i for i, item in enumerate(items) if item.text_index == start_item.text_index)
        except StopIteration:
            return []
        collected = []
        i = start_idx - 1
        while i >= 0 and len(collected) < previous_line_count:
            if items[i].text_index == start_item.text_index - len(collected) - 1:
                collected.append(items[i])
                i -= 1
            else:
                break
        return list(reversed(collected))

    # 生成待翻译片段
    def generate_item_chunks(self, limit_type: str, limit_count: int, previous_line_count: int) -> Tuple[List[List[CacheItem]], List[List[CacheItem]]]:
        
        chunks, previous_chunks = [], []
        for file in self.project.get_all_files():
            items = sorted(
                [item for item in file.get_all_items() if item.translation_status == Status.UNTRANSLATED],
                key=lambda x: x.text_index
            )
            if not items:
                continue
            current_chunk, current_length = [], 0
            for item in items:
                item_length = item.get_token_count() if limit_type == "token" else 1
                if current_chunk and (current_length + item_length > limit_count):
                    self._commit_chunk(current_chunk, previous_line_count, chunks, previous_chunks)
                    current_chunk, current_length = [], 0
                current_chunk.append(item)
                current_length += item_length
            if current_chunk:
                self._commit_chunk(current_chunk, previous_line_count, chunks, previous_chunks)
        return chunks, previous_chunks

    # 提交当前片段
    def _commit_chunk(self, chunk: List[CacheItem], previous_count: int,chunks: List[List[CacheItem]], previous_chunks: List[List[CacheItem]]) -> None:
        """提交当前片段"""
        chunks.append(chunk)
        previous_chunks.append(self.generate_previous_chunks(chunk[0], previous_count))