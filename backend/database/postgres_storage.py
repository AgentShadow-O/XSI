from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from backend.database.models import UnifiedEvent


class PostgresStorage:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.database_url, row_factory=dict_row)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id BIGSERIAL PRIMARY KEY,
                    device_id TEXT UNIQUE NOT NULL,
                    device_name TEXT,
                    device_type TEXT,
                    os TEXT,
                    version TEXT,
                    hostname TEXT,
                    platform TEXT,
                    token_hash TEXT,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    last_seen TEXT,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    risk_score INTEGER NOT NULL DEFAULT 0,
                    health TEXT,
                    agent_version TEXT,
                    token_issued_at TEXT,
                    token_rotated_at TEXT,
                    certificate_fingerprint TEXT,
                    metadata TEXT,
                    profile TEXT,
                    enrollment_status TEXT NOT NULL DEFAULT 'registered',
                    enrolled_at TEXT
                );
                CREATE TABLE IF NOT EXISTS device_enrollments (
                    id BIGSERIAL PRIMARY KEY,
                    enrollment_token_hash TEXT UNIQUE NOT NULL,
                    device_id TEXT UNIQUE NOT NULL,
                    device_name TEXT NOT NULL,
                    device_type TEXT,
                    os TEXT,
                    hostname TEXT,
                    platform TEXT,
                    version TEXT,
                    metadata TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    certificate TEXT NOT NULL,
                    certificate_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    mitre_attack TEXT,
                    ioc_matched TEXT,
                    details TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id BIGSERIAL PRIMARY KEY,
                    event_id BIGINT,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processes (
                    id BIGSERIAL PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    pid INTEGER,
                    name TEXT,
                    command_line TEXT,
                    risk_score INTEGER DEFAULT 0,
                    last_seen TEXT
                );
                CREATE TABLE IF NOT EXISTS network_activity (
                    id BIGSERIAL PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    ip TEXT,
                    port INTEGER,
                    protocol TEXT,
                    direction TEXT,
                    risk_score INTEGER DEFAULT 0,
                    last_seen TEXT
                );
                CREATE TABLE IF NOT EXISTS actions (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rules (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    rule_type TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    definition TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT,
                    created_at TEXT,
                    disabled INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    session_id TEXT UNIQUE NOT NULL,
                    refresh_token_hash TEXT UNIQUE NOT NULL,
                    device_name TEXT,
                    user_agent TEXT,
                    ip TEXT,
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    token_hash TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_risk ON events(risk_score);
                CREATE INDEX IF NOT EXISTS idx_alerts_risk ON alerts(risk_score);
                CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
                CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_sessions_session ON user_sessions(session_id);
                CREATE INDEX IF NOT EXISTS idx_password_reset_hash ON password_reset_tokens(token_hash);
                CREATE INDEX IF NOT EXISTS idx_device_enrollments_token ON device_enrollments(enrollment_token_hash);
                CREATE INDEX IF NOT EXISTS idx_device_enrollments_device ON device_enrollments(device_id);
                CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn: Any) -> None:
        columns = {
            "devices": {
                "created_at": "TEXT NOT NULL DEFAULT ''",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
                "certificate_fingerprint": "TEXT",
                "metadata": "TEXT",
                "profile": "TEXT",
                "enrollment_status": "TEXT NOT NULL DEFAULT 'registered'",
                "enrolled_at": "TEXT",
            },
            "events": {
                "mitre_attack": "TEXT",
                "ioc_matched": "TEXT",
            },
        }
        for table, wanted in columns.items():
            existing = {row["column_name"] for row in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,)).fetchall()}
            for name, definition in wanted.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    async def store_event(self, event: UnifiedEvent) -> int:
        return await asyncio.to_thread(self._store_event_sync, event)

    def _store_event_sync(self, event: UnifiedEvent) -> int:
        details = json.dumps(event.details, ensure_ascii=True)
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO events(timestamp, device_id, source, event_type, severity, risk_score, mitre_attack, ioc_matched, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    event.timestamp,
                    event.device_id,
                    event.source,
                    event.event_type,
                    event.severity,
                    event.risk_score,
                    json.dumps(event.mitre_attack or [], ensure_ascii=True),
                    json.dumps(event.ioc_matched or [], ensure_ascii=True),
                    details,
                ),
            ).fetchone()
            event_id = int(row["id"])
            if event.risk_score >= 50 or event.severity in {"warning", "critical"}:
                conn.execute(
                    """
                    INSERT INTO alerts(event_id, timestamp, device_id, severity, risk_score, title, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (event_id, event.timestamp, event.device_id, event.severity, event.risk_score, f"{event.source}:{event.event_type}", details),
                )
        return event_id

    async def register_device(self, device_id: str, device_name: str, device_type: str, os_name: str, version: str, hostname: str, platform: str, token_hash: str, metadata: dict[str, Any] | None = None, profile: dict[str, Any] | None = None, certificate_fingerprint: str = "") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            before = conn.execute("SELECT status FROM devices WHERE device_id = %s", (device_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO devices(device_id, device_name, device_type, os, version, hostname, platform, token_hash, status, last_seen, created_at, updated_at, risk_score, token_issued_at, certificate_fingerprint, metadata, profile, enrollment_status, enrolled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'online', %s, %s, %s, 0, %s, %s, %s, %s, 'registered', %s)
                ON CONFLICT(device_id) DO UPDATE SET
                    device_name=EXCLUDED.device_name,
                    device_type=EXCLUDED.device_type,
                    os=EXCLUDED.os,
                    version=EXCLUDED.version,
                    hostname=EXCLUDED.hostname,
                    platform=EXCLUDED.platform,
                    token_hash=EXCLUDED.token_hash,
                    status='online',
                    last_seen=EXCLUDED.last_seen,
                    updated_at=EXCLUDED.updated_at,
                    certificate_fingerprint=COALESCE(NULLIF(EXCLUDED.certificate_fingerprint, ''), devices.certificate_fingerprint),
                    metadata=EXCLUDED.metadata,
                    profile=EXCLUDED.profile,
                    enrollment_status='registered',
                    enrolled_at=COALESCE(devices.enrolled_at, EXCLUDED.enrolled_at)
                """,
                (
                    device_id,
                    device_name,
                    device_type,
                    os_name,
                    version,
                    hostname,
                    platform,
                    token_hash,
                    now,
                    now,
                    now,
                    now,
                    certificate_fingerprint,
                    json.dumps(metadata or {}, ensure_ascii=True),
                    json.dumps(profile or {}, ensure_ascii=True),
                    now,
                ),
            )
        return {"device_id": device_id, "previous_status": before["status"] if before else "", "status": "online", "last_seen": now}

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM devices WHERE device_id = %s", (device_id,)).fetchone()
        return dict(row) if row else None

    async def create_device_enrollment(
        self,
        enrollment_token_hash: str,
        device_id: str,
        device_name: str,
        device_type: str,
        os_name: str,
        hostname: str,
        platform: str,
        version: str,
        metadata: dict[str, Any],
        profile: dict[str, Any],
        certificate: str,
        certificate_fingerprint: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO device_enrollments(enrollment_token_hash, device_id, device_name, device_type, os, hostname, platform, version, metadata, profile, certificate, certificate_fingerprint, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                ON CONFLICT(device_id) DO UPDATE SET
                    enrollment_token_hash=EXCLUDED.enrollment_token_hash,
                    device_name=EXCLUDED.device_name,
                    device_type=EXCLUDED.device_type,
                    os=EXCLUDED.os,
                    hostname=EXCLUDED.hostname,
                    platform=EXCLUDED.platform,
                    version=EXCLUDED.version,
                    metadata=EXCLUDED.metadata,
                    profile=EXCLUDED.profile,
                    certificate=EXCLUDED.certificate,
                    certificate_fingerprint=EXCLUDED.certificate_fingerprint,
                    status='pending',
                    created_at=EXCLUDED.created_at,
                    completed_at=NULL
                RETURNING *
                """,
                (
                    enrollment_token_hash,
                    device_id,
                    device_name,
                    device_type,
                    os_name,
                    hostname,
                    platform,
                    version,
                    json.dumps(metadata, ensure_ascii=True),
                    json.dumps(profile, ensure_ascii=True),
                    certificate,
                    certificate_fingerprint,
                    now,
                ),
            ).fetchone()
        return dict(row)

    async def get_pending_enrollment_by_token_hash(self, enrollment_token_hash: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_enrollments WHERE enrollment_token_hash = %s AND status = 'pending'",
                (enrollment_token_hash,),
            ).fetchone()
        return dict(row) if row else None

    async def complete_device_enrollment(self, enrollment_token_hash: str, device_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE device_enrollments SET status = 'completed', completed_at = %s WHERE enrollment_token_hash = %s AND device_id = %s",
                (now, enrollment_token_hash, device_id),
            )

    async def heartbeat(self, device_id: str, status: str, health: dict[str, Any] | None = None, agent_version: str = "") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        normalized_status = "online" if status.lower() in {"alive", "online", "ok"} else status.lower()
        with self._connect() as conn:
            before = conn.execute("SELECT status FROM devices WHERE device_id = %s", (device_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO devices(device_id, device_name, device_type, os, version, status, last_seen, created_at, updated_at, health, agent_version, risk_score)
                VALUES (%s, %s, 'unknown', '', %s, %s, %s, %s, %s, %s, %s, 0)
                ON CONFLICT(device_id) DO UPDATE SET
                    status=EXCLUDED.status,
                    last_seen=EXCLUDED.last_seen,
                    updated_at=EXCLUDED.updated_at,
                    health=EXCLUDED.health,
                    agent_version=EXCLUDED.agent_version
                """,
                (device_id, device_id, agent_version, normalized_status, now, now, now, json.dumps(health or {}, ensure_ascii=True), agent_version),
            )
        return {"device_id": device_id, "previous_status": before["status"] if before else "", "status": normalized_status, "last_seen": now}

    async def mark_offline_stale(self, timeout_seconds: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        changed: list[dict[str, Any]] = []
        with self._connect() as conn:
            rows = conn.execute("SELECT device_id, status, last_seen FROM devices WHERE status != 'offline'").fetchall()
            for row in rows:
                device_id = row["device_id"]
                status = row["status"]
                last_seen_raw = row["last_seen"]
                try:
                    last_seen = datetime.fromisoformat(str(last_seen_raw).replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    last_seen = datetime.fromtimestamp(0, tz=timezone.utc)
                if (now - last_seen).total_seconds() > timeout_seconds:
                    conn.execute("UPDATE devices SET status = 'offline' WHERE device_id = %s", (device_id,))
                    changed.append({"device_id": device_id, "previous_status": status, "status": "offline", "last_seen": str(last_seen_raw or "")})
        return changed

    async def rotate_device_token(self, device_id: str, new_token_hash: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE devices SET token_hash = %s, token_rotated_at = %s, updated_at = %s WHERE device_id = %s", (new_token_hash, now, now, device_id))

    async def remove_device(self, device_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._remove_device_sync, device_id, now)

    def _remove_device_sync(self, device_id: str, now: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE devices SET status = 'removed', token_hash = '', token_rotated_at = %s, updated_at = %s WHERE device_id = %s", (now, now, device_id))
            conn.execute("DELETE FROM processes WHERE device_id = %s", (device_id,))
            conn.execute("DELETE FROM network_activity WHERE device_id = %s", (device_id,))

    async def create_user(self, username: str, password_hash: str, role: str = "admin") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        normalized = username.strip().lower()
        with self._connect() as conn:
            try:
                row = conn.execute(
                    """
                    INSERT INTO users(username, role, password_hash, created_at, disabled)
                    VALUES (%s, %s, %s, %s, 0)
                    RETURNING id, username, role, created_at, disabled
                    """,
                    (normalized, role, password_hash, now),
                ).fetchone()
            except Exception as exc:
                raise ValueError("username already exists") from exc
        return dict(row)

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        normalized = username.strip().lower()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = %s", (normalized,)).fetchone()
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT id, username, role, created_at, disabled FROM users WHERE id = %s", (user_id,)).fetchone()
        return dict(row) if row else None

    async def create_user_session(self, user_id: int, session_id: str, refresh_token_hash: str, device_name: str, user_agent: str, ip: str, expires_at: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO user_sessions(user_id, session_id, refresh_token_hash, device_name, user_agent, ip, created_at, last_seen, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, session_id, refresh_token_hash, device_name, user_agent, ip, now, now, expires_at),
            ).fetchone()
        return dict(row)

    async def get_active_session_by_refresh_hash(self, refresh_token_hash: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.*, u.username, u.role, u.disabled
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.refresh_token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > %s AND u.disabled = 0
                """,
                (refresh_token_hash, now),
            ).fetchone()
        return dict(row) if row else None

    async def get_active_session_by_id(self, session_id: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.*, u.username, u.role, u.disabled
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.session_id = %s AND s.revoked_at IS NULL AND s.expires_at > %s AND u.disabled = 0
                """,
                (session_id, now),
            ).fetchone()
        return dict(row) if row else None

    async def touch_session(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE user_sessions SET last_seen = %s WHERE session_id = %s AND revoked_at IS NULL", (now, session_id))

    async def revoke_session(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE user_sessions SET revoked_at = %s WHERE session_id = %s AND revoked_at IS NULL", (now, session_id))

    async def list_user_sessions(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, device_name, user_agent, ip, created_at, last_seen, expires_at, revoked_at
                FROM user_sessions
                WHERE user_id = %s
                ORDER BY last_seen DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def create_password_reset_token(self, user_id: int, reset_token_hash: str, expires_at: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO password_reset_tokens(user_id, token_hash, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                (user_id, reset_token_hash, now, expires_at),
            )

    async def reset_password_with_token(self, reset_token_hash: str, password_hash: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, user_id FROM password_reset_tokens WHERE token_hash = %s AND used_at IS NULL AND expires_at > %s",
                (reset_token_hash, now),
            ).fetchone()
            if not row:
                return False
            user_id = int(row["user_id"])
            conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
            conn.execute("UPDATE password_reset_tokens SET used_at = %s WHERE id = %s", (now, int(row["id"])))
            conn.execute("UPDATE user_sessions SET revoked_at = %s WHERE user_id = %s AND revoked_at IS NULL", (now, user_id))
        return True

    async def log_action(self, device_id: str, action: str, target: str, status: str, details: dict[str, Any]) -> dict[str, Any]:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "device_id": device_id, "action": action, "target": target, "status": status, "details": details}
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO actions(timestamp, device_id, action, target, status, details) VALUES (%s, %s, %s, %s, %s, %s)",
                (record["timestamp"], device_id, action, target, status, json.dumps(details, ensure_ascii=True)),
            )
        return record

    async def list_rows(self, table: str, limit: int = 100, search: str = "", **filters: Any) -> list[dict[str, Any]]:
        allowed = {"devices", "events", "alerts", "processes", "network_activity", "actions", "rules", "settings"}
        if table not in allowed:
            raise ValueError("invalid table")
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(filters.pop("offset", 0)))
        where: list[str] = []
        params: list[Any] = []
        if search:
            where.append("(CAST(details AS TEXT) ILIKE %s OR CAST(device_id AS TEXT) ILIKE %s OR CAST(event_type AS TEXT) ILIKE %s OR CAST(source AS TEXT) ILIKE %s)")
            like = f"%{search}%"
            params.extend([like, like, like, like])
        for key, value in filters.items():
            if value is not None:
                where.append(f"{key} = %s")
                params.append(value)
        query = f"SELECT * FROM {table}"
        if where:
            query += " WHERE " + " AND ".join(where)
        order_col = "key" if table == "settings" else "id"
        query += f" ORDER BY {order_col} DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    async def list_device_rows(self, table: str, device_id: str, limit: int = 100) -> list[dict[str, Any]]:
        allowed = {"events", "alerts", "processes", "network_activity", "actions"}
        if table not in allowed:
            raise ValueError("invalid table")
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table} WHERE device_id = %s ORDER BY id DESC LIMIT %s", (device_id, limit)).fetchall()
        return [dict(row) for row in rows]


    async def store_processes(self, device_id: str, processes: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM processes WHERE device_id = %s", (device_id,))
            for process in processes:
                conn.execute(
                    """
                    INSERT INTO processes(device_id, pid, name, command_line, risk_score, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (device_id, process.get("pid"), process.get("name"), process.get("command_line"), process.get("risk_score", 0), now),
                )

    async def store_network_activity(self, device_id: str, activity: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM network_activity WHERE device_id = %s", (device_id,))
            for item in activity:
                conn.execute(
                    """
                    INSERT INTO network_activity(device_id, ip, port, protocol, direction, risk_score, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (device_id, item.get("ip"), item.get("port"), item.get("protocol"), item.get("direction"), item.get("risk_score", 0), now),
                )

    async def get_setting(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = %s", (key,)).fetchone()
        if not row:
            return None
        return json.loads(row["value"])

    async def set_setting(self, key: str, value: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (%s, %s) ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value",
                (key, json.dumps(value, ensure_ascii=True)),
            )

    async def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            devices = conn.execute("SELECT COUNT(*) AS value FROM devices").fetchone()["value"]
            online = conn.execute("SELECT COUNT(*) AS value FROM devices WHERE status = 'online'").fetchone()["value"]
            alerts = conn.execute("SELECT COUNT(*) AS value FROM alerts").fetchone()["value"]
            events = conn.execute("SELECT COUNT(*) AS value FROM events").fetchone()["value"]
            max_risk = conn.execute("SELECT COALESCE(MAX(risk_score), 0) AS value FROM events").fetchone()["value"]
        return {"threat_score": int(max_risk or 0), "active_alerts": int(alerts or 0), "event_count": int(events or 0), "device_count": int(devices or 0), "online_devices": int(online or 0), "database": "postgres"}

    async def migrate_legacy_databases(self, source_root) -> int:
        return 0
