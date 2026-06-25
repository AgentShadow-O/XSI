from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any

from backend.core.config import JWT_SECRET


def create_device_certificate(device_id: str, metadata: dict[str, Any] | None = None) -> str:
    payload = {
        "device_id": device_id,
        "nonce": secrets.token_urlsafe(16),
        "metadata_hash": hashlib.sha256(json.dumps(metadata or {}, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest(),
    }
    body = _b64(payload)
    signature = hmac.new(JWT_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"xsi-cert.{body}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def certificate_fingerprint(certificate: str) -> str:
    return hashlib.sha256(str(certificate).encode("utf-8")).hexdigest()


def _b64(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
