import os
import time
import threading

import opencc
import rapidjson as json

from Base.Base import Base
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject

class CacheManager(Base):

    # 缓存文件保存周期（秒）
    SAVE_INTERVAL = 8

    def __init__(self) -> None:
        super().__init__()

        # 默认值
        self.project: CacheProject = CacheProject({})
        self.items: list[CacheItem] = []

        # 线程锁
        self.file_lock = threading.Lock()

        # 注册事件
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

        # 定时器
        threading.Thread(target = self.save_to_file_tick).start()

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        self.save_to_file_stop_flag = True

    # 保存缓存到文件
    def save_to_file(self) -> None:
        path = os.path.join(
            self.save_to_file_require_path, "cache", "AinieeCacheData.json"
        )
        with self.file_lock:
            with open(path, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(self.to_list(self.items), ensure_ascii=False))

    # 保存缓存到文件的定时任务
    def save_to_file_tick(self) -> None:
        while True:
            time.sleep(self.SAVE_INTERVAL)

            # 接收到退出信号则停止
            if getattr(self, "save_to_file_stop_flag", False)  == True:
                break

            # 接收到保存信号则保存
            if getattr(self, "save_to_file_require_flag", False)  == True:
                # 创建上级文件夹
                folder_path = f"{self.save_to_file_require_path}/cache"
                os.makedirs(folder_path, exist_ok = True)

                # 保存缓存到文件
                self.save_to_file()

                # 触发事件
                self.emit(Base.EVENT.CACHE_FILE_AUTO_SAVE, {})

                # 重置标志
                self.save_to_file_require_flag = False

    # 请求保存缓存到文件
    def require_save_to_file(self, output_path: str) -> None:
        self.save_to_file_require_flag = True
        self.save_to_file_require_path = output_path

    # 重置数据
    def reset(self) -> None:
        self.project: CacheProject = CacheProject({})
        self.items: list[CacheItem] = []

    # 从列表读取缓存数据
    def load_from_list(self, data: list[dict]) -> None:
        # 重置数据
        self.reset()

        try:
            self.project = CacheProject(data[0])
            self.items = [CacheItem(item) for item in data[1:]]
        except Exception as e:
            self.debug("从列表读取缓存数据失败 ...", e)

    # 从文件读取缓存数据
    def load_from_file(self, output_path: str) -> None:
        # 重置数据
        self.reset()

        # 读取文件
        path = os.path.join(output_path, "cache", "AinieeCacheData.json")
        with self.file_lock:
            if not os.path.isfile(path):
                self.debug(
                    "从文件读取缓存数据失败 ...", Exception(f"{path} 文件不存在")
                )
            else:
                try:
                    with open(path, "r", encoding="utf-8") as reader:
                        data = json.load(reader)
                        self.project = CacheProject(data[0])
                        self.items = [CacheItem(item) for item in data[1:]]
                except Exception as e:
                    self.debug("从文件读取缓存数据失败 ...", e)

    # 生成列表（兼容旧版接口）
    def to_list(self, items: list[CacheItem] = None) -> list[CacheItem]:
        results = [self.project.get_vars()]

        # 优先使用参数中的数据
        if items != None:
            results.extend([item.get_vars() for item in items])
        else:
            results.extend([item.get_vars() for item in self.items])

        return results

    # 获取缓存数据
    def get_project_data(self) -> dict:
        return self.project.get_data()

    # 设置缓存数据
    def set_project_data(self, data: dict) -> None:
        self.project.set_data(data)

    # 获取缓存数据数量
    def get_item_count(self) -> int:
        return len(self.items)

    # 获取缓存数据数量（根据翻译状态）
    def get_item_count_by_status(self, status: int) -> int:
        return len([item for item in self.items if item.get_translation_status() == status])

    # 获取缓存数据是否可以继续翻译
    def get_continue_status(self) -> bool:
        # 同时存在 已翻译 的条目与 待翻译 的条目，说明可以继续翻译
        return (
            any(v.get_translation_status() == CacheItem.STATUS.TRANSLATED for v in self.items)
            and
            any(v.get_translation_status() == CacheItem.STATUS.UNTRANSLATED for v in self.items)
        )

    # 生成上文数据条目片段
    def generate_previous_chunks(self, start_item: CacheItem, previous_line_count: int) -> list[CacheItem]:
        result = []

        try:
            # 获取当前条目在列表中的位置
            start_index = self.items.index(start_item)
        except ValueError:
            return result

        i = start_index - 1
        while len(result) < previous_line_count and i >= 0:
            item = self.items[i]

            # 上文不应跨文件
            if item.get_storage_path() != start_item.get_storage_path():
                break

            # 检查text_index是否连续递减
            expected_text_index = start_item.get_text_index() - (len(result) + 1)
            if item.get_text_index() != expected_text_index:
                break

            result.append(item)
            i -= 1  # 继续向前搜索

        # 反转列表，使顺序与原文一致
        result.reverse()
        return result

    # 开始生成缓存数据片段
    def generate_item_chunks(self, limit_type: str, limit_count: int, previous_line_count: int) -> tuple[list[list[CacheItem]], list[list[CacheItem]]]:
        chunks = []
        previous_chunks = []

        # 根据限制类型确定交叉限制参数
        if limit_type == "token":
            cross_max = 30  # 行数限制
        elif limit_type == "line":
            cross_max = 8000  # token限制
        else:
            raise ValueError("Invalid limit_type, must be 'token' or 'line'")

        chunk = []
        chunk_length = 0
        cross_length = 0  # 交叉限制累计值（行数/tokens）

        for item in [v for v in self.items if v.get_translation_status() == CacheItem.STATUS.UNTRANSLATED]:
            # 计算当前条目长度和交叉长度
            if limit_type == "token":
                current_length = item.get_token_count()
                cross_increment = 1  # 按行计数
            else:
                current_length = 1  # 按行计数
                cross_increment = item.get_token_count()

            # 判断是否结束当前chunk的条件（第一条不判断）
            if len(chunk) > 0:
                exceed_primary = (chunk_length + current_length) > limit_count
                exceed_cross = (cross_length + cross_increment) > cross_max
                path_changed = item.get_storage_path() != chunk[-1].get_storage_path()

                if exceed_primary or exceed_cross or path_changed:
                    chunks.append(chunk)
                    previous_chunks.append(self.generate_previous_chunks(chunk[0], previous_line_count))
                    # 重置累计值
                    chunk = []
                    chunk_length = 0
                    cross_length = 0

            # 添加条目到当前chunk
            chunk.append(item)
            chunk_length += current_length
            cross_length += cross_increment

        # 处理最后一个chunk
        if len(chunk) > 0:
            chunks.append(chunk)
            previous_chunks.append(self.generate_previous_chunks(chunk[0], previous_line_count))

        return chunks, previous_chunks

    # 生成缓存数据条目片段
    def generate_item_chunks_old(self, limit_type: str, limit_count: int, previous_line_count: int) -> tuple[list[list[CacheItem]], list[list[CacheItem]]]:
        chunks = []
        previous_chunks = []

        # 开始生成缓存数据片段
        chunk = []
        chunk_length = 0
        for item in [v for v in self.items if v.get_translation_status() == CacheItem.STATUS.UNTRANSLATED]:
            current_length = 1 if limit_type == "line" else item.get_token_count()
            if (
                # 首先，每个片段的第一条不判断是否超限，以避免特别长的文本导致死循环
                len(chunk) > 0
                # 然后，如果 累计长度超限 或者 数据来源跨文件，则结束此片段
                and (chunk_length + current_length > limit_count or item.get_storage_path() != chunk[-1].get_storage_path())
            ):
                chunks.append(chunk)
                previous_chunks.append(self.generate_previous_chunks(chunk[0], previous_line_count))

                chunk = []
                chunk_length = 0

            chunk.append(item)
            chunk_length = chunk_length + current_length

        # 如果还有剩余数据，则添加到列表中
        if len(chunk) > 0:
            chunks.append(chunk)
            previous_chunks.append(self.generate_previous_chunks(chunk[0], previous_line_count))

        return chunks, previous_chunks
