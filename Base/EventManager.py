from PyQt5.Qt import Qt
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

class EventManager(QObject):

    # 单一实例
    _singleton = None

    # 自定义信号
    # 字典类型或者其他复杂对象应该使用 object 作为信号参数类型，这样可以传递任意 Python 对象，包括 dict
    signal = pyqtSignal(int, object)

    # 事件列表
    event_callbacks = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signal.connect(self.process_event, Qt.QueuedConnection)

    # 获取单例
    def get_singleton():
        if EventManager._singleton == None:
            EventManager._singleton = EventManager()

        return EventManager._singleton

    # 处理事件
    def process_event(self, event: int, data: dict):
        if event in self.event_callbacks:
            for hanlder in self.event_callbacks[event]:
                hanlder(event, data)

    # 触发事件
    def emit(self, event: int, data: dict):
        self.signal.emit(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable):
        if event not in self.event_callbacks:
            self.event_callbacks[event] = []
        self.event_callbacks[event].append(hanlder)

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable):
        if event in self.event_callbacks:
            self.event_callbacks[event].remove(hanlder)
