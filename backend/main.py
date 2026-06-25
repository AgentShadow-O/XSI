from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import RateLimiter
from backend.api.routes import api_router
from backend.api.websocket import websocket_router
from backend.core.config import APP_VERSION, CORS_ORIGINS, ENVIRONMENT, LOG_DIR, LOG_LEVEL, PRODUCTION, PROJECT_ROOT, SERVER_HOST, SERVER_PORT, ensure_runtime_dirs, validate_production_config
from backend.core.engine import XSIEngine


logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(name)s event=%(message)s", force=True)
logger = logging.getLogger("xsi")


def create_app(engine: XSIEngine | None = None, *, run_legacy_migration: bool = True) -> FastAPI:
    app_engine = engine or XSIEngine()
    rate_limiter = RateLimiter()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        validate_production_config()
        ensure_runtime_dirs()
        await app_engine.start()
        backed_up = []
        migrated = 0
        if run_legacy_migration:
            backup_dir = PROJECT_ROOT / "backend" / "database" / "backups"
            source_root = PROJECT_ROOT.parent
            backed_up = await app_engine.backup_legacy(source_root, backup_dir)
            migrated = await app_engine.migrate_legacy(source_root)
        logger.info("backend_started module=backend.main logs=%s backup_count=%s migrated=%s", LOG_DIR, len(backed_up), migrated)
        try:
            yield
        finally:
            await app_engine.stop()
            logger.info("backend_stopped module=backend.main")

    created = FastAPI(title="XSI - Extended Security Intelligence", version="0.2.0", debug=not PRODUCTION, lifespan=lifespan)
    created.state.engine = app_engine
    created.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    created.include_router(api_router(app_engine))
    created.include_router(websocket_router(app_engine))

    @created.middleware("http")
    async def production_guards(request: Request, call_next: Any):
        client = request.client.host if request.client else "unknown"
        if not rate_limiter.check(client):
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        
        # Suspicious request detection (simple)
        path = request.url.path.lower()
        if any(marker in path for marker in ("/.env", "/.git", "/wp-admin", "/phpmyadmin", "/config.php")):
            await app_engine.ingest({
                "event_type": "SUSPICIOUS_WEB_REQUEST",
                "severity": "warning",
                "source": "web-defense",
                "details": {"client": client, "path": path, "user_agent": request.headers.get("user-agent")}
            })
            return JSONResponse({"detail": "not found"}, status_code=404)

        if PRODUCTION and request.url.scheme != "https" and request.headers.get("x-forwarded-proto") != "https":
            return JSONResponse({"detail": "https required"}, status_code=403)
        
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:;"
        return response

    @created.get("/")
    async def root() -> dict[str, str]:
        return {"name": "XSI", "description": "Extended Security Intelligence"}

    @created.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "environment": ENVIRONMENT, "version": APP_VERSION}

    @created.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception module=backend.main path=%s error=%s", request.url.path, exc, exc_info=not PRODUCTION)
        if PRODUCTION:
            return JSONResponse(status_code=500, content={"detail": "internal server error"})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return created


engine = XSIEngine()
app = create_app(engine)


def main() -> None:
    uvicorn.run("backend.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)


if __name__ == "__main__":
    main()
