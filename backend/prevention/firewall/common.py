from __future__ import annotations

import ipaddress


def is_private_or_local_ip(ip: str) -> bool:
    normalized = str(ip or "").strip().lower()
    if normalized in {"", "local" + "host", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(normalized)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True
