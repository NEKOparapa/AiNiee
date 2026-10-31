"""Thread-safe events independent of Qt; desktop dispatch is injected at startup."""
import threading

class EventManager:

    # 单一实例
    _singleton = None

    _singleton_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        self.event_callbacks = {}
        self._lock = threading.RLock()
        self._dispatcher = None
        self._command_sender = None

    # 获取单例
    @classmethod
    def get_singleton(cls):
        with cls._singleton_lock:
            if cls._singleton is None:
                cls._singleton = cls()
            return cls._singleton

    def configure(self, dispatcher=None, command_sender=None):
        self._dispatcher = dispatcher
        self._command_sender = command_sender

    def deliver(self, event: int, data: dict):
        """Deliver a received event without forwarding it back to the server."""
        if self._dispatcher is None:
            self.process_event(event, data)
        else:
            self._dispatcher(event, data)

    # 处理事件
    def process_event(self, event: int, data: dict):
        with self._lock:
            callbacks = tuple(self.event_callbacks.get(event, ()))
        if callbacks:
            for hanlder in callbacks:
                try:
                    hanlder(event, data)
                except RuntimeError as error:
                    if self._is_deleted_qobject_error(error):
                        self.unsubscribe(event, hanlder)
                        continue
                    raise

    # 触发事件
    def emit(self, event: int, data: dict):
        if self._command_sender is not None and self._command_sender(event, data):
            return
        self.deliver(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable):
        with self._lock:
            self.event_callbacks.setdefault(event, []).append(hanlder)

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable):
        with self._lock:
            callbacks = self.event_callbacks.get(event, [])
            if hanlder in callbacks:
                callbacks.remove(hanlder)
            if not callbacks:
                self.event_callbacks.pop(event, None)

    @staticmethod
    def _is_deleted_qobject_error(error: RuntimeError) -> bool:
        message = str(error)
        return "wrapped C/C++ object" in message and "has been deleted" in message
