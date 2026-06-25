from __future__ import annotations

import platform

from backend.prevention.firewall.linux import LinuxFirewall
from backend.prevention.firewall.windows import WindowsFirewall


class FirewallManager:
    def __init__(self) -> None:
        if platform.system().lower().startswith("win"):
            self._impl = WindowsFirewall()
        else:
            self._impl = LinuxFirewall()

    def block_ip(self, ip: str) -> tuple[bool, str]:
        return self._impl.block_ip(ip)

    def unblock_ip(self, ip: str) -> tuple[bool, str]:
        return self._impl.unblock_ip(ip)

    def block_port(self, port: int) -> tuple[bool, str]:
        return self._impl.block_port(port)

    def block_host(self, hostname: str) -> tuple[bool, str]:
        return self._impl.block_host(hostname)
