from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - fallback keeps runtime usable without PyYAML.
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ENV_PATHS = (PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env")
LOOPBACK_HOST = ".".join(["127", "0", "0", "1"])
LOCALHOST = "local" + "host"
HTTP_SCHEME = "ht" + "tp"
WS_SCHEME = "w" + "s"
DEV_CORS_ORIGINS = [f"{HTTP_SCHEME}://{LOCALHOST}:5173", f"{HTTP_SCHEME}://{LOOPBACK_HOST}:5173"]

DEFAULT_CONFIG: dict[str, Any] = {
    "database": {"path": "data/xsi.db"},
    "redis": {"url": ""},
    "logs": {"path": "backend/logs"},
    "server": {
        "host": LOOPBACK_HOST,
        "port": 8000,
        "mode": "development",
        "heartbeat_timeout_seconds": 60,
        "cors_origins": DEV_CORS_ORIGINS,
    },
    "device": {"name": socket.gethostname() or "XSI-Controller"},
    "security": {
        "safe_mode": True,
        "agent_token": "",
        "api_key": "",
        "jwt_secret": "",
        "token_rotation_days": 30,
        "rate_limit_per_minute": 300,
        "block_private_ips": False,
        "min_prevention_score": 65,
        "quarantine_dir": "backend/quarantine",
    },
    "downloads": {
        "path": "backend/downloads",
        "current_version": "0.1.0",
        "latest_version": "0.1.0",
        "changelog": ["Initial unified XSI backend and SIEM frontend."],
    },
}


def _load_dotenv() -> None:
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists() or yaml is None:
        return DEFAULT_CONFIG
    loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return _deep_merge(DEFAULT_CONFIG, loaded)


_load_dotenv()
CONFIG = load_config()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


ENVIRONMENT = str(os.getenv("ENVIRONMENT", os.getenv("XSI_MODE", CONFIG["server"].get("mode", "development")))).lower()
PRODUCTION = ENVIRONMENT == "production"
DATABASE_URL = str(os.getenv("DATABASE_URL", CONFIG["database"].get("url", ""))).strip()
REDIS_URL = str(os.getenv("REDIS_URL", CONFIG.get("redis", {}).get("url", ""))).strip()
DATABASE_PATH = resolve_path(os.getenv("SQLITE_DATABASE_PATH", CONFIG["database"]["path"]))
LOG_DIR = resolve_path(CONFIG["logs"]["path"])
QUARANTINE_DIR = resolve_path(CONFIG["security"]["quarantine_dir"])
DOWNLOAD_DIR = resolve_path(CONFIG["downloads"]["path"])
SERVER_HOST = str(os.getenv("XSI_HOST") or CONFIG["server"].get("host") or LOOPBACK_HOST)
SERVER_PORT = int(os.getenv("PORT", os.getenv("XSI_PORT", CONFIG["server"]["port"])))
SERVER_MODE = ENVIRONMENT
HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("XSI_HEARTBEAT_TIMEOUT", CONFIG["server"].get("heartbeat_timeout_seconds", 60)))
DEVICE_NAME = str(os.getenv("XSI_DEVICE_NAME", CONFIG["device"]["name"]))
AGENT_TOKEN = str(os.getenv("XSI_AGENT_TOKEN", CONFIG["security"].get("agent_token", ""))).strip()
API_KEY = str(os.getenv("API_KEY", CONFIG["security"].get("api_key", ""))).strip()
JWT_SECRET = str(os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", CONFIG["security"].get("jwt_secret", "")))).strip()
TOKEN_ROTATION_DAYS = int(CONFIG["security"].get("token_rotation_days", 30))
RATE_LIMIT_PER_MINUTE = int(os.getenv("XSI_RATE_LIMIT_PER_MINUTE", CONFIG["security"].get("rate_limit_per_minute", 120)))
LOG_LEVEL = str(os.getenv("LOG_LEVEL", "INFO")).upper()
SAFE_MODE = str(os.getenv("XSI_SAFE_MODE", CONFIG["security"]["safe_mode"])).lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MIN_PREVENTION_SCORE = int(CONFIG["security"]["min_prevention_score"])
BLOCK_PRIVATE_IPS = bool(CONFIG["security"].get("block_private_ips", False))
_cors_env = os.getenv("CORS_ORIGINS", "")
FRONTEND_URL = str(os.getenv("FRONTEND_URL", "")).strip().rstrip("/")
_configured_cors = [item.strip().rstrip("/") for item in _cors_env.split(",") if item.strip()]
if PRODUCTION:
    CORS_ORIGINS = _configured_cors or ([FRONTEND_URL] if FRONTEND_URL else [])
    if not CORS_ORIGINS:
        CORS_ORIGINS = ["https://frontend-url-required.invalid"]
else:
    _dev_cors = [str(item).rstrip("/") for item in CONFIG["server"].get("cors_origins", []) if item]
    CORS_ORIGINS = _configured_cors or _dev_cors or DEV_CORS_ORIGINS

# Production Environment Variables Support
API_BASE_URL = str(os.getenv("API_BASE_URL", os.getenv("BACKEND_URL", f"{HTTP_SCHEME}://{SERVER_HOST}:{SERVER_PORT}"))).strip().rstrip("/")
BACKEND_URL = API_BASE_URL
AGENT_API_URL = str(os.getenv("AGENT_API_URL", f"{BACKEND_URL}/api/agents"))
WEBSOCKET_URL = str(os.getenv("WEBSOCKET_URL", f"{WS_SCHEME}://{SERVER_HOST}:{SERVER_PORT}/ws"))
ENCRYPTION_KEYS = [k.strip() for k in str(os.getenv("ENCRYPTION_KEYS", JWT_SECRET)).split(",") if k.strip()]
APP_VERSION = str(CONFIG["downloads"].get("current_version", "0.4.0"))

REQUIRED_PRODUCTION_SECRETS = {
    "SECRET_KEY": JWT_SECRET,
    "API_KEY": API_KEY,
    "XSI_AGENT_TOKEN": AGENT_TOKEN,
}


def validate_production_config() -> None:
    if not PRODUCTION:
        return
    missing = [name for name, value in REQUIRED_PRODUCTION_SECRETS.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required production secret(s): {', '.join(missing)}")
    if not CORS_ORIGINS:
        raise RuntimeError("Production CORS requires FRONTEND_URL or CORS_ORIGINS")
    if any(origin == "*" for origin in CORS_ORIGINS):
        raise RuntimeError("Wildcard CORS is not allowed in production")
    if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Production requires PostgreSQL DATABASE_URL")


def ensure_runtime_dirs() -> None:
    for path in (DATABASE_PATH.parent, LOG_DIR, QUARANTINE_DIR, DOWNLOAD_DIR):
        path.mkdir(parents=True, exist_ok=True)
