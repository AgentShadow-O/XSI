from __future__ import annotations

import asyncio
import hashlib
import hmac
import platform
import random
import socket
from datetime import datetime, timezone
from typing import Any

import httpx
import psutil

from backend.core.config import AGENT_TOKEN
from backend.database.models import UnifiedEvent
from backend.sensors.edr.heartbeat import stable_device_id


class EndpointAgent:
    def __init__(self, controller_url: str, device_id: str | None = None, token: str = AGENT_TOKEN) -> None:
        self.controller_url = controller_url.rstrip("/")
        self.device_id = device_id or stable_device_id()
        self.token = token
        self.agent_version = "0.4.0"

    def _signed_headers(self, body: bytes) -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).isoformat()
        message = timestamp.encode("utf-8") + body
        signature = hmac.new(self.token.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Agent-Signature": signature,
            "X-Agent-Timestamp": timestamp,
            "X-Device-Id": self.device_id,
            "Content-Type": "application/json",
        }

    def _registration_payload(self) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = hmac.new(
            self.token.encode("utf-8"),
            f"{self.device_id}{timestamp}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        hostname = socket.gethostname()
        return {
            "device_id": self.device_id,
            "device_name": hostname,
            "device_type": "desktop",
            "os": platform.system(),
            "version": self.agent_version,
            "agent_version": self.agent_version,
            "hostname": hostname,
            "platform": platform.platform(),
            "token": self.token,
            "timestamp": timestamp,
            "signature": signature,
        }

    async def register(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{self.controller_url}/api/agents/register", json=self._registration_payload())
            response.raise_for_status()

    async def send_event(self, event: UnifiedEvent) -> None:
        payload = event.model_dump()
        payload["token"] = self.token
        async with httpx.AsyncClient(timeout=5.0) as client:
            body = json_dumps_bytes(payload)
            response = await client.post(
                f"{self.controller_url}/api/agents/event",
                content=body,
                headers=self._signed_headers(body),
            )
            response.raise_for_status()

    async def telemetry_once(self) -> dict[str, Any]:
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "memory": psutil.virtual_memory().percent,
            "process_count": len(psutil.pids()),
            "boot_time": psutil.boot_time(),
        }

    async def poll_command(self) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self.controller_url}/api/agents/{self.device_id}/commands",
                params={"token": self.token},
            )
            response.raise_for_status()
            return response.json().get("command")

    async def run(self, interval: float = 15.0) -> None:
        while True:
            try:
                await self.register()
                break
            except httpx.HTTPError:
                await asyncio.sleep(10.0)
        while True:
            metrics = await self.telemetry_once()
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "device_id": self.device_id,
                    "status": "alive",
                    "token": self.token,
                    "health": metrics,
                    "agent_version": self.agent_version,
                    "metrics": metrics,
                }
                body = json_dumps_bytes(payload)
                response = await client.post(
                    f"{self.controller_url}/api/agents/heartbeat",
                    content=body,
                    headers=self._signed_headers(body),
                )
                if response.status_code == 401:
                    await self.register()
                else:
                    response.raise_for_status()
            await self.poll_command()
            await asyncio.sleep(max(10.0, min(30.0, interval + random.uniform(-2.0, 2.0))))


def json_dumps_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, separators=(",", ":")).encode("utf-8")
