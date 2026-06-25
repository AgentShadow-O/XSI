from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException, Request
from starlette.websockets import WebSocket

from backend.agents.registration import token_valid
from backend.core.config import API_KEY, JWT_SECRET, RATE_LIMIT_PER_MINUTE


def require_agent_token(token: str) -> None:
    if not token_valid(token):
        raise HTTPException(status_code=401, detail="invalid agent token")


def require_api_key(value: str) -> None:
    if not API_KEY or not value or not hmac.compare_digest(str(value), API_KEY):
        raise HTTPException(status_code=401, detail="invalid api key")


async def request_token(request: Request) -> str:
    auth = str(request.headers.get("authorization") or "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    try:
        body = await request.json()
    except Exception:
        body = {}
    return str(body.get("token") or request.headers.get("x-xsi-token") or "")


PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).rstrip(b"=").decode("ascii"),
        base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_raw, digest_raw = str(encoded or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _decode_b64(salt_raw)
        expected = _decode_b64(digest_raw)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, OverflowError):
        return False


def new_secret_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def create_access_token(subject: str, role: str = "mobile", expires_in: int = 3600, extra: dict[str, Any] | None = None) -> str:
    header = _b64({"alg": "HS256", "typ": "JWT"})
    claims = {"sub": subject, "role": role, "iat": int(time.time()), "exp": int(time.time()) + expires_in}
    claims.update(extra or {})
    payload = _b64(claims)
    signing_input = f"{header}.{payload}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def verify_access_token(token: str) -> dict[str, Any]:
    parts = str(token or "").split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    signing_input = f"{parts[0]}.{parts[1]}"
    if not hmac.compare_digest(parts[2], _sign(signing_input)):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    payload = _unb64(parts[1])
    if int(payload.get("exp") or 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="expired bearer token")
    return payload


def bearer_payload(request: Request) -> dict[str, Any]:
    auth = str(request.headers.get("authorization") or "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return verify_access_token(auth[7:].strip())


def websocket_authorized(websocket: WebSocket) -> bool:
    token = str(websocket.query_params.get("token") or websocket.headers.get("x-xsi-token") or "")
    if token and API_KEY and hmac.compare_digest(token, API_KEY):
        return True
    try:
        if token:
            verify_access_token(token)
            return True
    except HTTPException:
        return False
    return False


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.time()
        hits = self._hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_MINUTE:
            return False
        hits.append(now)
        return True


def _b64(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(payload: str) -> dict[str, Any]:
    return json.loads(_decode_b64(payload))


def _decode_b64(payload: str) -> bytes:
    padded = payload + "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _sign(value: str) -> str:
    digest = hmac.new(JWT_SECRET.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
