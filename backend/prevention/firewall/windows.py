from __future__ import annotations

import subprocess


class WindowsFirewall:
    def block_ip(self, ip: str) -> tuple[bool, str]:
        rule = f"XSI_BLOCK_{ip.replace(':', '_').replace('.', '_')}"
        cmd = [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={rule}",
            "dir=out",
            "action=block",
            f"remoteip={ip}",
            "enable=yes",
        ]
        return self._run(cmd)

    def block_port(self, port: int) -> tuple[bool, str]:
        if port <= 0 or port > 65535:
            return False, "invalid_port"
        cmd = [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name=XSI_BLOCK_PORT_{port}",
            "dir=out",
            "action=block",
            "protocol=TCP",
            f"remoteport={port}",
            "enable=yes",
        ]
        return self._run(cmd)

    def unblock_ip(self, ip: str) -> tuple[bool, str]:
        rule = f"XSI_BLOCK_{ip.replace(':', '_').replace('.', '_')}"
        cmd = [
            "netsh",
            "advfirewall",
            "firewall",
            "delete",
            "rule",
            f"name={rule}",
        ]
        return self._run(cmd)

    def block_host(self, hostname: str) -> tuple[bool, str]:
        hosts_path = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        try:
            with open(hosts_path, "a") as f:
                f.write(f"\n{'.'.join(['127', '0', '0', '1'])} {hostname}\n")
            return True, f"Blocked {hostname} via hosts file"
        except Exception as exc:
            return False, str(exc)

    def _run(self, cmd: list[str]) -> tuple[bool, str]:
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=8)
            return completed.returncode == 0, completed.stderr.strip() or completed.stdout.strip()
        except Exception as exc:
            return False, str(exc)
