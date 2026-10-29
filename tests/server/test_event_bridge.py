import asyncio
import logging
import time
from threading import Thread

from ModuleFolders.Base.Base import Event
from ModuleFolders.Base.EventManager import EventManager
from Server.event_bridge import EVENT_TYPES, EventBridge
from Server.schemas.events import WS_MESSAGE_ADAPTER, WebSocketMessage


def test_worker_events_arrive_within_200ms_and_snapshot_the_payload():
    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop())
        bridge.start()
        queue = bridge.subscribe()
        try:
            payload = {"nested": {"line": 1}, "updated_items": {1: "translated"}}

            def worker():
                manager.emit(Event.TABLE_UPDATE, payload)
                payload["nested"]["line"] = 999

            started = time.monotonic()
            thread = Thread(target=worker)
            thread.start()
            message = await asyncio.wait_for(queue.get(), timeout=0.2)
            assert time.monotonic() - started < 0.2
            thread.join(timeout=1)
            assert not thread.is_alive()
            assert message.type == "table.update"
            assert message.seq == 1
            assert message.data == {"nested": {"line": 1}, "updated_items": {"1": "translated"}}
            assert WS_MESSAGE_ADAPTER.validate_json(message.model_dump_json()).seq == 1
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_task_updates_are_coalesced_for_100ms_and_latest_progress_is_delivered():
    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop())
        bridge.start()
        queue = bridge.subscribe()
        try:
            def worker():
                for line in range(20):
                    manager.emit(Event.TASK_UPDATE, {"line": line})

            started = time.monotonic()
            thread = Thread(target=worker)
            thread.start()
            await asyncio.sleep(0.04)
            assert queue.empty()
            message = await asyncio.wait_for(queue.get(), timeout=0.15)
            elapsed = time.monotonic() - started
            thread.join(timeout=1)
            assert 0.09 <= elapsed < 0.2
            assert message.type == "task.update"
            assert message.data.line == 19
            await asyncio.sleep(0.11)
            assert queue.empty()
            manager.emit(Event.TASK_COMPLETED, {})
            completed = await asyncio.wait_for(queue.get(), timeout=0.1)
            assert completed.seq == message.seq + 1
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_logs_are_batched_and_secrets_are_redacted(caplog):
    async def scenario():
        bridge = EventBridge(EventManager(), asyncio.get_running_loop())
        bridge.start()
        queue = bridge.subscribe()
        logger = logging.getLogger("AiNiee.test.ws")
        try:
            logger.info("api_key=do-not-broadcast-this-secret")
            logger.warning("Second log entry")
            await asyncio.sleep(0.04)
            assert queue.empty()
            message = await asyncio.wait_for(queue.get(), timeout=0.15)
            assert message.type == "log"
            assert len(message.data.entries) == 2
            assert "do-not-broadcast-this-secret" not in message.model_dump_json()
            assert "REDACTED" in message.data.entries[0].message
            assert message.data.entries[1].level == "WARNING"
        finally:
            await bridge.close()

    with caplog.at_level(logging.INFO):
        asyncio.run(scenario())


def test_slow_clients_disconnect_without_blocking_other_clients():
    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop(), queue_size=1)
        bridge.start()
        slow = bridge.subscribe()
        fast = bridge.subscribe()
        try:
            manager.emit(Event.TASK_START, {})
            first = await asyncio.wait_for(fast.get(), timeout=0.1)
            manager.emit(Event.TASK_COMPLETED, {})
            second = await asyncio.wait_for(fast.get(), timeout=0.1)
            assert second.seq == first.seq + 1
            assert await slow.get() is None
            manager.emit(Event.TASK_STOP_DONE, {})
            assert (await asyncio.wait_for(fast.get(), timeout=0.1)).type == "task.stop.done"
            assert slow.empty()
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_closing_unsubscribes_and_cancels_pending_batches():
    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop())
        bridge.start()
        bridge.start()
        queue = bridge.subscribe()
        manager.emit(Event.TASK_UPDATE, {"line": 5})
        await asyncio.sleep(0)
        await bridge.close()
        await bridge.close()
        assert manager.event_callbacks == {}
        assert await queue.get() is None
        await asyncio.sleep(0.11)
        assert queue.empty()
        manager.emit(Event.TASK_COMPLETED, {})
        assert queue.empty()

    asyncio.run(scenario())


def test_non_json_events_do_not_break_following_delivery():
    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop())
        bridge.start()
        queue = bridge.subscribe()
        try:
            manager.emit(Event.TABLE_UPDATE, {"item": object()})
            manager.emit(Event.TASK_COMPLETED, {})
            message = await asyncio.wait_for(queue.get(), timeout=0.1)
            assert message.type == "task.completed"
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_event_mapping_and_exported_websocket_schema_are_complete():
    assert EVENT_TYPES[Event.TASK_UPDATE] == "task.update"
    assert EVENT_TYPES[Event.APP_UPDATE_CHECK_DONE] == "app.update.check.done"
    assert len(EVENT_TYPES) == len({value for name, value in vars(Event).items() if name.isupper()})
    schema = WebSocketMessage.model_json_schema(ref_template="#/components/schemas/{model}")
    assert schema["title"] == "WebSocketMessage"
    assert {"TaskUpdateMessage", "LogMessage", "EventMessage"} <= schema["$defs"].keys()


def test_analysis_event_values_are_redacted_before_leaving_worker_scope():
    from ModuleFolders.Log.LogSystem import redact, sensitive_values

    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop())
        bridge.start()
        queue = bridge.subscribe()
        try:
            def worker():
                with sensitive_values(["private-provider-value"]):
                    manager.emit(Event.ANALYSIS_TASK_DONE, {
                        "status": "error", "message": "request failed private-provider-value",
                        "nested": [{"name": "private-provider-value", "number": 3, "empty": None}],
                    })

            thread = Thread(target=worker)
            thread.start()
            thread.join(1)  # The secret scope ends before the asyncio callback.
            assert not thread.is_alive()
            message = await asyncio.wait_for(queue.get(), timeout=0.1)
            assert "private-provider-value" not in message.model_dump_json()
            assert message.data["nested"][0]["number"] == 3
            assert message.data["nested"][0]["empty"] is None
            assert redact("private-provider-value") == "private-provider-value"
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_progress_is_flushed_before_lifecycle_and_project_change():
    async def scenario():
        manager = EventManager()
        bridge = EventBridge(manager, asyncio.get_running_loop())
        bridge.start()
        queue = bridge.subscribe()
        try:
            manager.emit(Event.TASK_UPDATE, {"line": 7})
            manager.emit(Event.TASK_STATE_CHANGED, {})
            manager.emit(Event.PROJECT_CHANGED, {"project_id": "new-project"})
            messages = [await asyncio.wait_for(queue.get(), timeout=0.1) for _ in range(3)]
            assert [message.type for message in messages] == ["task.update", "task.state.changed", "project.changed"]
            assert [message.seq for message in messages] == [1, 2, 3]
            assert messages[0].data.line == 7
            # Flushing cancels the original timer instead of allowing it to
            # prematurely flush the new project's next 100 ms batch.
            await asyncio.sleep(0.05)
            manager.emit(Event.TASK_UPDATE, {"line": 1})
            await asyncio.sleep(0.07)
            assert queue.empty()
            message = await asyncio.wait_for(queue.get(), timeout=0.1)
            assert message.data.line == 1
        finally:
            await bridge.close()

    asyncio.run(scenario())
