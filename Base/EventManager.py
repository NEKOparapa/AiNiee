from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

class EventManager(QObject):

    # 单一实例
    _instance = None

    # 自定义信号
    # 字典类型或者其他复杂对象应该使用 object 作为信号参数类型，这样可以传递任意 Python 对象，包括 dict
    signal = pyqtSignal(int, object)

    # 事件列表
    event_clllbacks = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signal.connect(self.process_event)

    def __new__(cls, *args, **kwargs):
        if cls._instance == None:
            cls._instance = super(EventManager, cls).__new__(cls, *args, **kwargs)

        return cls._instance

    # 处理事件
    def process_event(self, event: int, data: dict):
        if event in self.event_clllbacks:
            for hanlder in self.event_clllbacks[event]:
                hanlder(event, data)
    # 触发事件
    def emit(self, event: int, data: dict):
        self.signal.emit(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable):
        if event not in self.event_clllbacks:
            self.event_clllbacks[event] = []
        self.event_clllbacks[event].append(hanlder)

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable):
        if event in self.event_clllbacks:
            self.event_clllbacks[event].remove(hanlder)
