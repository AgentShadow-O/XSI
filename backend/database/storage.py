from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import DATABASE_PATH, LOG_DIR
from backend.core.log_safety import safe_json
from backend.database.models import UnifiedEvent

logger = logging.getLogger("xsi.storage")


class SiemStorage:
    def __init__(self, db_path: Path = DATABASE_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._ready = False

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Cast path to string for best compatibility across Python/OS versions
            db_str = str(self.db_path)
            conn = sqlite3.connect(
                db_str,
                timeout=30,
                check_same_thread=False
            )

            try:
                conn.execute("PRAGMA busy_timeout=5000")

                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                except sqlite3.OperationalError as e:
                    logger.warning("sqlite_wal_failed module=storage error=%s", e)
                    conn.execute("PRAGMA journal_mode=DELETE")

                self._ensure_schema(conn)
                conn.commit()

            finally:
                conn.close()

            self._ready = True

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                title TEXT NOT NULL,
                details TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                pid INTEGER,
                name TEXT,
                command_line TEXT,
                risk_score INTEGER DEFAULT 0,
                last_seen TEXT
            );
            CREATE TABLE IF NOT EXISTS network_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                ip TEXT,
                port INTEGER,
                protocol TEXT,
                direction TEXT,
                risk_score INTEGER DEFAULT 0,
                last_seen TEXT
            );
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                status TEXT NOT NULL,
                details TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                rule_type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                definition TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT,
                created_at TEXT,
                disabled INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT UNIQUE NOT NULL,
                refresh_token_hash TEXT UNIQUE NOT NULL,
                device_name TEXT,
                user_agent TEXT,
                ip TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_id ON events(id);
            CREATE INDEX IF NOT EXISTS idx_events_risk ON events(risk_score);
            CREATE INDEX IF NOT EXISTS idx_events_device ON events(device_id);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_alerts_id ON alerts(id);
            CREATE INDEX IF NOT EXISTS idx_alerts_risk ON alerts(risk_score);
            CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts(device_id);
            CREATE INDEX IF NOT EXISTS idx_actions_id ON actions(id);
            CREATE INDEX IF NOT EXISTS idx_actions_device ON actions(device_id);
            CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
            CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
            CREATE INDEX IF NOT EXISTS idx_devices_risk ON devices(risk_score);
            CREATE INDEX IF NOT EXISTS idx_device_enrollments_token ON device_enrollments(enrollment_token_hash);
            CREATE INDEX IF NOT EXISTS idx_device_enrollments_device ON device_enrollments(device_id);
            CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_sessions_session ON user_sessions(session_id);
            CREATE INDEX IF NOT EXISTS idx_password_reset_hash ON password_reset_tokens(token_hash);
            CREATE INDEX IF NOT EXISTS idx_processes_device ON processes(device_id);
            CREATE INDEX IF NOT EXISTS idx_network_device ON network_activity(device_id);
            """
        )
        self._ensure_device_columns(conn)
        self._ensure_event_columns(conn)
        self._ensure_user_columns(conn)

    def _ensure_event_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
        columns = {
            "mitre_attack": "TEXT",
            "ioc_matched": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")

    def _ensure_device_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
        columns = {
            "device_name": "TEXT",
            "device_type": "TEXT",
            "os": "TEXT",
            "version": "TEXT",
            "risk_score": "INTEGER NOT NULL DEFAULT 0",
            "health": "TEXT",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
            "agent_version": "TEXT",
            "token_issued_at": "TEXT",
            "token_rotated_at": "TEXT",
            "certificate_fingerprint": "TEXT",
            "metadata": "TEXT",
            "profile": "TEXT",
            "enrollment_status": "TEXT NOT NULL DEFAULT 'registered'",
            "enrolled_at": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE devices ADD COLUMN {name} {definition}")

    def _ensure_user_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        columns = {
            "created_at": "TEXT",
            "disabled": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")

    async def store_event(self, event: UnifiedEvent) -> int:
        return await asyncio.to_thread(self._store_event_sync, event)

    def _store_event_sync(self, event: UnifiedEvent) -> int:
        payload = event.model_dump()
        with self._lock:
            if not self._ready:
                self._initialize_sync()
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                cur = conn.execute(
                    """
                    INSERT INTO events(timestamp, device_id, source, event_type, severity, risk_score, mitre_attack, ioc_matched, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["timestamp"],
                        payload["device_id"],
                        payload["source"],
                        payload["event_type"],
                        payload["severity"],
                        payload["risk_score"],
                        json.dumps(payload.get("mitre_attack") or [], ensure_ascii=True),
                        json.dumps(payload.get("ioc_matched") or [], ensure_ascii=True),
                        json.dumps(payload["details"], ensure_ascii=True),
                    ),
                )
                event_id = int(cur.lastrowid)
                if event.risk_score >= 50 or event.severity in {"warning", "critical"}:
                    conn.execute(
                        """
                        INSERT INTO alerts(event_id, timestamp, device_id, severity, risk_score, title, details)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            event.timestamp,
                            event.device_id,
                            event.severity,
                            event.risk_score,
                            f"{event.source}:{event.event_type}",
                            json.dumps(event.details, ensure_ascii=True),
                        ),
                    )
                self._index_event(conn, event)
                conn.commit()
        self._append_jsonl(LOG_DIR / "events.jsonl", payload)
        return event_id

    def _index_event(self, conn: sqlite3.Connection, event: UnifiedEvent) -> None:
        details = event.details
        pid = int(details.get("pid") or 0)
        process = str(details.get("process_name") or details.get("process") or "")
        if pid or process:
            conn.execute(
                """
                INSERT INTO processes(device_id, pid, name, command_line, risk_score, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event.device_id, pid, process, str(details.get("command_line") or details.get("cmdline") or ""), event.risk_score, event.timestamp),
            )
        ip = str(details.get("ip") or details.get("remote_ip") or "")
        if ip:
            conn.execute(
                """
                INSERT INTO network_activity(device_id, ip, port, protocol, direction, risk_score, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event.device_id, ip, int(details.get("port") or 0), str(details.get("protocol") or ""), str(details.get("direction") or ""), event.risk_score, event.timestamp),
            )

    async def register_device(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        os_name: str,
        version: str,
        hostname: str,
        platform: str,
        token_hash: str,
        metadata: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        certificate_fingerprint: str = "",
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._register_device_sync,
            device_id,
            device_name,
            device_type,
            os_name,
            version,
            hostname,
            platform,
            token_hash,
            metadata or {},
            profile or {},
            certificate_fingerprint,
        )

    def _register_device_sync(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        os_name: str,
        version: str,
        hostname: str,
        platform: str,
        token_hash: str,
        metadata: dict[str, Any],
        profile: dict[str, Any],
        certificate_fingerprint: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            before = conn.execute("SELECT status FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO devices(device_id, device_name, device_type, os, version, hostname, platform, token_hash, status, last_seen, created_at, updated_at, risk_score, token_issued_at, certificate_fingerprint, metadata, profile, enrollment_status, enrolled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, 0, ?, ?, ?, ?, 'registered', ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    device_name=excluded.device_name,
                    device_type=excluded.device_type,
                    os=excluded.os,
                    version=excluded.version,
                    hostname=excluded.hostname,
                    platform=excluded.platform,
                    token_hash=excluded.token_hash,
                    status='online',
                    last_seen=excluded.last_seen,
                    updated_at=excluded.updated_at,
                    certificate_fingerprint=COALESCE(NULLIF(excluded.certificate_fingerprint, ''), devices.certificate_fingerprint),
                    metadata=excluded.metadata,
                    profile=excluded.profile,
                    enrollment_status='registered',
                    enrolled_at=COALESCE(devices.enrolled_at, excluded.enrolled_at)
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
                    json.dumps(metadata, ensure_ascii=True),
                    json.dumps(profile, ensure_ascii=True),
                    now,
                ),
            )
            conn.commit()
        return {"device_id": device_id, "previous_status": before[0] if before else "", "status": "online", "last_seen": now}

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
        return await asyncio.to_thread(
            self._create_device_enrollment_sync,
            enrollment_token_hash,
            device_id,
            device_name,
            device_type,
            os_name,
            hostname,
            platform,
            version,
            metadata,
            profile,
            certificate,
            certificate_fingerprint,
        )

    def _create_device_enrollment_sync(
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
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO device_enrollments(enrollment_token_hash, device_id, device_name, device_type, os, hostname, platform, version, metadata, profile, certificate, certificate_fingerprint, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
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
            )
            conn.commit()
            row = conn.execute("SELECT * FROM device_enrollments WHERE device_id = ?", (device_id,)).fetchone()
            return dict(row)

    async def get_pending_enrollment_by_token_hash(self, enrollment_token_hash: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_pending_enrollment_by_token_hash_sync, enrollment_token_hash)

    def _get_pending_enrollment_by_token_hash_sync(self, enrollment_token_hash: str) -> dict[str, Any] | None:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM device_enrollments WHERE enrollment_token_hash = ? AND status = 'pending'", (enrollment_token_hash,)).fetchone()
            return dict(row) if row else None

    async def complete_device_enrollment(self, enrollment_token_hash: str, device_id: str) -> None:
        await asyncio.to_thread(self._complete_device_enrollment_sync, enrollment_token_hash, device_id)

    def _complete_device_enrollment_sync(self, enrollment_token_hash: str, device_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE device_enrollments SET status = 'completed', completed_at = ? WHERE enrollment_token_hash = ? AND device_id = ?",
                (now, enrollment_token_hash, device_id),
            )
            conn.commit()

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_device_sync, device_id)

    def _get_device_sync(self, device_id: str) -> dict[str, Any] | None:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            return dict(row) if row else None

    async def heartbeat(self, device_id: str, status: str, health: dict[str, Any] | None = None, agent_version: str = "") -> dict[str, Any]:
        return await asyncio.to_thread(self._heartbeat_sync, device_id, status, health or {}, agent_version)

    def _heartbeat_sync(self, device_id: str, status: str, health: dict[str, Any], agent_version: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        normalized_status = "online" if status.lower() in {"alive", "online", "ok"} else status.lower()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            before = conn.execute("SELECT status FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            conn.execute(
                "UPDATE devices SET status = ?, last_seen = ?, updated_at = ?, health = ?, agent_version = ? WHERE device_id = ?",
                (normalized_status, now, now, json.dumps(health, ensure_ascii=True), agent_version, device_id),
            )
            if conn.total_changes == 0:
                conn.execute(
                    "INSERT INTO devices(device_id, device_name, device_type, os, version, status, last_seen, created_at, updated_at, health, agent_version, risk_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                    (device_id, device_id, "unknown", "", agent_version, normalized_status, now, now, now, json.dumps(health, ensure_ascii=True), agent_version),
                )
            conn.commit()
        return {"device_id": device_id, "previous_status": before[0] if before else "", "status": normalized_status, "last_seen": now}

    async def remove_device(self, device_id: str) -> None:
        await asyncio.to_thread(self._remove_device_sync, device_id)

    def _remove_device_sync(self, device_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute("UPDATE devices SET status = 'removed', token_hash = '', token_rotated_at = ?, updated_at = ? WHERE device_id = ?", (now, now, device_id))
            conn.execute("DELETE FROM processes WHERE device_id = ?", (device_id,))
            conn.execute("DELETE FROM network_activity WHERE device_id = ?", (device_id,))
            conn.commit()

    async def mark_offline_stale(self, timeout_seconds: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._mark_offline_stale_sync, timeout_seconds)

    def _mark_offline_stale_sync(self, timeout_seconds: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        changed: list[dict[str, Any]] = []
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            rows = conn.execute("SELECT device_id, status, last_seen FROM devices WHERE status != 'offline'").fetchall()
            for row in rows:
                last_seen_raw = str(row["last_seen"] or "")
                try:
                    last_seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    last_seen = datetime.fromtimestamp(0, tz=timezone.utc)
                if (now - last_seen).total_seconds() > timeout_seconds:
                    conn.execute("UPDATE devices SET status = 'offline' WHERE device_id = ?", (row["device_id"],))
                    changed.append({"device_id": row["device_id"], "previous_status": row["status"], "status": "offline", "last_seen": last_seen_raw})
            conn.commit()
        return changed

    async def rotate_device_token(self, device_id: str, new_token_hash: str) -> None:
        await asyncio.to_thread(self._rotate_device_token_sync, device_id, new_token_hash)

    def _rotate_device_token_sync(self, device_id: str, new_token_hash: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute("UPDATE devices SET token_hash = ?, token_rotated_at = ?, updated_at = ? WHERE device_id = ?", (new_token_hash, now, now, device_id))
            conn.commit()

    async def create_user(self, username: str, password_hash: str, role: str = "admin") -> dict[str, Any]:
        return await asyncio.to_thread(self._create_user_sync, username, password_hash, role)

    def _create_user_sync(self, username: str, password_hash: str, role: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        normalized = username.strip().lower()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            try:
                cur = conn.execute(
                    "INSERT INTO users(username, role, password_hash, created_at, disabled) VALUES (?, ?, ?, ?, 0)",
                    (normalized, role, password_hash, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("username already exists") from exc
            conn.commit()
            return dict(conn.execute("SELECT id, username, role, created_at, disabled FROM users WHERE id = ?", (int(cur.lastrowid),)).fetchone())

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_user_by_username_sync, username)

    def _get_user_by_username_sync(self, username: str) -> dict[str, Any] | None:
        normalized = username.strip().lower()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM users WHERE username = ?", (normalized,)).fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_user_by_id_sync, user_id)

    def _get_user_by_id_sync(self, user_id: int) -> dict[str, Any] | None:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute("SELECT id, username, role, created_at, disabled FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    async def create_user_session(
        self,
        user_id: int,
        session_id: str,
        refresh_token_hash: str,
        device_name: str,
        user_agent: str,
        ip: str,
        expires_at: str,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_user_session_sync, user_id, session_id, refresh_token_hash, device_name, user_agent, ip, expires_at)

    def _create_user_session_sync(self, user_id: int, session_id: str, refresh_token_hash: str, device_name: str, user_agent: str, ip: str, expires_at: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            cur = conn.execute(
                """
                INSERT INTO user_sessions(user_id, session_id, refresh_token_hash, device_name, user_agent, ip, created_at, last_seen, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, refresh_token_hash, device_name, user_agent, ip, now, now, expires_at),
            )
            conn.commit()
            return dict(conn.execute("SELECT * FROM user_sessions WHERE id = ?", (int(cur.lastrowid),)).fetchone())

    async def get_active_session_by_refresh_hash(self, refresh_token_hash: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_active_session_by_refresh_hash_sync, refresh_token_hash)

    def _get_active_session_by_refresh_hash_sync(self, refresh_token_hash: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute(
                """
                SELECT s.*, u.username, u.role, u.disabled
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.refresh_token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ? AND u.disabled = 0
                """,
                (refresh_token_hash, now),
            ).fetchone()
            return dict(row) if row else None

    async def get_active_session_by_id(self, session_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_active_session_by_id_sync, session_id)

    def _get_active_session_by_id_sync(self, session_id: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute(
                """
                SELECT s.*, u.username, u.role, u.disabled
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.session_id = ? AND s.revoked_at IS NULL AND s.expires_at > ? AND u.disabled = 0
                """,
                (session_id, now),
            ).fetchone()
            return dict(row) if row else None

    async def touch_session(self, session_id: str) -> None:
        await asyncio.to_thread(self._touch_session_sync, session_id)

    def _touch_session_sync(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute("UPDATE user_sessions SET last_seen = ? WHERE session_id = ? AND revoked_at IS NULL", (now, session_id))
            conn.commit()

    async def revoke_session(self, session_id: str) -> None:
        await asyncio.to_thread(self._revoke_session_sync, session_id)

    def _revoke_session_sync(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE session_id = ? AND revoked_at IS NULL", (now, session_id))
            conn.commit()

    async def list_user_sessions(self, user_id: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_user_sessions_sync, user_id)

    def _list_user_sessions_sync(self, user_id: int) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT session_id, device_name, user_agent, ip, created_at, last_seen, expires_at, revoked_at
                FROM user_sessions
                WHERE user_id = ?
                ORDER BY last_seen DESC
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    async def create_password_reset_token(self, user_id: int, reset_token_hash: str, expires_at: str) -> None:
        await asyncio.to_thread(self._create_password_reset_token_sync, user_id, reset_token_hash, expires_at)

    def _create_password_reset_token_sync(self, user_id: int, reset_token_hash: str, expires_at: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute(
                "INSERT INTO password_reset_tokens(user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (user_id, reset_token_hash, now, expires_at),
            )
            conn.commit()

    async def reset_password_with_token(self, reset_token_hash: str, password_hash: str) -> bool:
        return await asyncio.to_thread(self._reset_password_with_token_sync, reset_token_hash, password_hash)

    def _reset_password_with_token_sync(self, reset_token_hash: str, password_hash: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT id, user_id FROM password_reset_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                (reset_token_hash, now),
            ).fetchone()
            if not row:
                return False
            user_id = int(row[1])
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?", (now, int(row[0])))
            conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id))
            conn.commit()
            return True

    async def log_action(self, device_id: str, action: str, target: str, status: str, details: dict[str, Any]) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id,
            "action": action,
            "target": target,
            "status": status,
            "details": details,
        }
        await asyncio.to_thread(self._log_action_sync, record)
        return record

    def _log_action_sync(self, record: dict[str, Any]) -> None:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute(
                "INSERT INTO actions(timestamp, device_id, action, target, status, details) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record["timestamp"],
                    record["device_id"],
                    record["action"],
                    record["target"],
                    record["status"],
                    json.dumps(record["details"], ensure_ascii=True),
                ),
            )
            conn.commit()
        self._append_jsonl(LOG_DIR / "actions.jsonl", record)

    async def store_processes(self, device_id: str, processes: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(self._store_processes_sync, device_id, processes)

    def _store_processes_sync(self, device_id: str, processes: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            # Clear old processes for this device to keep it a snapshot? 
            # Or just append? Usually snapshots are better for 'running processes'.
            conn.execute("DELETE FROM processes WHERE device_id = ?", (device_id,))
            for p in processes:
                conn.execute(
                    """
                    INSERT INTO processes(device_id, pid, name, command_line, risk_score, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (device_id, p.get("pid"), p.get("name"), p.get("command_line"), p.get("risk_score", 0), now),
                )
            conn.commit()

    async def store_network_activity(self, device_id: str, activity: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(self._store_network_activity_sync, device_id, activity)

    def _store_network_activity_sync(self, device_id: str, activity: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute("DELETE FROM network_activity WHERE device_id = ?", (device_id,))
            for a in activity:
                conn.execute(
                    """
                    INSERT INTO network_activity(device_id, ip, port, protocol, direction, risk_score, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (device_id, a.get("ip"), a.get("port"), a.get("protocol"), a.get("direction"), a.get("risk_score", 0), now),
                )
            conn.commit()

    async def list_rows(self, table: str, limit: int = 100, search: str = "", **filters: Any) -> list[dict[str, Any]]:
        allowed = {"devices", "events", "alerts", "processes", "network_activity", "actions", "rules", "settings"}
        if table not in allowed:
            raise ValueError("invalid table")
        return await asyncio.to_thread(self._list_rows_sync, table, limit, search, **filters)

    async def list_device_rows(self, table: str, device_id: str, limit: int = 100) -> list[dict[str, Any]]:
        allowed = {"events", "alerts", "processes", "network_activity", "actions"}
        if table not in allowed:
            raise ValueError("invalid table")
        return await asyncio.to_thread(self._list_device_rows_sync, table, device_id, limit)

    def _list_device_rows_sync(self, table: str, device_id: str, limit: int) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            rows = conn.execute(f"SELECT * FROM {table} WHERE device_id = ? ORDER BY id DESC LIMIT ?", (device_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def _list_rows_sync(self, table: str, limit: int, search: str, **filters: Any) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(filters.pop("offset", 0)))
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            
            query = f"SELECT * FROM {table}"
            params: list[Any] = []
            where_clauses: list[str] = []

            if search:
                where_clauses.append("(CAST(details AS TEXT) LIKE ? OR CAST(device_id AS TEXT) LIKE ? OR CAST(event_type AS TEXT) LIKE ? OR CAST(source AS TEXT) LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
            
            for key, value in filters.items():
                if value is not None:
                    where_clauses.append(f"{key} = ?")
                    params.append(value)
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            order_col = "id" if table != "settings" else "key"
            query += f" ORDER BY {order_col} DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    async def get_setting(self, key: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_setting_sync, key)

    def _get_setting_sync(self, key: str) -> dict[str, Any] | None:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return json.loads(row[0])
            return None

    async def set_setting(self, key: str, value: dict[str, Any]) -> None:
        await asyncio.to_thread(self._set_setting_sync, key, value)

    def _set_setting_sync(self, key: str, value: dict[str, Any]) -> None:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(value)))
            conn.commit()

    async def summary(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._summary_sync)

    def _summary_sync(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            devices = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
            online = conn.execute("SELECT COUNT(*) FROM devices WHERE status = 'online'").fetchone()[0]
            alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            max_risk = conn.execute("SELECT COALESCE(MAX(risk_score), 0) FROM events").fetchone()[0]
            active_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE risk_score >= 50").fetchone()[0]
        return {
            "threat_score": int(max_risk or 0),
            "active_alerts": int(active_alerts or 0),
            "event_count": int(events or 0),
            "device_count": int(devices or 0),
            "online_devices": int(online or 0),
            "database": str(self.db_path),
        }

    async def migrate_legacy_databases(self, source_root: Path) -> int:
        return await asyncio.to_thread(self._migrate_legacy_databases_sync, source_root)

    def _migrate_legacy_databases_sync(self, source_root: Path) -> int:
        with self._lock, sqlite3.connect(self.db_path, timeout=30) as conn:
            self._ensure_schema(conn)
            migrated = conn.execute(
                "SELECT value FROM settings WHERE key = 'legacy_migration_complete'"
            ).fetchone()
            if migrated:
                return 0

            count = 0
            count += self._migrate_ids_alerts(conn, source_root / "IDS" / "alerts.db")
            count += self._migrate_ids_message_alerts(conn, source_root / "IDS" / "ids_alerts.db")
            count += self._migrate_edr_structured(conn, source_root / "EDR" / "logs" / "edr.db")
            count += self._migrate_edr_structured(conn, source_root / "EDR" / "WEB" / "backend" / "logs" / "edr.db")
            conn.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES ('legacy_migration_complete', ?)",
                (json.dumps({"rows": count, "timestamp": datetime.now(timezone.utc).isoformat()}),),
            )
            conn.commit()
            return count

    def _insert_legacy_event(
        self,
        conn: sqlite3.Connection,
        *,
        timestamp: str,
        device_id: str,
        source: str,
        event_type: str,
        severity: str,
        risk_score: int,
        details: dict[str, Any],
        mitre_attack: list[str] | None = None,
        ioc_matched: list[str] | None = None,
    ) -> None:
        cur = conn.execute(
            """
            INSERT INTO events(timestamp, device_id, source, event_type, severity, risk_score, mitre_attack, ioc_matched, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                device_id,
                source,
                event_type,
                severity,
                risk_score,
                json.dumps(mitre_attack or [], ensure_ascii=True),
                json.dumps(ioc_matched or [], ensure_ascii=True),
                json.dumps(details, ensure_ascii=True),
            ),
        )
        if risk_score >= 50 or severity in {"warning", "critical"}:
            conn.execute(
                """
                INSERT INTO alerts(event_id, timestamp, device_id, severity, risk_score, title, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (int(cur.lastrowid), timestamp, device_id, severity, risk_score, f"{source}:{event_type}", json.dumps(details, ensure_ascii=True)),
            )

    def _migrate_ids_alerts(self, conn: sqlite3.Connection, path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        with sqlite3.connect(path) as src:
            for row in src.execute("SELECT timestamp, alert_type, confidence FROM alerts"):
                confidence = int(float(row[2] or 0))
                severity = "critical" if confidence >= 80 else "warning" if confidence >= 50 else "safe"
                self._insert_legacy_event(
                    conn,
                    timestamp=str(row[0] or ""),
                    device_id="legacy-ids",
                    source="ids",
                    event_type=str(row[1] or "IDS_ALERT").upper(),
                    severity=severity,
                    risk_score=max(0, min(100, confidence)),
                    details={"legacy_source": str(path), "confidence": row[2]},
                )
                count += 1
        return count

    def _migrate_ids_message_alerts(self, conn: sqlite3.Connection, path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        with sqlite3.connect(path) as src:
            for row in src.execute("SELECT timestamp, message FROM alerts"):
                message = str(row[1] or "")
                self._insert_legacy_event(
                    conn,
                    timestamp=str(row[0] or ""),
                    device_id="legacy-ids",
                    source="ids",
                    event_type="IDS_ALERT",
                    severity="warning",
                    risk_score=50,
                    details={"legacy_source": str(path), "message": message},
                )
                count += 1
        return count

    def _migrate_edr_structured(self, conn: sqlite3.Connection, path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        with sqlite3.connect(path) as src:
            tables = {row[0] for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("events", "alerts"):
                if table not in tables:
                    continue
                for row in src.execute(f"SELECT time, type, severity, details FROM {table}"):
                    try:
                        details = json.loads(row[3] or "{}")
                    except json.JSONDecodeError:
                        details = {"raw": row[3]}
                    if not isinstance(details, dict):
                        details = {"value": details}
                    details["legacy_source"] = str(path)
                    score = int(details.get("risk_score") or details.get("behavior_score") or (80 if row[2] == "critical" else 50 if row[2] == "warning" else 0))
                    self._insert_legacy_event(
                        conn,
                        timestamp=str(row[0] or ""),
                        device_id=str(details.get("agent_id") or details.get("device_id") or "legacy-edr"),
                        source="edr",
                        event_type=str(row[1] or "EDR_EVENT").upper(),
                        severity=str(row[2] or "safe").lower(),
                        risk_score=max(0, min(100, score)),
                        details=details,
                    )
                    count += 1
            if "actions" in tables:
                for row in src.execute("SELECT time, type, severity, details FROM actions"):
                    try:
                        details = json.loads(row[3] or "{}")
                    except json.JSONDecodeError:
                        details = {"raw": row[3]}
                    conn.execute(
                        "INSERT INTO actions(timestamp, device_id, action, target, status, details) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            str(row[0] or ""),
                            str(details.get("agent_id") or details.get("device_id") or "legacy-edr"),
                            str(details.get("action") or row[1] or "ACTION"),
                            str(details.get("target") or ""),
                            str(details.get("status") or "legacy"),
                            json.dumps({"legacy_source": str(path), **details}, ensure_ascii=True),
                        ),
                    )
                    count += 1
        return count

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(safe_json(payload) + "\n")


def backup_legacy_databases(source_root: Path, backup_dir: Path) -> list[Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backed_up: list[Path] = []
    for candidate in (
        source_root / "IDS" / "alerts.db",
        source_root / "IDS" / "ids_alerts.db",
        source_root / "EDR" / "logs" / "edr.db",
        source_root / "EDR" / "WEB" / "backend" / "logs" / "edr.db",
    ):
        if not candidate.exists():
            continue
        target = backup_dir / candidate.name
        if target.exists():
            backed_up.append(target)
            continue
        shutil.copy2(candidate, target)
        backed_up.append(target)
    return backed_up
