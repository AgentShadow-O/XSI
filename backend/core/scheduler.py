from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class Scheduler:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def every(self, seconds: float, callback: Callable[[], Awaitable[None]], name: str) -> None:
        async def _loop() -> None:
            while True:
                await callback()
                await asyncio.sleep(seconds)

        self._tasks.add(asyncio.create_task(_loop(), name=name))

    async def shutdown(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()
        for task in tuple(self._tasks):
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
