from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.core.config import (
    PROJECT_ROOT,
    AGENT_TOKEN,
    APP_VERSION,
    CONFIG,
    DEVICE_NAME,
    DOWNLOAD_DIR,
    ENVIRONMENT,
    PRODUCTION,
)
from backend.agents.certificates import certificate_fingerprint, create_device_certificate
from backend.agents.registration import new_device_id, token_hash, token_valid
from backend.api.auth import bearer_payload, create_access_token, hash_password, new_secret_token, require_api_key, token_digest, verify_password
from backend.core.engine import XSIEngine
from backend.database.models import AgentEnrollRequest, AgentRegistration, DeviceCommand, DeviceEnrollmentComplete, DeviceEnrollmentRequest, Heartbeat, ManualAction, MobileLogin, NetworkTelemetry, PasswordResetConfirm, PasswordResetRequest, ProcessTelemetry, RefreshRequest, Setting, UnifiedEvent, UserLogin, UserRegister


def api_router(engine: XSIEngine) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "online", "environment": ENVIRONMENT, "version": APP_VERSION}

    @router.post("/auth/register")
    async def auth_register(register: UserRegister, request: Request) -> dict[str, Any]:
        username = register.username.strip().lower()
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="username must be at least 3 characters")
        if len(register.password) < 10:
            raise HTTPException(status_code=400, detail="password must be at least 10 characters")
        role = register.role if register.role in {"admin", "analyst", "viewer"} else "admin"
        try:
            user = await engine.storage.create_user(username, hash_password(register.password), role)
        except ValueError:
            raise HTTPException(status_code=409, detail="username already exists") from None
        tokens = await _create_user_tokens(engine, user, register.device_name, request)
        return {"user": _public_user(user), **tokens}

    @router.post("/auth/login")
    async def auth_login(login: UserLogin, request: Request) -> dict[str, Any]:
        user = await engine.storage.get_user_by_username(login.username)
        if not user or int(user.get("disabled") or 0) or not verify_password(login.password, str(user.get("password_hash") or "")):
            raise HTTPException(status_code=401, detail="invalid username or password")
        tokens = await _create_user_tokens(engine, user, login.device_name, request)
        return {"user": _public_user(user), **tokens}

    @router.post("/auth/refresh")
    async def auth_refresh(refresh: RefreshRequest) -> dict[str, Any]:
        session = await engine.storage.get_active_session_by_refresh_hash(token_digest(refresh.refresh_token))
        if not session:
            raise HTTPException(status_code=401, detail="invalid refresh token")
        await engine.storage.touch_session(str(session["session_id"]))
        access_token = create_access_token(
            str(session["user_id"]),
            str(session["role"]),
            expires_in=900,
            extra={"sid": session["session_id"], "username": session["username"]},
        )
        return {"access_token": access_token, "token_type": "bearer", "expires_in": 900}

    @router.get("/auth/me")
    async def auth_me(request: Request) -> dict[str, Any]:
        user, session = await _current_user(engine, request)
        return {"user": _public_user(user), "session": _public_session(session)}

    @router.get("/auth/sessions")
    async def auth_sessions(request: Request) -> dict[str, Any]:
        user, _ = await _current_user(engine, request)
        sessions = await engine.storage.list_user_sessions(int(user["id"]))
        return {"items": [_public_session(session) for session in sessions]}

    @router.post("/auth/logout")
    async def auth_logout(request: Request) -> dict[str, Any]:
        _, session = await _current_user(engine, request)
        await engine.storage.revoke_session(str(session["session_id"]))
        return {"status": "logged_out"}

    @router.post("/auth/password-reset/request")
    async def password_reset_request(reset: PasswordResetRequest) -> dict[str, Any]:
        user = await engine.storage.get_user_by_username(reset.username)
        if not user or int(user.get("disabled") or 0):
            return {"status": "ok"}
        reset_token = new_secret_token()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        await engine.storage.create_password_reset_token(int(user["id"]), token_digest(reset_token), expires_at)
        if PRODUCTION:
            return {"status": "ok"}
        return {"status": "ok", "reset_token": reset_token, "expires_at": expires_at}

    @router.post("/auth/password-reset/confirm")
    async def password_reset_confirm(reset: PasswordResetConfirm) -> dict[str, Any]:
        if len(reset.new_password) < 10:
            raise HTTPException(status_code=400, detail="password must be at least 10 characters")
        ok = await engine.storage.reset_password_with_token(token_digest(reset.reset_token), hash_password(reset.new_password))
        if not ok:
            raise HTTPException(status_code=400, detail="invalid or expired reset token")
        return {"status": "password_reset"}

    @router.get("/summary")
    async def summary() -> dict[str, Any]:
        return await engine.storage.summary()

    @router.get("/devices")
    async def devices(limit: int = 100) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("devices", limit)}

    @router.get("/devices/{device_id}")
    async def device_detail(device_id: str) -> dict[str, Any]:
        device = await engine.storage.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="device not found")
        return {"device": device}

    @router.get("/devices/{device_id}/command-center")
    async def device_command_center(device_id: str, limit: int = 100) -> dict[str, Any]:
        device = await engine.storage.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="device not found")
        events = await engine.storage.list_device_rows("events", device_id, limit)
        alerts = await engine.storage.list_device_rows("alerts", device_id, limit)
        processes = await engine.storage.list_device_rows("processes", device_id, limit)
        network = await engine.storage.list_device_rows("network_activity", device_id, limit)
        actions = await engine.storage.list_device_rows("actions", device_id, limit)
        return {
            "device": device,
            "overview": {
                "alert_count": len(alerts),
                "event_count": len(events),
                "process_count": len(processes),
                "network_count": len(network),
                "action_count": len(actions),
            },
            "alerts": alerts,
            "processes": processes,
            "network": network,
            "logs": events,
            "xdr": [event for event in events if str(event.get("source") or "").lower() == "edr"],
            "ips": actions,
            "settings": {
                "profile": device.get("profile"),
                "metadata": device.get("metadata"),
                "enrollment_status": device.get("enrollment_status"),
            },
        }

    @router.delete("/agents/{device_id}")
    async def remove_device(device_id: str, request: Request) -> dict[str, Any]:
        # Protected by admin role
        user, _ = await _current_user(engine, request)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="admin required")
        
        device = await engine.storage.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="device not found")
            
        return await engine.remove_device(device_id)

    @router.post("/agent/enroll")
    async def auto_enroll_agent(enroll: AgentEnrollRequest) -> dict[str, Any]:
        import secrets
        
        device_id = new_device_id(enroll.device_name or enroll.hostname)
        token = secrets.token_urlsafe(32)
        cert = create_device_certificate(device_id, {})
        fp = certificate_fingerprint(cert)
        
        result = await engine.register_device(
            device_id,
            enroll.device_name,
            "desktop",
            enroll.os_info,
            enroll.agent_version,
            enroll.hostname,
            "",
            token,
            {},
            {},
            fp,
        )
        return {"agent_id": device_id, "token": token}

    @router.post("/devices/enroll")
    async def enroll_device(enrollment: DeviceEnrollmentRequest, request: Request) -> dict[str, Any]:
        require_api_key(str(request.headers.get("x-api-key") or ""))
        import secrets

        device_id = new_device_id(enrollment.device_name or enrollment.hostname or enrollment.platform)
        token = secrets.token_urlsafe(32)
        cert = create_device_certificate(device_id, enrollment.metadata)
        fp = certificate_fingerprint(cert)
        profile = {**enrollment.profile, "os": enrollment.os, "device_type": enrollment.device_type}
        row = await engine.storage.create_device_enrollment(
            token_hash(token),
            device_id,
            enrollment.device_name,
            enrollment.device_type,
            enrollment.os,
            enrollment.hostname,
            enrollment.platform,
            enrollment.version,
            enrollment.metadata,
            profile,
            cert,
            fp,
        )
        return {"status": "pending", "device_id": device_id, "enrollment_token": token, "certificate": cert, "certificate_fingerprint": fp, "enrollment": row}

    @router.post("/devices/enroll/complete")
    async def complete_enrollment(complete: DeviceEnrollmentComplete) -> dict[str, Any]:
        enrollment = await engine.storage.get_pending_enrollment_by_token_hash(token_hash(complete.enrollment_token))
        if not enrollment:
            raise HTTPException(status_code=401, detail="invalid enrollment token")
        metadata = json_loads(str(enrollment.get("metadata") or "{}"))
        metadata.update(complete.metadata)
        profile = json_loads(str(enrollment.get("profile") or "{}"))
        result = await engine.register_device(
            complete.device_id or str(enrollment["device_id"]),
            str(enrollment["device_name"]),
            str(enrollment["device_type"] or "desktop"),
            str(enrollment["os"] or ""),
            complete.version or str(enrollment["version"] or ""),
            complete.hostname or str(enrollment["hostname"] or ""),
            complete.platform or str(enrollment["platform"] or ""),
            complete.enrollment_token,
            metadata,
            profile,
            str(enrollment["certificate_fingerprint"]),
        )
        await engine.storage.complete_device_enrollment(token_hash(complete.enrollment_token), result["device_id"])
        return {"status": "registered", "device_id": result["device_id"], "device": result, "certificate": enrollment["certificate"]}

    @router.post("/devices/register")
    async def register_device_from_dashboard(agent: AgentRegistration, request: Request) -> dict[str, Any]:
        require_api_key(str(request.headers.get("x-api-key") or ""))
        token = agent.token or AGENT_TOKEN
        result = await engine.register_device(
            agent.device_id,
            agent.device_name,
            agent.device_type,
            agent.os or agent.platform,
            agent.version,
            agent.hostname,
            agent.platform,
            token,
            agent.metadata,
            agent.profile,
            certificate_fingerprint(agent.certificate) if agent.certificate else "",
        )
        return {
            "status": "registered",
            "device_id": result["device_id"],
            "device": result,
            "agent_token": token,
        }

    @router.get("/events")
    async def events(
        limit: int = 100,
        offset: int = 0,
        search: str = "",
        device_id: str | None = None,
        source: str | None = None,
        severity: str | None = None,
    ) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("events", limit, search, offset=offset, device_id=device_id, source=source, severity=severity)}

    @router.get("/alerts")
    async def alerts(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("alerts", limit, offset=offset)}

    @router.get("/processes")
    async def processes(limit: int = 100) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("processes", limit)}

    @router.get("/network")
    async def network(limit: int = 100) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("network_activity", limit)}

    @router.get("/actions")
    async def actions(limit: int = 100) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("actions", limit)}

    @router.get("/logs")
    async def logs(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("events", limit, offset=offset)}

    @router.get("/xdr")
    async def xdr(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        items = await engine.storage.list_rows("events", limit, offset=offset)
        xdr_items = [item for item in items if str(item.get("source") or "").lower() == "edr" or str(item.get("event_type") or "").upper() == "XDR"]
        return {"items": xdr_items}

    @router.get("/ips")
    async def ips(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("actions", limit, offset=offset)}

    @router.get("/rules")
    async def rules(limit: int = 100) -> dict[str, Any]:
        return {"items": await engine.storage.list_rows("rules", limit)}

    async def verify_agent_signature(request: Request):
        signature = request.headers.get("X-Agent-Signature")
        timestamp = request.headers.get("X-Agent-Timestamp")
        device_id = request.headers.get("X-Device-Id")
        auth_header = request.headers.get("Authorization")
        
        if not signature or not timestamp:
            raise HTTPException(status_code=401, detail="missing agent signature headers")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing Bearer token")
            
        token = auth_header.split(" ")[1]
        
        try:
            ts = datetime.fromisoformat(timestamp)
            if abs((datetime.now(timezone.utc) - ts).total_seconds()) > 300:
                raise HTTPException(status_code=401, detail="timestamp expired")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid timestamp format")
            
        body_bytes = await request.body()
        
        # We don't query DB here on every ping for speed, but if we need to we can. 
        # The Bearer token acts as the HMAC key to verify payload integrity.
        import hmac, hashlib
        message = timestamp.encode('utf-8') + body_bytes
        expected = hmac.new(token.encode('utf-8'), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            import logging
            logging.getLogger("uvicorn").warning(f"Agent signature mismatch for device {device_id}")
            raise HTTPException(status_code=401, detail="invalid signature")

    @router.post("/events")
    async def ingest_event(event: UnifiedEvent) -> dict[str, Any]:
        stored = await engine.ingest(event)
        return {"status": "ok", "event": stored.model_dump()}

    @router.post("/agents/register")
    async def register(agent: AgentRegistration, request: Request) -> dict[str, Any]:
        from backend.core.config import AGENT_TOKEN
        import logging
        import hmac, hashlib
        logger = logging.getLogger("uvicorn")
        
        signature = agent.signature
        timestamp = agent.timestamp
        
        if not agent.device_id:
            raise HTTPException(status_code=400, detail={"error": "Invalid request", "message": "Registration requires device_id."})
        if not agent.hostname:
            raise HTTPException(status_code=400, detail={"error": "Invalid request", "message": "Registration requires hostname."})
        if not agent.platform:
            raise HTTPException(status_code=400, detail={"error": "Invalid request", "message": "Registration requires platform."})
        if not signature or not timestamp:
            logger.warning(f"Registration FAILED: device_id={agent.device_id} - Missing signature")
            raise HTTPException(status_code=401, detail={"error": "Missing signature", "message": "Registration requires timestamp and signature. Sign device_id + timestamp with the enrollment token using HMAC-SHA256."})
            
        try:
            ts = datetime.fromisoformat(timestamp)
            if abs((datetime.now(timezone.utc) - ts).total_seconds()) > 300:
                raise HTTPException(status_code=401, detail={"error": "Validation failed", "message": "Registration timestamp is expired (allowed window is 5 minutes)."})
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "Invalid request format", "message": "Timestamp is not in valid ISO format."})

        message = agent.device_id + timestamp
        expected = hmac.new(AGENT_TOKEN.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(signature, expected):
            logger.warning(f"Registration FAILED: device_id={agent.device_id} - Invalid enrollment secret signature")
            raise HTTPException(status_code=401, detail={"error": "Configuration issue", "message": "Invalid enrollment secret signature. Check your agent token."})

        logger.info(f"Registration SUCCESS: device_id={agent.device_id} hostname={agent.hostname}")
        
        import secrets
        result = await engine.register_device(
            agent.device_id,
            agent.device_name,
            agent.device_type,
            agent.os or agent.platform,
            agent.agent_version or agent.version,
            agent.hostname,
            agent.platform,
            AGENT_TOKEN,
            agent.metadata,
            agent.profile,
            certificate_fingerprint(agent.certificate) if agent.certificate else "",
        )
        return {
            "status": "registered",
            "endpoint_id": result["device_id"],
            "device_id": result["device_id"],
            "enrollment_status": "enrolled",
            "session_token": AGENT_TOKEN,
            "encryption_key": secrets.token_urlsafe(32),
            "next_heartbeat_interval": 15,
            "heartbeat_interval": 15,
            "connection_configuration": {"server_url": str(request.base_url), "features": ["heartbeat", "telemetry"]},
            "device": result
        }

    @router.get("/agents/version")
    async def get_agent_version() -> dict[str, Any]:
        from backend.core.config import CONFIG
        version = CONFIG["downloads"].get("current_version", "0.4.0")
        latest = CONFIG["downloads"].get("latest_version", version)
        return {"current_agent_version": version, "latest_agent_version": latest}

    @router.get("/agents/deployment/info")
    async def agent_deployment_info(request: Request) -> dict[str, Any]:
        version = str(CONFIG["downloads"].get("current_version", "0.4.0"))
        latest = str(CONFIG["downloads"].get("latest_version", version))
        base_url = str(request.base_url).rstrip("/")
        return {
            "windows": {
                "version": version,
                "latest_version": latest,
                "download_url": f"{base_url}/api/agents/download/windows",
                "installer": "XSI-Agent-Setup.exe",
            },
            "android": {
                "version": version,
                "latest_version": latest,
                "download_url": f"{base_url}/api/agents/download/android",
                "installer": "XSI-Agent.apk",
            },
            "required_registration_fields": [
                "device_id",
                "hostname",
                "agent_version",
                "platform",
                "timestamp",
                "signature",
            ],
        }

    @router.post("/agents/heartbeat")
    async def heartbeat(beat: Heartbeat, request: Request) -> dict[str, Any]:
        await verify_agent_signature(request)
        result = await engine.heartbeat(beat.device_id, beat.status, beat.health or beat.metrics, beat.agent_version)
        return {"status": "ok", "device": result}

    @router.post("/agents/processes")
    async def ingest_processes(telemetry: ProcessTelemetry, request: Request) -> dict[str, Any]:
        await verify_agent_signature(request)
        await engine.ingest_processes(telemetry.device_id, telemetry.processes)
        return {"status": "ok"}

    @router.post("/agents/network")
    async def ingest_network(telemetry: NetworkTelemetry, request: Request) -> dict[str, Any]:
        await verify_agent_signature(request)
        await engine.ingest_network(telemetry.device_id, telemetry.activity)
        return {"status": "ok"}

    @router.post("/agents/event")
    async def agent_event(request: Request) -> dict[str, Any]:
        await verify_agent_signature(request)
        body = await request.json()
        stored = await engine.ingest(body)
        return {"status": "ok", "event": stored.model_dump()}

    @router.get("/agents/{device_id}/commands")
    async def agent_commands(device_id: str, token: str) -> dict[str, Any]:
        if not token_valid(token):
            raise HTTPException(status_code=401, detail="invalid agent token")
        command = await engine.next_command(device_id)
        return {"command": command}

    @router.post("/agents/command")
    async def enqueue_command(command: DeviceCommand, request: Request) -> dict[str, Any]:
        require_api_key(str(request.headers.get("x-api-key") or ""))
        await engine.queue_command(command.device_id, {"command": command.command, "details": command.details})
        return {"status": "queued"}

    @router.post("/agents/action")
    async def agent_action(action: ManualAction, request: Request) -> dict[str, Any]:
        await verify_agent_signature(request)
        body = await request.json()
        device_id = str(body.get("device_id", ""))
        return await engine.manual_action(device_id, action.action, action.target, action.details)

    @router.post("/agents/{device_id}/rotate-token")
    async def rotate_token(device_id: str, request: Request) -> dict[str, Any]:
        require_api_key(str(request.headers.get("x-api-key") or ""))
        import secrets

        new_token = secrets.token_urlsafe(32)
        await engine.storage.rotate_device_token(device_id, token_hash(new_token))
        await engine.event_bus.publish({"type": "TOKEN_ROTATED", "device_id": device_id})
        return {"device_id": device_id, "token": new_token}

    @router.post("/ips/action")
    async def ips_action(action: ManualAction) -> dict[str, Any]:
        return await engine.manual_action(DEVICE_NAME, action.action, action.target, action.details)

    @router.get("/settings")
    async def settings(request: Request) -> dict[str, Any]:
        user, _ = await _current_user(engine, request)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="admin required")
        system = await engine.storage.get_setting("system")
        downloads = CONFIG.get("downloads", {})
        return {"config": {"downloads": {"current_version": downloads.get("current_version"), "latest_version": downloads.get("latest_version")}}, "system": system or {}}

    @router.get("/settings/{key}")
    async def get_setting(key: str, request: Request) -> dict[str, Any]:
        user, _ = await _current_user(engine, request)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="admin required")
        value = await engine.storage.get_setting(key)
        return {"key": key, "value": value or {}}

    @router.post("/settings/{key}")
    async def update_setting(key: str, setting: Setting, request: Request) -> dict[str, Any]:
        user, _ = await _current_user(engine, request)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="admin required")
        await engine.storage.set_setting(key, setting.value)
        return {"status": "ok"}

    @router.get("/agents/windows/download")
    async def download_windows_agent() -> FileResponse:
        # Point to the professional installer generated by Inno Setup
        path = PROJECT_ROOT / "windows" / "installer" / "XSI-Agent-Setup.exe"
        if not path.exists():
            # Fallback to backend/downloads if not in windows folder
            path = Path(DOWNLOAD_DIR) / "XSI-Agent-Setup.exe"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("DUMMY EXE CONTENT", encoding="utf-8")
        return FileResponse(path, filename="XSI-Agent-Setup.exe")

    @router.get("/agents/android/download")
    async def download_android_agent() -> FileResponse:
        # Point to the APK generated in Phase 1
        path = PROJECT_ROOT / "android" / "dist" / "XSI-Agent.apk"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("DUMMY APK CONTENT", encoding="utf-8")
        return FileResponse(path, filename="XSI-Agent.apk")

    @router.post("/mobile/login")
    async def mobile_login(login: MobileLogin) -> dict[str, Any]:
        require_api_key(login.api_key)
        return {"access_token": create_access_token("mobile-client"), "token_type": "bearer"}

    @router.get("/mobile/devices")
    async def mobile_devices(request: Request) -> dict[str, Any]:
        bearer_payload(request)
        return {"items": await engine.storage.list_rows("devices", 200)}

    @router.get("/mobile/alerts")
    async def mobile_alerts(request: Request, limit: int = 100) -> dict[str, Any]:
        bearer_payload(request)
        return {"items": await engine.storage.list_rows("alerts", limit)}

    @router.get("/mobile/status")
    async def mobile_status(request: Request) -> dict[str, Any]:
        bearer_payload(request)
        return await engine.storage.summary()

    return router


