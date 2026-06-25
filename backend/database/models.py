from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UnifiedEvent(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    device_id: str = "controller"
    source: str = "xsi"
    event_type: str = "UNKNOWN"
    severity: str = "safe"
    risk_score: int = 0
    mitre_attack: list[str] = Field(default_factory=list)
    ioc_matched: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "UnifiedEvent":
        details = dict(raw.get("details") or {})
        for key, value in raw.items():
            if key not in {
                "timestamp",
                "device_id",
                "agent_id",
                "source",
                "event_type",
                "type",
                "severity",
                "risk_score",
                "mitre_attack",
                "ioc_matched",
                "details",
            }:
                details.setdefault(key, value)
        return cls(
            timestamp=str(raw.get("timestamp") or utc_now_iso()),
            device_id=str(raw.get("device_id") or raw.get("agent_id") or "controller"),
            source=str(raw.get("source") or "edr"),
            event_type=str(raw.get("event_type") or raw.get("type") or "UNKNOWN").upper(),
            severity=str(raw.get("severity") or "safe").lower(),
            risk_score=max(0, min(100, int(raw.get("risk_score") or raw.get("behavior_score") or 0))),
            mitre_attack=list(raw.get("mitre_attack") or []),
            ioc_matched=list(raw.get("ioc_matched") or []),
            details=details,
        )


class AgentRegistration(BaseModel):
    device_id: str = ""
    device_name: str = ""
    device_type: str = "desktop"
    os: str = ""
    version: str = "0.1.0"
    agent_version: str = ""
    hostname: str = ""
    platform: str = ""
    token: str = ""
    timestamp: str = ""
    signature: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    certificate: str = ""


class AgentEnrollRequest(BaseModel):
    device_name: str
    hostname: str = ""
    os_info: str = ""
    agent_version: str = "0.3.0"


class DeviceEnrollmentRequest(BaseModel):
    device_name: str
    device_type: str = "desktop"
    os: str = "Windows"
    hostname: str = ""
    platform: str = ""
    version: str = "0.1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)


class DeviceEnrollmentComplete(BaseModel):
    enrollment_token: str
    device_id: str = ""
    hostname: str = ""
    platform: str = ""
    version: str = "0.1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Heartbeat(BaseModel):
    device_id: str
    status: str = "alive"
    health: dict[str, Any] = Field(default_factory=dict)
    agent_version: str = "0.1.0"
    timestamp: str = Field(default_factory=utc_now_iso)
    token: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class ProcessTelemetry(BaseModel):
    device_id: str
    token: str
    processes: list[dict[str, Any]]


class NetworkTelemetry(BaseModel):
    device_id: str
    token: str
    activity: list[dict[str, Any]]


class MobileLogin(BaseModel):
    api_key: str


class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "admin"
    device_name: str = "Dashboard"


class UserLogin(BaseModel):
    username: str
    password: str
    device_name: str = "Dashboard"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    username: str


class PasswordResetConfirm(BaseModel):
    reset_token: str
    new_password: str


class DeviceCommand(BaseModel):
    device_id: str
    command: str
    details: dict[str, Any] = Field(default_factory=dict)


class ManualAction(BaseModel):
    action: str
    target: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class Setting(BaseModel):
    key: str
    value: dict[str, Any]
    category: str = "system"
