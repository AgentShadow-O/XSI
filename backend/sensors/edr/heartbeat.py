from __future__ import annotations

import hashlib
import platform
import socket
from datetime import datetime, timezone


def heartbeat_payload(device_id: str, token: str, status: str = "alive") -> dict:
    return {
        "device_id": device_id,
        "token": token,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def stable_device_id() -> str:
    seed = "|".join([socket.gethostname(), platform.system(), platform.machine()])
    return "xsi-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
