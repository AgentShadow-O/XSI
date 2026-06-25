from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone

from backend.database.models import UnifiedEvent


class CorrelationEngine:
    def __init__(self, window_seconds: int = 30, max_events: int = 500) -> None:
        self._events: deque[UnifiedEvent] = deque(maxlen=max_events)
        self._window = timedelta(seconds=window_seconds)

    def correlate(self, event: UnifiedEvent) -> UnifiedEvent:
        now = self._parse_time(event.timestamp)
        self._events.append(event)
        recent = [item for item in self._events if now - self._parse_time(item.timestamp) <= self._window]
        details = dict(event.details)
        tags = list(details.get("tags") or [])

        ip = str(details.get("ip") or details.get("remote_ip") or "")
        if ip:
            device_count = len({item.device_id for item in recent if str(item.details.get("ip") or item.details.get("remote_ip") or "") == ip})
            if device_count >= 2:
                tags.append("multi_device")
                details["device_confirmation_count"] = device_count
                event = event.model_copy(update={"risk_score": min(100, event.risk_score + 20)})

        pid = str(details.get("pid") or "")
        if pid:
            types = {item.event_type for item in recent if item.device_id == event.device_id and str(item.details.get("pid") or "") == pid}
            if {"PROCESS", "NETWORK"}.issubset(types):
                tags.append("process_network_chain")
                event = event.model_copy(update={"risk_score": min(100, event.risk_score + 15)})

        details["tags"] = list(dict.fromkeys(tags))
        return event.model_copy(update={"details": details})

    def _parse_time(self, raw: str) -> datetime:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
