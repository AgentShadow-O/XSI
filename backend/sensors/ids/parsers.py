from __future__ import annotations

from typing import Any

from backend.database.models import UnifiedEvent


def ids_alert_to_event(alert: dict[str, Any]) -> UnifiedEvent:
    return UnifiedEvent.from_raw(
        {
            "device_id": alert.get("device_id") or "controller",
            "source": "ids",
            "event_type": alert.get("event_type") or alert.get("reason") or "IDS_ALERT",
            "severity": alert.get("severity") or "warning",
            "risk_score": alert.get("risk_score") or alert.get("confidence") or 50,
            "details": alert,
        }
    )
