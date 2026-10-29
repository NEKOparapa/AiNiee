"""Thread-safe event delivery without an application or UI event loop."""

import logging
from collections.abc import Callable
from threading import Lock


EventHandler = Callable[[int, dict], None]


class EventBus:
    """Run subscribers synchronously on the thread that calls ``emit``.

    Subscribers are copied before delivery, so callbacks can subscribe,
    unsubscribe, or emit recursively without holding the registry lock. Changes
    to subscriptions take effect on the next emission; an in-flight snapshot
    still runs in subscription order. Concurrent emitters may run the same
    callback concurrently, so subscribers must protect their own shared state.
    """

    def __init__(self) -> None:
        self._callbacks: dict[int, list[EventHandler]] = {}
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)

    def emit(self, event: int, data: dict) -> None:
        with self._lock:
            callbacks = tuple(self._callbacks.get(event, ()))

        for handler in callbacks:
            try:
                handler(event, data)
            except Exception:
                self._logger.exception("Event subscriber failed (event=%s)", event)

    def subscribe(self, event: int, hanlder: EventHandler) -> None:
        with self._lock:
            self._callbacks.setdefault(event, []).append(hanlder)

    def unsubscribe(self, event: int, hanlder: EventHandler) -> None:
        with self._lock:
            callbacks = self._callbacks.get(event)
            if callbacks is None:
                return
            try:
                callbacks.remove(hanlder)
            except ValueError:
                return
            if not callbacks:
                del self._callbacks[event]

    @property
    def event_callbacks(self) -> dict[int, list[EventHandler]]:
        """Return a detached snapshot for existing subscription inspection."""
        with self._lock:
            return {event: list(callbacks) for event, callbacks in self._callbacks.items()}
