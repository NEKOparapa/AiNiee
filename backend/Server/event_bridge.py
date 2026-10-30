"""Deliver worker-thread events and logs to WebSocket subscribers."""

import asyncio
import json
import logging
import time
from collections.abc import Callable

from pydantic import ValidationError

from ModuleFolders.Base.Base import Event
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Log.LogSystem import redact
from Server.schemas.events import (
    EventMessage,
    LogBatch,
    LogEntry,
    LogMessage,
    TaskProgress,
    TaskUpdateMessage,
    WsMessage,
)


# Keep the backend-event -> wire-name convention in this one module.
EVENT_TYPES = {
    value: name.lower().replace("_", ".")
    for name, value in vars(Event).items()
    if name.isupper() and isinstance(value, int)
}

_logger = logging.getLogger(__name__)


def _redact_event_values(value):
    """Run on the emitting worker while its credential scope is still active."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_event_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_event_values(item) for key, item in value.items()}
    return value


class _BridgeLogHandler(logging.Handler):
    def __init__(self, bridge: "EventBridge") -> None:
        super().__init__(level=logging.INFO)
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        # Diagnostics must not feed back into their own event transport.
        if record.name == __name__ or record.name.startswith(__name__ + "."):
            return
        try:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            self.bridge._post(
                self.bridge._accept_log,
                LogEntry(
                    ts=record.created,
                    level=record.levelname,
                    logger=record.name,
                    message=redact(message),
                ),
            )
        except Exception:
            # A malformed log record must never interrupt business work.
            return


class EventBridge:
    """All subscriber queues and batching state belong to the supplied loop.

    Worker callbacks snapshot payloads before scheduling, so mutations after
    emit cannot change messages waiting in the asyncio event loop. Slow clients
    receive a None sentinel and reconnect to fetch the authoritative state.
    """

    BATCH_INTERVAL = 0.1

    def __init__(
        self,
        manager: EventManager,
        loop: asyncio.AbstractEventLoop,
        *,
        queue_size: int = 256,
    ) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self.manager = manager
        self.loop = loop
        self.queue_size = queue_size
        self._started = False
        self._closed = False
        self._seq = 0
        self._subscribers: set[asyncio.Queue[WsMessage | None]] = set()
        self._pending_task: tuple[float, dict] | None = None
        self._pending_logs: list[LogEntry] = []
        self._task_timer: asyncio.TimerHandle | None = None
        self._log_timer: asyncio.TimerHandle | None = None
        self._log_handler = _BridgeLogHandler(self)

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("EventBridge is closed")
        if self._started:
            return
        self._started = True
        for event in EVENT_TYPES:
            self.manager.subscribe(event, self._on_event)
        logging.getLogger().addHandler(self._log_handler)

    def subscribe(self) -> asyncio.Queue[WsMessage | None]:
        if not self._started or self._closed:
            raise RuntimeError("EventBridge is not running")
        queue: asyncio.Queue[WsMessage | None] = asyncio.Queue(self.queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[WsMessage | None]) -> None:
        self._subscribers.discard(queue)

    def _post(self, callback: Callable, *args) -> None:
        if not self._started or self._closed:
            return
        try:
            self.loop.call_soon_threadsafe(callback, *args)
        except RuntimeError:
            # The loop can close between checking state and posting a callback.
            return

    def _on_event(self, event: int, data: dict) -> None:
        if self._closed:
            return
        try:
            # A JSON roundtrip both detaches mutable containers and normalizes
            # legacy integer item-index keys into wire-compatible string keys.
            snapshot = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
            if not isinstance(snapshot, dict):
                raise TypeError("Event payload must be an object")
            snapshot = _redact_event_values(snapshot)
        except (TypeError, ValueError, RecursionError):
            _logger.warning("Ignoring non-JSON event payload (event=%s)", event)
            return
        self._post(self._accept_event, event, snapshot, time.time())

    def _accept_event(self, event: int, data: dict, timestamp: float) -> None:
        if self._closed:
            return
        if event == Event.TASK_UPDATE:
            self._pending_task = (timestamp, data)
            if self._task_timer is None:
                self._task_timer = self.loop.call_later(self.BATCH_INTERVAL, self._flush_task)
            return
        if event in (Event.TASK_STATE_CHANGED, Event.TASK_COMPLETED, Event.TASK_STOP_DONE, Event.PROJECT_CHANGED):
            # A buffered update belongs to the previous lifecycle/project. Send
            # it first so it cannot overwrite a newer REST snapshot afterwards.
            self._flush_task()
        self._broadcast(EventMessage(seq=self._next_seq(), type=EVENT_TYPES[event], ts=timestamp, data=data))

    def _accept_log(self, entry: LogEntry) -> None:
        if self._closed:
            return
        self._pending_logs.append(entry)
        if self._log_timer is None:
            self._log_timer = self.loop.call_later(self.BATCH_INTERVAL, self._flush_logs)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _flush_task(self) -> None:
        if self._task_timer is not None:
            self._task_timer.cancel()
        self._task_timer = None
        pending, self._pending_task = self._pending_task, None
        if self._closed or pending is None:
            return
        timestamp, data = pending
        try:
            progress = TaskProgress.model_validate(data)
        except ValidationError:
            _logger.warning("Ignoring invalid task progress payload")
            return
        self._broadcast(TaskUpdateMessage(seq=self._next_seq(), type="task.update", ts=timestamp, data=progress))

    def _flush_logs(self) -> None:
        self._log_timer = None
        entries, self._pending_logs = self._pending_logs, []
        if self._closed or not entries:
            return
        self._broadcast(LogMessage(seq=self._next_seq(), type="log", ts=time.time(), data=LogBatch(entries=entries)))

    def _disconnect(self, queue: asyncio.Queue[WsMessage | None]) -> None:
        self.unsubscribe(queue)
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(None)

    def _broadcast(self, message: WsMessage) -> None:
        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                self._disconnect(queue)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for event in EVENT_TYPES:
            self.manager.unsubscribe(event, self._on_event)
        logging.getLogger().removeHandler(self._log_handler)
        self._log_handler.close()
        for timer in (self._task_timer, self._log_timer):
            if timer is not None:
                timer.cancel()
        self._task_timer = self._log_timer = None
        self._pending_task = None
        self._pending_logs.clear()
        for queue in tuple(self._subscribers):
            self._disconnect(queue)
