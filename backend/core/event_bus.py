from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator


class EventBus:
    def __init__(self, maxsize: int = 1000) -> None:
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._maxsize = maxsize

    async def publish(self, event: dict) -> None:
        for subscriber in tuple(self._subscribers):
            if subscriber.full():
                try:
                    subscriber.get_nowait()
                    subscriber.task_done()
                except asyncio.QueueEmpty:
                    pass
            await subscriber.put(event)

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                queue.task_done()
                yield event
        finally:
            self._subscribers.discard(queue)
