from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

from backend.agents.communication import create_command_queue
from backend.agents.registration import new_device_id, token_hash
from backend.core.config import DATABASE_URL, HEARTBEAT_TIMEOUT_SECONDS, PROJECT_ROOT, REDIS_URL, ensure_runtime_dirs
from backend.core.event_bus import EventBus
from backend.database.models import UnifiedEvent
from backend.database.postgres_storage import PostgresStorage
from backend.database.storage import SiemStorage, backup_legacy_databases
from backend.detection.correlation import CorrelationEngine
from backend.detection.risk_engine import RiskEngine
from backend.detection.rule_engine import RuleEngine
from backend.prevention.ips.blocker import PreventionEngine


logger = logging.getLogger("xsi.engine")


class XSIEngine:
    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.storage = PostgresStorage(DATABASE_URL) if DATABASE_URL.startswith(("postgres://", "postgresql://")) else SiemStorage()
        self.rules = RuleEngine()
        self.correlation = CorrelationEngine()
        self.risk = RiskEngine()
        self.prevention = PreventionEngine()
        self.commands = create_command_queue(REDIS_URL)
        self.running = False
        self._heartbeat_task = None

    async def start(self) -> None:
        ensure_runtime_dirs()
        await self.storage.initialize()
        self.running = True
        import asyncio

        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor_loop(), name="heartbeat-monitor")
        
        self._integrity_hashes = self._capture_integrity_hashes()
        asyncio.create_task(self._integrity_monitor_loop(), name="integrity-monitor")

    async def _integrity_monitor_loop(self) -> None:
        import asyncio
        while self.running:
            await asyncio.sleep(300)  # Check every 5 minutes
            current = self._capture_integrity_hashes()
            for path, h in current.items():
                if h != self._integrity_hashes.get(path):
                    await self.ingest({
                        "event_type": "TAMPER_DETECTED",
                        "severity": "critical",
                        "source": "self-protection",
                        "details": {"path": path, "reason": "file_modified"}
                    })
                    self._integrity_hashes[path] = h

    def _capture_integrity_hashes(self) -> dict[str, str]:
        import hashlib
        hashes = {}
        paths = [
            PROJECT_ROOT / "backend" / "main.py",
            PROJECT_ROOT / "config.yaml",
            PROJECT_ROOT / "backend" / "core" / "engine.py",
        ]
        for path in paths:
            if path.exists():
                try:
                    hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
                except Exception:
                    continue
        return hashes

    async def stop(self) -> None:
        self.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except BaseException:
                pass
            self._heartbeat_task = None

    async def ingest(self, raw_event: dict[str, Any] | UnifiedEvent) -> UnifiedEvent:
        event = raw_event if isinstance(raw_event, UnifiedEvent) else UnifiedEvent.from_raw(raw_event)
        event = self.rules.apply(event)
        event = self.correlation.correlate(event)
        event = self.risk.score(event)
        actions = self.prevention.recommended_actions(event)
        details = dict(event.details)
        details["recommended_actions"] = actions
        event = event.model_copy(update={"details": details})
        event_id = await self.storage.store_event(event)
        logger.info("event=event_stored module=engine device_id=%s source=%s event_type=%s risk_score=%s", event.device_id, event.source, event.event_type, event.risk_score)
        payload = event.model_dump()
        payload["id"] = event_id
        await self.event_bus.publish(payload)
        if event.risk_score >= 50:
            await self.event_bus.publish({"type": "NEW_ALERT", "event": payload})
        for action in actions:
            result = self.prevention.execute(str(action["action"]), str(action["target"]))
            if result.get("isolate"):
                await self.storage.heartbeat(event.device_id, "isolated")
                await self.event_bus.publish({"type": "DEVICE_STATUS", "device_id": event.device_id, "status": "isolated"})
            await self.storage.log_action(event.device_id, str(action["action"]), str(action["target"]), str(result["status"]), result)
            await self.event_bus.publish({"type": "ACTION", **result})
        return event

    async def register_device(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        os_name: str,
        version: str,
        hostname: str,
        platform: str,
        token: str,
        metadata: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        certificate_fingerprint: str = "",
    ) -> dict[str, Any]:
        resolved_id = device_id or new_device_id(device_name or hostname or platform)
        result = await self.storage.register_device(
            resolved_id,
            device_name or hostname or resolved_id,
            device_type,
            os_name,
            version,
            hostname,
            platform,
            token_hash(token),
            metadata or {},
            profile or {},
            certificate_fingerprint,
        )
        await self._publish_device_status_if_changed(result)
        return result

    async def heartbeat(self, device_id: str, status: str, health: dict[str, Any] | None = None, agent_version: str = "") -> dict[str, Any]:
        logger.info("event=agent_heartbeat module=engine device_id=%s status=%s", device_id, status)
        result = await self.storage.heartbeat(device_id, status, health or {}, agent_version)
        await self._publish_device_status_if_changed(result)
        return result

    async def remove_device(self, device_id: str) -> dict[str, Any]:
        logger.warning("event=device_removed module=engine device_id=%s", device_id)
        await self.storage.remove_device(device_id)
        payload = {"type": "DEVICE_STATUS", "device_id": device_id, "status": "removed"}
        await self.event_bus.publish(payload)
        return {"status": "removed", "device_id": device_id}

    async def ingest_processes(self, device_id: str, processes: list[dict[str, Any]]) -> None:
        logger.info("event=process_telemetry module=engine device_id=%s count=%s", device_id, len(processes))
        await self.storage.store_processes(device_id, processes)
        await self.event_bus.publish({"type": "PROCESS_UPDATE", "device_id": device_id, "count": len(processes)})

    async def ingest_network(self, device_id: str, activity: list[dict[str, Any]]) -> None:
        logger.info("event=network_telemetry module=engine device_id=%s count=%s", device_id, len(activity))
        await self.storage.store_network_activity(device_id, activity)
        await self.event_bus.publish({"type": "NETWORK_UPDATE", "device_id": device_id, "count": len(activity)})

    async def queue_command(self, device_id: str, command: dict[str, Any]) -> None:
        await self.commands.push(device_id, command)

    async def next_command(self, device_id: str) -> dict[str, Any] | None:
        return await self.commands.pop(device_id, timeout=0.1)

    async def manual_action(self, device_id: str, action: str, target: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.prevention.execute(action, target)
        result.update(details or {})
        return await self.storage.log_action(device_id, action, target, str(result.get("status") or "unknown"), result)

    async def backup_legacy(self, source_root: Path, backup_dir: Path) -> list[Path]:
        return backup_legacy_databases(source_root, backup_dir)

    async def migrate_legacy(self, source_root: Path) -> int:
        return await self.storage.migrate_legacy_databases(source_root)

    async def _heartbeat_monitor_loop(self) -> None:
        import asyncio

        while self.running:
            for change in await self.storage.mark_offline_stale(HEARTBEAT_TIMEOUT_SECONDS):
                await self.event_bus.publish({"type": "DEVICE_STATUS", **change})
            await asyncio.sleep(10)

    async def _publish_device_status_if_changed(self, result: dict[str, Any]) -> None:
        if result.get("previous_status") != result.get("status"):
            await self.event_bus.publish({"type": "DEVICE_STATUS", **result})
