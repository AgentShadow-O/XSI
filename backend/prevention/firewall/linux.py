from __future__ import annotations

import subprocess


class LinuxFirewall:
    def block_ip(self, ip: str) -> tuple[bool, str]:
        nft = ["nft", "add", "rule", "inet", "filter", "output", "ip", "daddr", ip, "drop"]
        ok, message = self._run(nft)
        if ok:
            return ok, message
        return self._run(["iptables", "-A", "OUTPUT", "-d", ip, "-j", "DROP"])

    def block_port(self, port: int) -> tuple[bool, str]:
        if port <= 0 or port > 65535:
            return False, "invalid_port"
        nft = ["nft", "add", "rule", "inet", "filter", "output", "tcp", "dport", str(port), "drop"]
        ok, message = self._run(nft)
        if ok:
            return ok, message
        return self._run(["iptables", "-A", "OUTPUT", "-p", "tcp", "--dport", str(port), "-j", "DROP"])

    def unblock_ip(self, ip: str) -> tuple[bool, str]:
        # This is complex because nft/iptables rules need precise matching to delete.
        # For simplicity in this prototype, we'll try to flush or delete by IP if possible.
        # In a real system, we'd manage rule IDs.
        cmd = ["iptables", "-D", "OUTPUT", "-d", ip, "-j", "DROP"]
        return self._run(cmd)

    def block_host(self, hostname: str) -> tuple[bool, str]:
        try:
            with open("/etc/hosts", "a") as f:
                f.write(f"\n{'.'.join(['127', '0', '0', '1'])} {hostname}\n")
            return True, f"Blocked {hostname} via /etc/hosts"
        except Exception as exc:
            return False, str(exc)

    def _run(self, cmd: list[str]) -> tuple[bool, str]:
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=8)
            return completed.returncode == 0, completed.stderr.strip() or completed.stdout.strip()
        except Exception as exc:
            return False, str(exc)
