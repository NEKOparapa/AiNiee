import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, Thread, get_ident

import pytest

from ModuleFolders.Base.EventBus import EventBus
from ModuleFolders.Base.EventManager import EventManager


@pytest.mark.parametrize("factory", [EventBus, EventManager])
def test_worker_emission_runs_callbacks_on_the_emitting_thread(factory):
    bus = factory()
    calls = []
    payload = {"progress": 50}
    main_thread = get_ident()
    bus.subscribe(1, lambda event, data: calls.append((get_ident(), event, data)))

    with ThreadPoolExecutor(max_workers=1) as pool:
        worker_thread = pool.submit(get_ident).result(timeout=5)
        pool.submit(bus.emit, 1, payload).result(timeout=5)

    assert worker_thread != main_thread
    assert calls == [(worker_thread, 1, payload)]
    assert calls[0][2] is payload


@pytest.mark.parametrize("factory", [EventBus, EventManager])
def test_unsubscribe_does_not_deliver_future_events(factory):
    bus = factory()
    calls = []

    def handler(event, data):
        calls.append(event)

    bus.subscribe(1, handler)
    bus.subscribe(2, handler)
    bus.unsubscribe(1, handler)
    bus.unsubscribe(1, handler)
    bus.unsubscribe(3, handler)
    bus.emit(1, {})
    bus.emit(2, {})

    assert calls == [2]


@pytest.mark.parametrize("factory", [EventBus, EventManager])
def test_callback_failure_is_logged_and_does_not_stop_delivery(factory, caplog):
    bus = factory()
    calls = []

    def failing_handler(event, data):
        raise ValueError("test subscriber failure")

    bus.subscribe(1, failing_handler)
    bus.subscribe(1, lambda event, data: calls.append(event))

    with caplog.at_level(logging.ERROR):
        bus.emit(1, {})
        bus.emit(1, {})

    assert calls == [1, 1]
    assert "test subscriber failure" in caplog.text


def test_subscription_changes_during_delivery_apply_to_next_emission():
    bus = EventBus()
    entered = Event()
    release = Event()
    calls = []

    def first(event, data):
        entered.set()
        assert release.wait(timeout=5)
        calls.append("first")

    def second(event, data):
        calls.append("second")

    def third(event, data):
        calls.append("third")

    bus.subscribe(1, first)
    bus.subscribe(1, second)
    worker = Thread(target=bus.emit, args=(1, {}), daemon=True)
    worker.start()
    try:
        assert entered.wait(timeout=5)
        bus.unsubscribe(1, first)
        bus.unsubscribe(1, second)
        bus.subscribe(1, third)
    finally:
        release.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert calls == ["first", "second"]
    bus.emit(1, {})
    assert calls == ["first", "second", "third"]


def test_callback_can_unsubscribe_itself_and_emit_another_event():
    bus = EventBus()
    calls = []

    def handler(event, data):
        calls.append(event)
        bus.unsubscribe(event, handler)
        bus.emit(2, data)

    bus.subscribe(1, handler)
    bus.subscribe(2, lambda event, data: calls.append(event))
    worker = Thread(target=bus.emit, args=(1, {}), daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()

    bus.emit(1, {})
    assert calls == [1, 2]


def test_duplicate_subscriptions_are_removed_one_at_a_time():
    bus = EventBus()
    calls = []

    def handler(event, data):
        calls.append(event)

    bus.subscribe(1, handler)
    bus.subscribe(1, handler)
    bus.emit(1, {})
    bus.unsubscribe(1, handler)
    bus.emit(1, {})
    bus.unsubscribe(1, handler)
    bus.emit(1, {})
    assert calls == [1, 1, 1]


def test_concurrent_emit_and_subscription_changes_do_not_lose_stable_subscriber():
    bus = EventBus()
    calls = []
    lock = Lock()

    def stable_handler(event, data):
        with lock:
            calls.append(data["id"])

    def emit_many(worker_id):
        def temporary_handler(event, data):
            pass

        for index in range(100):
            bus.subscribe(1, temporary_handler)
            bus.emit(1, {"id": (worker_id, index)})
            bus.unsubscribe(1, temporary_handler)

    bus.subscribe(1, stable_handler)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(emit_many, worker_id) for worker_id in range(8)]
        for future in futures:
            future.result(timeout=10)

    assert sorted(calls) == [(worker_id, index) for worker_id in range(8) for index in range(100)]
    assert bus.event_callbacks == {1: [stable_handler]}


def test_subscription_snapshot_cannot_change_the_registry():
    bus = EventBus()
    calls = []
    bus.subscribe(1, lambda event, data: calls.append(event))
    snapshot = bus.event_callbacks
    snapshot[1].clear()
    snapshot.clear()
    bus.emit(1, {})
    assert calls == [1]


def test_singleton_creation_is_thread_safe(monkeypatch):
    monkeypatch.setattr(EventManager, "_singleton", None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        managers = list(pool.map(lambda _: EventManager.get_singleton(), range(100)))
    assert len({id(manager) for manager in managers}) == 1


def test_process_event_uses_the_same_subscriptions_as_emit():
    manager = EventManager()
    calls = []
    manager.subscribe(event=1, hanlder=lambda event, data: calls.append(data))
    manager.process_event(1, {"source": "process"})
    manager.emit(1, {"source": "emit"})
    assert calls == [{"source": "process"}, {"source": "emit"}]
