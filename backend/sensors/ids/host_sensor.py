from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.database.models import UnifiedEvent


class HostSensor:
    def file_modified_event(self, path: str | Path, device_id: str = "controller") -> UnifiedEvent:
        file_path = str(path)
        return UnifiedEvent(
            device_id=device_id,
            source="ids",
            event_type="FILE_MODIFIED",
            severity="warning",
            risk_score=50,
            details={"file_path": file_path, "message": "File modified"},
        )

    def start(self, watch_path: Path, publish: Callable[[UnifiedEvent], None]) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            return

        sensor = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):  # type: ignore[no-untyped-def]
                if not event.is_directory:
                    publish(sensor.file_modified_event(event.src_path))

        observer = Observer()
        observer.schedule(Handler(), str(watch_path), recursive=True)
        observer.start()
