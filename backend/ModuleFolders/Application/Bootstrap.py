"""组装进程内唯一一组业务组件；入口负责调用和持有其生命周期。"""

import logging
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Infrastructure.Tokener.TiktokenLoader import initialize_tiktoken

if TYPE_CHECKING:
    from ModuleFolders.Domain.FileOutputer.FileOutputer import FileOutputer
    from ModuleFolders.Domain.FileReader.FileReader import FileReader
    from ModuleFolders.Service.Cache.CacheManager import CacheManager
    from ModuleFolders.Service.SimpleExecutor.SimpleExecutor import SimpleExecutor
    from ModuleFolders.Service.TaskExecutor.TaskExecutor import TaskExecutor


@dataclass
class ApplicationRuntime:
    cache_manager: "CacheManager"
    file_reader: "FileReader"
    file_writer: "FileOutputer"
    simple_executor: "SimpleExecutor"
    task_executor: "TaskExecutor"
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """沿用已有关闭事件通知后台停止，并释放本组组件的事件订阅。

        任务取消沿用执行器原有语义；此方法不等待正在执行的请求结束。
        """
        if self._closed:
            return
        self._closed = True
        try:
            EventManager.get_singleton().emit(Base.EVENT.APP_SHUT_DOWN, {})
        finally:
            for component in (self.task_executor, self.simple_executor, self.cache_manager):
                component._cleanup_event_subscriptions()

    def __enter__(self) -> "ApplicationRuntime":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def bootstrap() -> ApplicationRuntime:
    """由进程入口调用一次，创建共享缓存、读写器和事件驱动执行器。

    保留现有配置和缓存路径规则，不读取或重写用户配置，不启动任务。
    token 缓存须在加载执行器依赖前初始化，以复用仓库内的编码资源。
    """
    try:
        initialize_tiktoken()
    except Exception:
        logging.getLogger(__name__).exception(
            "tiktoken 初始化失败，Token 限制模式将不可用，请使用行数限制模式"
        )

    from ModuleFolders.Domain.FileOutputer.FileOutputer import FileOutputer
    from ModuleFolders.Domain.FileReader.FileReader import FileReader
    from ModuleFolders.Service.Cache.CacheManager import CacheManager
    from ModuleFolders.Service.SimpleExecutor.SimpleExecutor import SimpleExecutor
    from ModuleFolders.Service.TaskExecutor.TaskExecutor import TaskExecutor

    # 构造后续组件失败时，撤销已完成组件的订阅，避免留下半初始化对象。
    with ExitStack() as rollback:
        cache_manager = CacheManager()
        rollback.callback(cache_manager._cleanup_event_subscriptions)
        file_reader = FileReader()
        file_writer = FileOutputer()
        simple_executor = SimpleExecutor()
        rollback.callback(simple_executor._cleanup_event_subscriptions)
        task_executor = TaskExecutor(cache_manager, file_reader, file_writer)
        rollback.callback(task_executor._cleanup_event_subscriptions)
        runtime = ApplicationRuntime(
            cache_manager, file_reader, file_writer, simple_executor, task_executor
        )
        rollback.pop_all()
        return runtime
