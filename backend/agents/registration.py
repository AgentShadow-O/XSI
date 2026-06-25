from __future__ import annotations

import hashlib
import hmac
import uuid

from backend.core.config import AGENT_TOKEN


def token_valid(token: str) -> bool:
    if not AGENT_TOKEN or not token:
        return False
    return hmac.compare_digest(str(token), AGENT_TOKEN)


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def new_device_id(seed: str = "") -> str:
    if seed:
        return f"xsi-{uuid.uuid5(uuid.NAMESPACE_DNS, seed)}"
    return f"xsi-{uuid.uuid4()}"
