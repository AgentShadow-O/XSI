from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.auth import websocket_authorized
from backend.core.engine import XSIEngine


def websocket_router(engine: XSIEngine) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def ws_events(websocket: WebSocket) -> None:
        if not websocket_authorized(websocket):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            async for event in engine.event_bus.subscribe():
                await websocket.send_json(event)
        except WebSocketDisconnect:
            return

    return router
