from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.agents.registration import token_hash
from backend.core.engine import XSIEngine
from backend.database.storage import SiemStorage
from backend.main import create_app


class DeviceLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "xsi-test.db"
        self.engine = XSIEngine()
        self.engine.storage = SiemStorage(self.db_path)
        await self.engine.start()

    async def asyncTearDown(self) -> None:
        await self.engine.stop()
        self.temp_dir.cleanup()

    async def test_device_online_offline_recovery(self) -> None:
        await self.engine.register_device(
            "desktop-1",
            "Desktop-PC",
            "desktop",
            "Windows",
            "0.2.0",
            "Desktop-PC",
            "Windows-11",
            "agent-token",
        )
        devices = await self.engine.storage.list_rows("devices", 10)
        self.assertEqual(devices[0]["status"], "online")

        await self.engine.heartbeat("desktop-1", "alive", {"cpu": 1}, "0.2.0")
        changed = await self.engine.storage.mark_offline_stale(0)
        self.assertEqual(changed[0]["status"], "offline")

        await self.engine.heartbeat("desktop-1", "alive", {"cpu": 2}, "0.2.0")
        devices = await self.engine.storage.list_rows("devices", 10)
        self.assertEqual(devices[0]["status"], "online")

    async def test_event_persistence_and_command_queue(self) -> None:
        await self.engine.queue_command("desktop-1", {"command": "scan"})
        command = await self.engine.next_command("desktop-1")
        self.assertEqual(command["command"], "scan")

        event = await self.engine.ingest(
            {
                "device_id": "desktop-1",
                "source": "edr",
                "event_type": "PROCESS",
                "risk_score": 75,
                "details": {"process_name": "powershell.exe", "cmdline": "powershell -enc test"},
            }
        )
        self.assertGreaterEqual(event.risk_score, 75)
        rows = await self.engine.storage.list_rows("events", 5)
        self.assertTrue(rows)


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "xsi-api-test.db"
        self.engine = XSIEngine()
        self.engine.storage = SiemStorage(self.db_path)
        self.app = create_app(self.engine, run_legacy_migration=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_mobile_login_and_status(self) -> None:
        with TestClient(self.app) as client:
            login = client.post("/api/mobile/login", json={"api_key": "change-me-xsi-api-key"})
            self.assertEqual(login.status_code, 200)
            token = login.json()["access_token"]
            status = client.get("/api/mobile/status", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(status.status_code, 200)

    def test_user_auth_lifecycle(self) -> None:
        with TestClient(self.app) as client:
            registered = client.post(
                "/api/auth/register",
                json={"username": "soc-admin", "password": "correct-horse-1", "device_name": "browser-a"},
            )
            self.assertEqual(registered.status_code, 200)
            body = registered.json()
            self.assertEqual(body["user"]["username"], "soc-admin")
            self.assertIn("access_token", body)
            self.assertIn("refresh_token", body)

            duplicate = client.post(
                "/api/auth/register",
                json={"username": "soc-admin", "password": "correct-horse-1"},
            )
            self.assertEqual(duplicate.status_code, 409)

            login = client.post(
                "/api/auth/login",
                json={"username": "soc-admin", "password": "correct-horse-1", "device_name": "browser-b"},
            )
            self.assertEqual(login.status_code, 200)
            access_token = login.json()["access_token"]
            refresh_token = login.json()["refresh_token"]

            me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["user"]["role"], "admin")

            refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
            self.assertEqual(refreshed.status_code, 200)
            self.assertIn("access_token", refreshed.json())

            sessions = client.get("/api/auth/sessions", headers={"Authorization": f"Bearer {access_token}"})
            self.assertEqual(sessions.status_code, 200)
            self.assertGreaterEqual(len(sessions.json()["items"]), 1)

            logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
            self.assertEqual(logout.status_code, 200)
            after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
            self.assertEqual(after_logout.status_code, 401)

    def test_password_reset_invalidates_sessions(self) -> None:
        with TestClient(self.app) as client:
            registered = client.post(
                "/api/auth/register",
                json={"username": "reset-user", "password": "initial-pass-1", "device_name": "browser"},
            )
            self.assertEqual(registered.status_code, 200)
            access_token = registered.json()["access_token"]

            reset = client.post("/api/auth/password-reset/request", json={"username": "reset-user"})
            self.assertEqual(reset.status_code, 200)
            reset_token = reset.json()["reset_token"]

            confirmed = client.post(
                "/api/auth/password-reset/confirm",
                json={"reset_token": reset_token, "new_password": "replacement-pass-1"},
            )
            self.assertEqual(confirmed.status_code, 200)

            old_session = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
            self.assertEqual(old_session.status_code, 401)

            old_login = client.post(
                "/api/auth/login",
                json={"username": "reset-user", "password": "initial-pass-1"},
            )
            self.assertEqual(old_login.status_code, 401)

            new_login = client.post(
                "/api/auth/login",
                json={"username": "reset-user", "password": "replacement-pass-1"},
            )
            self.assertEqual(new_login.status_code, 200)

    def test_agent_register_heartbeat_command(self) -> None:
        with TestClient(self.app) as client:
            import hmac, hashlib
            from datetime import datetime, timezone
            ts = datetime.now(timezone.utc).isoformat()
            sig = hmac.new(b"change-me-xsi-agent-token", ("api-desktop-1" + ts).encode(), hashlib.sha256).hexdigest()
            payload = {
                "device_id": "api-desktop-1",
                "device_name": "Desktop-PC",
                "device_type": "desktop",
                "os": "Windows",
                "version": "0.2.0",
                "hostname": "Desktop-PC",
                "platform": "Windows-11",
                "token": "change-me-xsi-agent-token",
                "timestamp": ts,
                "signature": sig
            }
            self.assertEqual(client.post("/api/agents/register", json=payload).status_code, 200)
            beat = {
                "device_id": "api-desktop-1",
                "status": "alive",
                "health": {"cpu": 4},
                "agent_version": "0.2.0",
                "token": "change-me-xsi-agent-token",
            }
            import json
            ts2 = datetime.now(timezone.utc).isoformat()
            body = json.dumps(beat)
            sig2 = hmac.new(b"change-me-xsi-agent-token", (ts2 + body).encode(), hashlib.sha256).hexdigest()
            headers = {
                "Authorization": "Bearer change-me-xsi-agent-token",
                "X-Agent-Signature": sig2,
                "X-Agent-Timestamp": ts2,
                "X-Device-Id": "api-desktop-1",
                "Content-Type": "application/json"
            }
            self.assertEqual(client.post("/api/agents/heartbeat", data=body, headers=headers).status_code, 200)
            queued = client.post(
                "/api/agents/command",
                headers={"x-api-key": "change-me-xsi-api-key"},
                json={"device_id": "api-desktop-1", "command": "scan", "details": {}},
            )
            self.assertEqual(queued.status_code, 200)
            command = client.get(
                "/api/agents/api-desktop-1/commands",
                params={"token": "change-me-xsi-agent-token"},
            )
            self.assertEqual(command.status_code, 200)
            self.assertEqual(command.json()["command"]["command"], "scan")

    def test_agent_process_and_network_telemetry(self) -> None:
        with TestClient(self.app) as client:
            import hashlib
            import hmac
            import json
            from datetime import datetime, timezone

            ts = datetime.now(timezone.utc).isoformat()
            sig = hmac.new(b"change-me-xsi-agent-token", ("telemetry-desktop" + ts).encode(), hashlib.sha256).hexdigest()
            self.assertEqual(
                client.post(
                    "/api/agents/register",
                    json={
                        "device_id": "telemetry-desktop",
                        "device_name": "Telemetry",
                        "device_type": "desktop",
                        "os": "Windows",
                        "version": "0.4.0",
                        "agent_version": "0.4.0",
                        "hostname": "Telemetry",
                        "platform": "Windows-11",
                        "token": "change-me-xsi-agent-token",
                        "timestamp": ts,
                        "signature": sig,
                    },
                ).status_code,
                200,
            )

            def signed_post(path: str, payload: dict[str, object]) -> int:
                timestamp = datetime.now(timezone.utc).isoformat()
                body = json.dumps(payload, separators=(",", ":"))
                signature = hmac.new(b"change-me-xsi-agent-token", (timestamp + body).encode(), hashlib.sha256).hexdigest()
                return client.post(
                    path,
                    data=body,
                    headers={
                        "Authorization": "Bearer change-me-xsi-agent-token",
                        "X-Agent-Signature": signature,
                        "X-Agent-Timestamp": timestamp,
                        "X-Device-Id": "telemetry-desktop",
                        "Content-Type": "application/json",
                    },
                ).status_code

            process_payload = {
                "device_id": "telemetry-desktop",
                "token": "change-me-xsi-agent-token",
                "processes": [{"pid": 1, "name": "system", "command_line": "system"}],
            }
            network_payload = {
                "device_id": "telemetry-desktop",
                "token": "change-me-xsi-agent-token",
                "activity": [{"ip": "127.0.0.1", "port": 8000, "protocol": "TCP", "direction": "outbound"}],
            }
            self.assertEqual(signed_post("/api/agents/processes", process_payload), 200)
            self.assertEqual(signed_post("/api/agents/network", network_payload), 200)

    def test_agent_registration_rejects_missing_signature(self) -> None:
        with TestClient(self.app) as client:
            response = client.post(
                "/api/agents/register",
                json={
                    "device_id": "unsigned-desktop",
                    "device_name": "Unsigned",
                    "hostname": "Unsigned",
                    "platform": "Windows-11",
                    "agent_version": "0.4.0",
                    "token": "change-me-xsi-agent-token",
                },
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"]["error"], "Missing signature")

    def test_python_agent_registration_payload_is_signed(self) -> None:
        import hashlib
        import hmac

        from backend.agents.common.api_client import XSIApiClient

        captured: dict[str, object] = {}

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, str]:
                return {"device_id": "xsi-dev", "session_token": "change-me-xsi-agent-token"}

        class FakeSession:
            def post(self, url: str, data: bytes, headers: dict[str, str], timeout: int) -> FakeResponse:
                captured.update({"url": url, "data": data, "headers": headers, "timeout": timeout})
                return FakeResponse()

        client = XSIApiClient("http://controller", "change-me-xsi-agent-token", "xsi-dev")
        client.session = FakeSession()  # type: ignore[assignment]
        client.register("dev", "Windows", "Windows-11", "0.4.0")

        import json

        payload = json.loads(captured["data"])
        expected = hmac.new(
            b"change-me-xsi-agent-token",
            (payload["device_id"] + payload["timestamp"]).encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(payload["device_id"], "xsi-dev")
        self.assertEqual(payload["hostname"], "dev")
        self.assertEqual(payload["agent_version"], "0.4.0")
        self.assertEqual(payload["signature"], expected)

    def test_device_enrollment_flow(self) -> None:
        with TestClient(self.app) as client:
            enrollment = client.post(
                "/api/devices/enroll",
                headers={"x-api-key": "change-me-xsi-api-key"},
                json={
                    "device_name": "Workstation 01",
                    "device_type": "desktop",
                    "os": "Windows",
                    "metadata": {"owner": "soc"},
                    "profile": {"site": "lab"},
                },
            )
            self.assertEqual(enrollment.status_code, 200)
            body = enrollment.json()
            self.assertIn("certificate", body)
            completed = client.post(
                "/api/devices/enroll/complete",
                json={"enrollment_token": body["enrollment_token"], "hostname": "WS01", "platform": "Windows-11"},
            )
            self.assertEqual(completed.status_code, 200)
            detail = client.get(f"/api/devices/{body['device_id']}")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["device"]["device_id"], body["device_id"])
            center = client.get(f"/api/devices/{body['device_id']}/command-center")
            self.assertEqual(center.status_code, 200)
            self.assertEqual(center.json()["device"]["device_id"], body["device_id"])
            for key in ("alerts", "processes", "network", "logs", "xdr", "ips"):
                self.assertTrue(all(item.get("device_id") == body["device_id"] for item in center.json()[key]))

    def test_agent_deployment_info(self) -> None:
        with TestClient(self.app) as client:
            resp = client.get("/api/agents/deployment/info")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("windows", data)
            self.assertIn("android", data)
            self.assertEqual(data["windows"]["version"], "0.4.0")
            self.assertEqual(data["android"]["version"], "0.4.0")


if __name__ == "__main__":
    unittest.main()
