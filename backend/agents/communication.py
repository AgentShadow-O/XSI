from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


class CommandQueue:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = defaultdict(asyncio.Queue)

    async def push(self, device_id: str, command: dict[str, Any]) -> None:
        await self._queues[device_id].put(command)

    async def pop(self, device_id: str, timeout: float = 0.1) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._queues[device_id].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class RedisCommandQueue:
    def __init__(self, redis_url: str, prefix: str = "xsi:commands") -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix

    async def push(self, device_id: str, command: dict[str, Any]) -> None:
        await self._redis.lpush(self._key(device_id), json.dumps(command, ensure_ascii=True))

    async def pop(self, device_id: str, timeout: float = 0.1) -> dict[str, Any] | None:
        deadline = asyncio.get_running_loop().time() + max(0.0, timeout)
        while True:
            raw = await self._redis.rpop(self._key(device_id))
            if raw:
                payload = json.loads(raw)
                return payload if isinstance(payload, dict) else {"value": payload}
            if asyncio.get_running_loop().time() >= deadline:
                return None
            await asyncio.sleep(min(0.05, max(0.0, deadline - asyncio.get_running_loop().time())))

    def _key(self, device_id: str) -> str:
        return f"{self._prefix}:{device_id}"


def create_command_queue(redis_url: str = "") -> CommandQueue | RedisCommandQueue:
    if redis_url:
        return RedisCommandQueue(redis_url)
    return CommandQueue()
