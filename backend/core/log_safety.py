from __future__ import annotations

import json
import re
from typing import Any


SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
    "secret",
    "private_key",
    "device_secret",
    "encryption_key",
    "authorization",
}


_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key['\"]?\s*[:=]\s*['\"]?)[^,'\"\s}]+"),
    re.compile(r"(?i)(token['\"]?\s*[:=]\s*['\"]?)[^,'\"\s}]+"),
    re.compile(r"(?i)(password['\"]?\s*[:=]\s*['\"]?)[^,'\"\s}]+"),
    re.compile(r"(?i)(secret['\"]?\s*[:=]\s*['\"]?)[^,'\"\s}]+"),
]


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        redacted = value
        for pattern in _PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        return redacted
    return value


def safe_json(payload: dict[str, Any]) -> str:
    return json.dumps(redact(payload), ensure_ascii=True)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(marker in normalized for marker in SENSITIVE_KEYS)
