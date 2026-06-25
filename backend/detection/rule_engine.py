from __future__ import annotations

from backend.database.models import UnifiedEvent


class RuleEngine:
    def __init__(self) -> None:
        self.iocs = {
            "ips": {"1.2.3.4", "8.8.4.4", "45.33.32.156"},
            "domains": {"malicious-site.com", "attacker.net", "evil-command.xyz"},
            "hashes": {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        }

    def apply(self, event: UnifiedEvent) -> UnifiedEvent:
        details = dict(event.details)
        tags = list(details.get("tags") or [])
        mitre = list(event.mitre_attack)
        iocs = list(event.ioc_matched)

        # MITRE ATT&CK Mapping
        if event.event_type == "PORT_SCAN":
            event = event.model_copy(update={"risk_score": max(event.risk_score, 60)})
            tags.append("ids_port_scan")
            mitre.append("T1595.001")  # Active Scanning: IP Addresses
        if event.event_type == "SYN_FLOOD":
            event = event.model_copy(update={"risk_score": max(event.risk_score, 80)})
            tags.append("ids_syn_flood")
            mitre.append("T1498.001")  # Network Denial of Service: Direct Network Flood
        
        process = str(details.get("process_name") or details.get("process") or "").lower()
        command = str(details.get("command_line") or details.get("cmdline") or "").lower()

        if process in {"powershell.exe", "cmd.exe"} and any(marker in command for marker in (" -enc", "downloadstring", "invoke-webrequest")):
            event = event.model_copy(update={"risk_score": max(event.risk_score, 75)})
            tags.append("suspicious_shell")
            mitre.append("T1059.001")  # Command and Scripting Interpreter: PowerShell

        if process in {"certutil.exe", "bitsadmin.exe", "regsvr32.exe"} and any(marker in command for marker in ("-urlcache", "-f", "http")):
            event = event.model_copy(update={"risk_score": max(event.risk_score, 70)})
            tags.append("living_off_the_land")
            mitre.append("T1218")  # System Binary Proxy Execution

        if event.event_type == "FILE" and any(ext in str(details.get("file_path") or "").lower() for ext in (".exe", ".dll", ".ps1", ".bat")):
            if str(details.get("operation") or "").lower() == "create":
                tags.append("executable_creation")
                mitre.append("T1105")  # Ingress Tool Transfer

        # Network monitoring - suspicious connections
        port = int(details.get("port") or 0)
        if port in {4444, 5555, 6666, 7777, 8888, 9999}:
            event = event.model_copy(update={"risk_score": max(event.risk_score, 65)})
            tags.append("suspicious_port")
            mitre.append("T1041")  # Exfiltration Over C2 Channel

        # Masquerading detection
        if process == "svchost.exe" and "system32" not in command:
            event = event.model_copy(update={"risk_score": max(event.risk_score, 85)})
            tags.append("masquerading")
            mitre.append("T1036")  # Masquerading

        details["tags"] = list(dict.fromkeys(tags))
        ip = str(details.get("ip") or details.get("remote_ip") or "")
        if ip in self.iocs["ips"]:
            iocs.append(f"ip:{ip}")
            event = event.model_copy(update={"risk_score": max(event.risk_score, 90)})
            tags.append("ioc_match")

        domain = str(details.get("domain") or details.get("hostname") or "")
        if domain in self.iocs["domains"]:
            iocs.append(f"domain:{domain}")
            event = event.model_copy(update={"risk_score": max(event.risk_score, 90)})
            tags.append("ioc_match")

        file_hash = str(details.get("hash") or details.get("sha256") or "")
        if file_hash in self.iocs["hashes"]:
            iocs.append(f"hash:{file_hash}")
            event = event.model_copy(update={"risk_score": max(event.risk_score, 95)})
            tags.append("ioc_match")

        details["tags"] = list(dict.fromkeys(tags))
        return event.model_copy(update={
            "details": details,
            "mitre_attack": list(dict.fromkeys(mitre)),
            "ioc_matched": list(dict.fromkeys(iocs))
        })
