import unittest
import asyncio
import json
import time
from backend.core.engine import XSIEngine
from backend.database.models import UnifiedEvent
from backend.detection.rule_engine import RuleEngine
from backend.detection.correlation import CorrelationEngine
from backend.prevention.ips.blocker import PreventionEngine

class TestPhases10to14(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = XSIEngine()
        await self.engine.start()

    async def asyncTearDown(self):
        await self.engine.stop()

    async def test_siem_log_ingestion_and_normalized_format(self):
        event_data = {
            "device_id": "test-device",
            "source": "edr",
            "event_type": "PROCESS",
            "severity": "warning",
            "details": {"pid": 1234, "process_name": "malware.exe"}
        }
        event = await self.engine.ingest(event_data)
        self.assertEqual(event.device_id, "test-device")
        self.assertEqual(event.event_type, "PROCESS")
        self.assertEqual(event.severity, "warning")
        self.assertIn("pid", event.details)

    async def test_siem_mitre_and_ioc_mapping(self):
        # IOC Match
        event_data = {
            "device_id": "test-device",
            "source": "network",
            "event_type": "CONNECTION",
            "details": {"remote_ip": "1.2.3.4"}
        }
        event = await self.engine.ingest(event_data)
        self.assertIn("ioc_match", event.details.get("tags", []))
        self.assertIn("ip:1.2.3.4", event.ioc_matched)
        self.assertGreaterEqual(event.risk_score, 90)

        # MITRE Mapping
        event_data = {
            "device_id": "test-device",
            "source": "ids",
            "event_type": "PORT_SCAN",
            "details": {"ip": "10.0.0.5"}
        }
        event = await self.engine.ingest(event_data)
        self.assertIn("T1595.001", event.mitre_attack)

    async def test_xdr_suspicious_activity_detection(self):
        # Masquerading
        event_data = {
            "device_id": "test-device",
            "source": "edr",
            "event_type": "PROCESS",
            "details": {"process_name": "svchost.exe", "command_line": "C:\\Users\\Public\\svchost.exe"}
        }
        event = await self.engine.ingest(event_data)
        self.assertIn("masquerading", event.details.get("tags", []))
        self.assertIn("T1036", event.mitre_attack)
        self.assertGreaterEqual(event.risk_score, 85)

    async def test_ips_automated_prevention(self):
        # Suspicious domain -> block_host
        event_data = {
            "device_id": "test-device",
            "source": "edr",
            "event_type": "NETWORK",
            "risk_score": 75,
            "details": {"domain": "malicious-site.com"}
        }
        # We need to make sure the risk score stays high enough for prevention
        # RuleEngine might override it, so let's use an IOC domain
        event_data = {
            "device_id": "test-device",
            "source": "edr",
            "event_type": "NETWORK",
            "details": {"domain": "malicious-site.com"}
        }
        event = await self.engine.ingest(event_data)
        
        # Check if action was logged
        actions = await self.engine.storage.list_device_rows("actions", "test-device")
        block_host_actions = [a for a in actions if a["action"] == "block_host" and a["target"] == "malicious-site.com"]
        self.assertTrue(len(block_host_actions) > 0)

    async def test_self_protection_tamper_detection(self):
        # This is harder to test because it runs in a background task
        # But we can call the capture method
        hashes = self.engine._capture_integrity_hashes()
        self.assertGreater(len(hashes), 0)
        
    async def test_web_defense_suspicious_request(self):
        # We'll test the middleware by mocking or just checking if ingest is called
        # Actually, let's just check if it correctly detects suspicious paths in a manual way
        # since we're testing the engine here, not the full FastAPI app with middleware.
        # But we can verify the engine ingests these correctly.
        event_data = {
            "event_type": "SUSPICIOUS_WEB_REQUEST",
            "severity": "warning",
            "source": "web-defense",
            "details": {"client": "1.2.3.4", "path": "/.env"}
        }
        event = await self.engine.ingest(event_data)
        self.assertEqual(event.event_type, "SUSPICIOUS_WEB_REQUEST")
        self.assertEqual(event.source, "web-defense")

if __name__ == "__main__":
    unittest.main()
