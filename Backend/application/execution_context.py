"""Per-call cancellation and progress hooks, independent of desktop events."""
from dataclasses import dataclass, field
from threading import Event
from typing import Callable


@dataclass
class ExecutionContext:
    source: str = "api"
    cancel_event: Event = field(default_factory=Event)
    on_batch_complete: Callable | None = None
    on_progress: Callable | None = None
    on_model_prepared: Callable | None = None
    on_result: Callable | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

