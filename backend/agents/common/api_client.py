from __future__ import annotations
import json
import logging
import requests
import hmac
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("api_client")

class XSIApiClient:
    def __init__(self, server_url: str, agent_token: str, device_id: str | None = None, data_dir: Path | None = None):
        self.server_url = server_url.rstrip('/')
        self.agent_token = agent_token
        self.device_id = device_id
        self.session = requests.Session()
        self.data_dir = data_dir
        self.queue_file = self.data_dir / "queue.jsonl" if self.data_dir else None
        self.queue_lock = threading.Lock()

    def _post(self, path: str, payload: dict[str, Any], queueable: bool = True) -> dict[str, Any]:
        body = json.dumps(payload, separators=(',', ':'))
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.agent_token:
            message = timestamp + body
            signature = hmac.new(self.agent_token.encode(), message.encode(), hashlib.sha256).hexdigest()
            headers = {
                "Authorization": f"Bearer {self.agent_token}",
                "X-Agent-Signature": signature,
                "X-Agent-Timestamp": timestamp,
                "X-Device-Id": self.device_id or "",
                "Content-Type": "application/json"
            }
        else:
            headers = {"Content-Type": "application/json"}
            
        url = f"{self.server_url}{path}"
        try:
            resp = self.session.post(url, data=body.encode('utf-8'), headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if queueable and self.queue_file:
                logger.warning(f"Request to {path} failed. Queuing payload offline. Error: {e}")
                self._enqueue(path, payload)
            raise

    def _enqueue(self, path: str, payload: dict[str, Any]):
        if not self.queue_file:
            return
        try:
            with self.queue_lock:
                with open(self.queue_file, 'a') as f:
                    f.write(json.dumps({"path": path, "payload": payload}) + "\n")
        except Exception as e:
            logger.error(f"Failed to queue payload: {e}")

    def flush_queue(self):
        if not self.queue_file or not self.queue_file.exists():
            return
        
        try:
            with self.queue_lock:
                with open(self.queue_file, 'r') as f:
                    lines = f.readlines()
            
            if not lines:
                return

            logger.info(f"Flushing {len(lines)} queued items...")
            
            remaining = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    body = json.dumps(item["payload"], separators=(',', ':'))
                    timestamp = datetime.now(timezone.utc).isoformat()
                    headers = {"Content-Type": "application/json"}
                    if self.agent_token:
                        message = timestamp + body
                        signature = hmac.new(self.agent_token.encode(), message.encode(), hashlib.sha256).hexdigest()
                        headers.update({
                            "Authorization": f"Bearer {self.agent_token}",
                            "X-Agent-Signature": signature,
                            "X-Agent-Timestamp": timestamp,
                            "X-Device-Id": self.device_id or ""
                        })
                    resp = self.session.post(f"{self.server_url}{item['path']}", data=body.encode('utf-8'), headers=headers, timeout=10)
                    resp.raise_for_status()
                except Exception as e:
                    logger.warning(f"Failed to flush item {item.get('path', 'unknown')}: {e}")
                    remaining.append(line)
            
            with self.queue_lock:
                with open(self.queue_file, 'w') as f:
                    f.writelines(remaining)
                
        except Exception as e:
            logger.error(f"Error during queue flush: {e}")

    def register(self, device_name: str, os_info: str, platform: str, version: str) -> dict[str, Any]:
        if not self.agent_token:
            raise ValueError("Registration requires an enrollment token")
        device_id = self.device_id or f"xsi-{device_name.lower()}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Sign with enrollment secret (currently stored in self.agent_token before auth)
        message = device_id + timestamp
        signature = hmac.new(self.agent_token.encode(), message.encode(), hashlib.sha256).hexdigest()

        payload = {
            "device_id": device_id,
            "device_name": device_name,
            "device_type": "desktop",
            "os": os_info,
            "version": version,
            "agent_version": version,
            "hostname": device_name,
            "platform": platform,
            "token": self.agent_token,
            "timestamp": timestamp,
            "signature": signature
        }
        
        body = json.dumps(payload, separators=(',', ':'))
        headers = {"Content-Type": "application/json"}
        
        resp = self.session.post(f"{self.server_url}/api/agents/register", data=body.encode('utf-8'), headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def heartbeat(self, status: str, health: dict[str, Any], version: str) -> dict[str, Any]:
        payload = {
            "device_id": self.device_id,
            "status": status,
            "health": health,
            "agent_version": version,
            "token": self.agent_token,
            "metrics": health
        }
        return self._post("/api/agents/heartbeat", payload, queueable=False)

    def send_processes(self, processes: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "device_id": self.device_id,
            "token": self.agent_token,
            "processes": processes
        }
        return self._post("/api/agents/processes", payload, queueable=True)

    def send_network(self, activity: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "device_id": self.device_id,
            "token": self.agent_token,
            "activity": activity
        }
        return self._post("/api/agents/network", payload, queueable=True)

    def send_event(self, event_type: str, severity: str, source: str, details: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "device_id": self.device_id,
            "event_type": event_type,
            "severity": severity,
            "source": source,
            "details": details,
            "token": self.agent_token,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return self._post("/api/agents/event", payload, queueable=True)

    def get_commands(self) -> list[dict[str, Any]]:
        # GET request cannot be signed with body, we will pass it normally 
        # (could sign query params, but skipping for brevity)
        resp = self.session.get(f"{self.server_url}/api/agents/{self.device_id}/commands", params={"token": self.agent_token}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [data["command"]] if data.get("command") else []

    def send_action(self, action: str, target: str, details: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "device_id": self.device_id,
            "action": action,
            "target": target,
            "details": details,
            "token": self.agent_token,
        }
        return self._post("/api/agents/action", payload, queueable=True)
