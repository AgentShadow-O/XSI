from __future__ import annotations

from pathlib import Path

from backend.database.models import UnifiedEvent


def file_event(device_id: str, path: str | Path, event_type: str = "FILE") -> UnifiedEvent:
    return UnifiedEvent(
        device_id=device_id,
        source="edr",
        event_type=event_type,
        severity="warning",
        risk_score=50,
        details={"file_path": str(path)},
    )
