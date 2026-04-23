from __future__ import annotations
import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        try:
            self._connections.remove(ws)
        except ValueError:
            pass

    async def broadcast(self, message: dict) -> None:
        if not self._connections:
            return
        data = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    app = websocket.app
    mms = app.state.mms_server
    log_buf = app.state.log_buffer

    await ws_manager.connect(websocket)
    log_queue = log_buf.subscribe()

    try:
        # Send immediate status snapshot
        await websocket.send_json({
            "type": "server_status",
            "data": mms.get_status(),
        })

        async def forward_logs() -> None:
            while True:
                try:
                    entry = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                    await websocket.send_json({
                        "type": "log_entry",
                        "data": entry.model_dump(),
                    })
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    return

        log_task = asyncio.create_task(forward_logs())

        # Keep alive: read ping messages from client
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send keepalive ping to client
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break
            except Exception:
                break

    finally:
        log_task.cancel()
        log_buf.unsubscribe(log_queue)
        ws_manager.disconnect(websocket)
