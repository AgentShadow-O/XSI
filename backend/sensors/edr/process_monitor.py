from __future__ import annotations

import psutil

from backend.database.models import UnifiedEvent


def snapshot_processes(device_id: str) -> list[UnifiedEvent]:
    events: list[UnifiedEvent] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            info = proc.info
        except (psutil.Error, OSError):
            continue
        events.append(
            UnifiedEvent(
                device_id=device_id,
                source="edr",
                event_type="PROCESS",
                severity="safe",
                risk_score=0,
                details={
                    "pid": info.get("pid") or 0,
                    "process_name": info.get("name") or "",
                    "command_line": " ".join(info.get("cmdline") or []),
                },
            )
        )
    return events
