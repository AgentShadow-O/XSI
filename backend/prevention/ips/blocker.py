from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import psutil

from backend.core.config import BLOCK_PRIVATE_IPS, MIN_PREVENTION_SCORE, QUARANTINE_DIR, SAFE_MODE
from backend.database.models import UnifiedEvent
from backend.prevention.firewall.common import is_private_or_local_ip
from backend.prevention.firewall.manager import FirewallManager


PROTECTED_PROCESSES = {
    "system",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "winlogon.exe",
    "explorer.exe",
    "python.exe",
    "uvicorn.exe",
}


class PreventionEngine:
    def __init__(self) -> None:
        self.firewall = FirewallManager()

    def recommended_actions(self, event: UnifiedEvent) -> list[dict]:
        if event.risk_score < MIN_PREVENTION_SCORE:
            return []
        details = event.details
        actions: list[dict] = []
        ip = str(details.get("ip") or details.get("remote_ip") or "")
        if ip and (BLOCK_PRIVATE_IPS or not is_private_or_local_ip(ip)):
            actions.append({"action": "block_ip", "target": ip})
        domain = str(details.get("domain") or "")
        if domain and event.risk_score >= 70:
            actions.append({"action": "block_host", "target": domain})
        process = str(details.get("process_name") or details.get("process") or "").lower()
        if event.risk_score >= 80 and process and process not in PROTECTED_PROCESSES:
            actions.append({"action": "stop_process", "target": process})
        file_path = str(details.get("file_path") or "")
        if event.risk_score >= 80 and file_path:
            actions.append({"action": "quarantine_file", "target": file_path})
        if event.risk_score >= 90:
            actions.append({"action": "isolate_device", "target": event.device_id})
        return actions

    def execute(self, action: str, target: str) -> dict:
        if SAFE_MODE:
            return {"status": "success", "reason": "safe_mode", "action": action, "target": target}
        if action == "block_ip":
            ok, message = self.firewall.block_ip(target)
            return {"status": "success" if ok else "failed", "reason": message, "action": action, "target": target}
        if action == "allow_ip":
            ok, message = self.firewall.unblock_ip(target)
            return {"status": "success" if ok else "failed", "reason": message, "action": action, "target": target}
        if action == "block_host":
            ok, message = self.firewall.block_host(target)
            return {"status": "success" if ok else "failed", "reason": message, "action": action, "target": target}
        if action == "block_port":
            ok, message = self.firewall.block_port(int(target))
            return {"status": "success" if ok else "failed", "reason": message, "action": action, "target": target}
        if action == "stop_process":
            return self._stop_process(target)
        if action == "quarantine_file":
            return self._quarantine_file(target)
        if action == "isolate_device":
            return {"status": "success", "reason": "device_isolated_by_prevention_engine", "action": action, "target": target, "isolate": True}
        return {"status": "failed", "reason": "unknown_action", "action": action, "target": target}

    def _stop_process(self, process_name: str) -> dict:
        target = process_name.lower()
        if target in PROTECTED_PROCESSES:
            return {"status": "failed", "reason": "protected_process", "action": "stop_process", "target": process_name}
        stopped = 0
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                if str(proc.info.get("name") or "").lower() == target:
                    proc.terminate()
                    stopped += 1
            except (psutil.Error, OSError):
                continue
        return {"status": "success" if stopped else "failed", "reason": f"stopped={stopped}", "action": "stop_process", "target": process_name}

    def _quarantine_file(self, file_path: str) -> dict:
        source = Path(file_path)
        if not source.exists() or not source.is_file():
            return {"status": "failed", "reason": "file_not_found", "action": "quarantine_file", "target": file_path}
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        target = QUARANTINE_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{source.name}"
        try:
            shutil.move(str(source), str(target))
        except OSError as exc:
            return {"status": "failed", "reason": str(exc), "action": "quarantine_file", "target": file_path}
        return {"status": "success", "reason": str(target), "action": "quarantine_file", "target": file_path}