async def _create_user_tokens(engine: XSIEngine, user: dict[str, Any], device_name: str, request: Request) -> dict[str, Any]:
    session_id = new_secret_token()
    refresh_token = new_secret_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    session = await engine.storage.create_user_session(
        int(user["id"]),
        session_id,
        token_digest(refresh_token),
        device_name,
        str(request.headers.get("user-agent") or ""),
        request.client.host if request.client else "",
        expires_at,
    )
    access_token = create_access_token(
        str(user["id"]),
        str(user["role"]),
        expires_in=900,
        extra={"sid": session["session_id"], "username": user["username"]},
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 900,
        "session": _public_session(session),
    }


async def _current_user(engine: XSIEngine, request: Request) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = bearer_payload(request)
    session_id = str(payload.get("sid") or "")
    if not session_id:
        raise HTTPException(status_code=401, detail="missing session")
    session = await engine.storage.get_active_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="invalid session")
    user = await engine.storage.get_user_by_id(int(session["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="invalid user")
    await engine.storage.touch_session(session_id)
    return user, session


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "created_at": user.get("created_at"),
    }


def _public_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session.get("session_id"),
        "device_name": session.get("device_name"),
        "user_agent": session.get("user_agent"),
        "ip": session.get("ip"),
        "created_at": session.get("created_at"),
        "last_seen": session.get("last_seen"),
        "expires_at": session.get("expires_at"),
        "revoked_at": session.get("revoked_at"),
    }


def json_loads(value: str) -> dict[str, Any]:
    import json

    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
