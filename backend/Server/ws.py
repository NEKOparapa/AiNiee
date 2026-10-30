"""Authenticated WebSocket delivery and per-client disconnect handling."""

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from Server.deps import require_websocket_token


router = APIRouter()


@router.websocket("/ws")
async def websocket_events(websocket: WebSocket) -> None:
    await require_websocket_token(websocket)
    bridge = websocket.app.state.event_bridge
    queue = bridge.subscribe()
    tasks: set[asyncio.Task] = set()
    try:
        await websocket.accept()

        async def send_messages() -> None:
            while True:
                message = await queue.get()
                if message is None:
                    await websocket.close(code=1013, reason="Reconnect and refresh current state")
                    return
                await websocket.send_json(message.model_dump(mode="json", exclude_unset=True))

        async def receive_disconnect() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return

        tasks = {asyncio.create_task(send_messages()), asyncio.create_task(receive_disconnect())}
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (WebSocketDisconnect, OSError):
        pass
    finally:
        bridge.unsubscribe(queue)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError, WebSocketDisconnect, OSError, RuntimeError):
                await task
