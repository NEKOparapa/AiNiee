"""The shared event manager used by existing backend services."""

from threading import Lock

from ModuleFolders.Base.EventBus import EventBus, EventHandler


class EventManager:
    _singleton = None
    _singleton_lock = Lock()

    def __init__(self) -> None:
        self._bus = EventBus()

    @staticmethod
    def get_singleton() -> "EventManager":
        with EventManager._singleton_lock:
            if EventManager._singleton is None:
                EventManager._singleton = EventManager()
            return EventManager._singleton

    def process_event(self, event: int, data: dict) -> None:
        self._bus.emit(event, data)

    def emit(self, event: int, data: dict) -> None:
        self._bus.emit(event, data)

    def subscribe(self, event: int, hanlder: EventHandler) -> None:
        self._bus.subscribe(event, hanlder)

    def unsubscribe(self, event: int, hanlder: EventHandler) -> None:
        self._bus.unsubscribe(event, hanlder)

    @property
    def event_callbacks(self) -> dict[int, list[EventHandler]]:
        return self._bus.event_callbacks
