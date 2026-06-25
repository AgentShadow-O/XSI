# XSI v2 Phase 0 Audit Report

Generated: 2026-06-11

## Audit Scope

This audit inspected the existing XSI project before any upgrade work. No implementation files were modified during the audit.

Areas reviewed:

- Frontend
- Backend
- Database
- APIs
- Authentication
- Agent communication
- Dashboard
- Settings
- Logging system
- Detection system
- Existing SIEM functions
- Existing XDR functions
- Existing IPS functions
- Deployment and tests

## Executive Summary

XSI is currently a compact FastAPI backend with a React/Vite frontend and a SQLite-first persistence layer. It already has useful foundations for device registration, heartbeat tracking, event ingestion, alert generation, WebSocket event streaming, simple mobile API access, detection/risk scoring, and safe-mode prevention actions.

The project is not yet an enterprise XDR/SIEM/IPS platform. Several v2 requirements are either missing or only partially represented:

- No full user authentication system.
- No user registration, password hashing, refresh tokens, password reset, or durable sessions.
- No certificate-based device enrollment.
- No durable command queue.
- No strict per-device authorization boundary.
- No real Android APK or PWA.
- No production Windows installer.
- No WAF/CSRF/bot protection layer.
- No configurable SIEM/XDR/IPS settings UI.
- No MITRE ATT&CK mapping, IOC matching, advanced search, or long-term event correlation.

The largest immediate architectural concern is the existing SQLite database size. `data/xsi.db` is about 1.3 GB and contains approximately 3.55 million events and 3.53 million alerts. Backup, migration, and dashboard query work must be staged carefully.

## Current Architecture

### Backend

Primary stack:

- FastAPI application in `backend/main.py`
- Uvicorn local runner
- Gunicorn/Uvicorn deployment target
- Pydantic models
- SQLite storage by default
- Optional PostgreSQL storage selected by `DATABASE_URL`
- In-process WebSocket event bus
- In-process command queues
- JSONL logs for events and actions

Main backend flow:

1. `backend/main.py` creates `XSIEngine`.
2. Startup initializes runtime directories and storage.
3. Startup attempts legacy database backup and migration.
4. REST API routes are mounted under `/api`.
5. WebSocket route is mounted at `/ws`.
6. Incoming events pass through rules, correlation, risk scoring, prevention recommendation, persistence, and event bus publication.

### Frontend

Primary stack:

- React 19
- Vite 6
- lucide-react icons
- Plain CSS

Frontend pages:

- Dashboard
- Events
- Alerts
- Endpoints
- Network
- IPS
- Downloads
- Settings

The frontend is a single-page app in `frontend/src/main.jsx`. It depends on:

- `VITE_API_URL`
- `VITE_WS_URL`
- `VITE_API_KEY`

### Database

Default database:

- `data/xsi.db`
- SQLite WAL mode

Current database status from inspection:

- Size: about 1.3 GB
- `devices`: 1 row
- `events`: 3,550,862 rows
- `alerts`: 3,528,076 rows
- `processes`: 1 row
- `network_activity`: 1 row
- `actions`: 2,969 rows
- `rules`: 0 rows
- `users`: 0 rows
- `settings`: 1 row

Existing tables:

- `devices`
- `events`
- `alerts`
- `processes`
- `network_activity`
- `actions`
- `rules`
- `users`
- `settings`

Indexes exist for event risk, event device, alert risk, action id, device id, and device status.

PostgreSQL support exists in `backend/database/postgres_storage.py`, but it is less complete than SQLite:

- No event indexing into `processes` and `network_activity`.
- No JSONL action/event logging.
- Search parameter is ignored.
- Legacy migration returns `0`.
- Schema is created directly without versioned migrations.

### Deployment

Deployment files are present:

- `deployment/Dockerfile`
- `deployment/docker-compose.yml`
- `deployment/nginx.conf`
- `deployment/install.sh`
- `deployment/README.md`

Docker Compose includes:

- Controller
- PostgreSQL 16
- Redis 7
- Nginx

Redis is declared but not used by the application code yet.

## Folder Structure

```text
XSI/
├─ backend/
│  ├─ agents/
│  ├─ api/
│  ├─ core/
│  ├─ database/
│  ├─ detection/
│  ├─ logs/
│  ├─ prevention/
│  ├─ sensors/
│  ├─ tray/
│  └─ main.py
├─ data/
│  └─ xsi.db
├─ deployment/
├─ frontend/
│  ├─ src/
│  ├─ dist/
│  ├─ node_modules/
│  ├─ package.json
│  └─ vite.config.js
├─ tests/
├─ config.yaml
└─ requirements.txt
```

Generated/runtime directories are present in the repository tree:

- `frontend/node_modules`
- `frontend/dist`
- `backend/__pycache__`
- `backend/logs`
- `backend/database/backups`
- SQLite WAL/SHM files

## Existing Functionality

### APIs

Implemented endpoints include:

- `GET /api/health`
- `GET /api/summary`
- `GET /api/devices`
- `POST /api/devices/register`
- `GET /api/events`
- `POST /api/events`
- `GET /api/alerts`
- `GET /api/processes`
- `GET /api/network`
- `GET /api/actions`
- `GET /api/rules`
- `POST /api/agents/register`
- `POST /api/agents/heartbeat`
- `POST /api/agents/event`
- `GET /api/agents/{device_id}/commands`
- `POST /api/agents/command`
- `POST /api/agents/{device_id}/rotate-token`
- `POST /api/ips/action`
- `GET /api/settings`
- `GET /api/downloads`
- `GET /api/downloads/{package_name}`
- `POST /api/mobile/login`
- `GET /api/mobile/devices`
- `GET /api/mobile/alerts`
- `GET /api/mobile/status`
- `WS /ws`

### Device and Agent Communication

Implemented:

- Agent token validation using a shared configured token.
- Agent registration.
- Heartbeat updates.
- Stale heartbeat offline marking.
- Event submission from agents.
- Per-device in-memory command queue.
- Token rotation endpoint for stored device token hash.
- Lightweight Python endpoint agent.
- Generated PowerShell Windows agent starter.

Not implemented:

- Device certificates.
- Mutual TLS.
- Per-device token validation against stored device token hashes.
- Durable command queues.
- Agent-side execution of queued commands.
- Agent config sync.
- Signed policy/rule sync.
- Device linking to authenticated users.

### Dashboard

Implemented:

- Summary metrics.
- Live WebSocket event feed.
- Event table and local search over loaded events.
- Alert table.
- Endpoint registration form.
- Device and process tables.
- Network activity table.
- IPS action table.
- Download cards.
- Read-only settings JSON.

Not implemented:

- Login gate.
- Role-aware views.
- Per-device command center pages.
- SIEM threat hunting workflow.
- Rich filtering, pagination, or server-side search UI.
- Editable validated settings.
- Accessibility review.

### Logging

Implemented:

- SQLite event/action persistence.
- JSONL event log at `backend/logs/events.jsonl`.
- JSONL action log at `backend/logs/actions.jsonl`.
- Empty server stdout/stderr log files exist.

Limitations:

- No log rotation.
- No retention policy.
- No compression or archival.
- No structured application audit log for auth/admin actions.
- Logs may duplicate database data without lifecycle management.

### Detection System

Implemented:

- Rule engine for port scan, SYN flood, and suspicious PowerShell/cmd usage.
- Short in-memory correlation window.
- Risk scoring from severity, source, event type, tags, and behavior score.
- Alert creation when risk score or severity crosses thresholds.

Limitations:

- Rules are hardcoded.
- `rules` table is empty and not actively used by `RuleEngine`.
- Correlation state is in-memory and lost on restart.
- No MITRE ATT&CK mapping.
- No IOC store or matching.
- No timeline model beyond raw event timestamps.
- No tenant/user/device isolation model.

### SIEM Functions

Existing SIEM-like features:

- Central event ingestion.
- Event storage.
- Alert generation.
- Basic event search endpoint for SQLite.
- Dashboard event and alert views.
- Legacy database migration into unified events.

Missing enterprise SIEM features:

- Full-text search/indexing.
- Query language.
- Saved searches.
- Event normalization schema beyond flexible details JSON.
- Timeline analysis.
- IOC matching.
- MITRE ATT&CK mapping.
- Event retention and lifecycle controls.
- High-volume ingestion pipeline.

### XDR Functions

Existing XDR-like features:

- Endpoint registration.
- Endpoint heartbeat.
- Basic process snapshot helper.
- Basic file event helper.
- Risk scoring for endpoint events.
- Safe-mode recommendations for stopping processes, quarantining files, and isolating devices.

Missing enterprise XDR features:

- Continuous production endpoint agent.
- Tamper-resistant agent service.
- File monitoring loop.
- Network monitoring loop.
- Persistence detection.
- Response action execution on remote endpoints.
- Endpoint isolation implementation.
- Policy/config sync.
- Device health model beyond arbitrary JSON.

### IPS Functions

Existing IPS-like features:

- Recommended actions based on risk.
- IP blocking through OS firewall adapters.
- Port blocking through OS firewall adapters.
- File quarantine helper.
- Process termination helper.
- Safe mode enabled by default.

Limitations:

- Domain blocking is not implemented.
- Host blocking is not distinct from IP blocking.
- Automated rules are hardcoded.
- No rollback/unblock API.
- No action approval workflow.
- No rate-limit/brute-force rules outside global API request limiter.
- Firewall operations are local to the controller, not endpoint devices.

## Broken or Risky Functionality

These items require confirmation in Phase 1 stability testing, but the audit found likely issues:

1. Root route does not serve the frontend.
   - `GET /` returns JSON only.
   - The Vite frontend must run or be deployed separately.

2. Dashboard registration exposes sensitive token material.
   - `POST /api/devices/register` returns `agent_token` to the frontend.

3. Frontend API key is browser-exposed.
   - `VITE_API_KEY` is embedded in client-side JavaScript.

4. Public read APIs are unauthenticated.
   - Summary, devices, events, alerts, processes, network, actions, rules, downloads, and settings endpoints do not require authentication.

5. Shared agent token is the effective trust boundary.
   - Stored per-device token hashes are not used for subsequent request validation.

6. Command queues are in-memory.
   - Queued commands are lost on restart and cannot be audited reliably before retrieval.

7. PostgreSQL backend is not functionally equivalent to SQLite backend.
   - Search behavior, legacy migration, and event indexing differ.

8. Settings page is display-only.
   - No validation or update path exists.

9. Tests use default secrets and the real FastAPI app.
   - API tests start the app lifecycle, which may initialize and migrate the configured runtime database.

10. `frontend/dist` and `node_modules` are present in the project tree.
    - This increases repository size and can hide source/build drift.

## Security Weaknesses

High priority:

- Default secrets are configured in `config.yaml`.
- Dashboard/mobile API key is designed to be passed to the browser.
- Most read endpoints are public.
- No user account authentication exists.
- No password hashing implementation exists.
- No refresh token/session invalidation model exists.
- No CSRF protection for future cookie-based auth.
- No rate limit persistence or distributed rate limiting.
- No audit log for admin actions.
- No certificate-bound device identity.
- No per-device authorization for commands or events.
- No WAF layer.
- No bot detection.
- No brute-force-specific protection for login, because full login does not exist yet.

Medium priority:

- JWT implementation is custom and minimal.
- JWTs have no `iat`, `jti`, issuer, audience, revocation, or rotation support.
- WebSocket auth accepts API key or mobile bearer token only.
- CORS falls back to wildcard if configured origins are empty.
- Production HTTPS enforcement relies on `X-Forwarded-Proto`.
- Nginx config currently serves HTTP and has ACME scaffolding, but no complete TLS server block.
- Safe mode prevents destructive IPS actions by default, but manual action endpoint itself is unauthenticated.

## Performance Bottlenecks

Observed or likely:

- SQLite database is already about 1.3 GB with millions of rows.
- `GET /api/events` and `GET /api/alerts` are simple ordered queries over large tables.
- Alert count and max risk summary queries may become expensive without tighter indexing/summary tables.
- Dashboard refresh polls nine endpoints every five seconds.
- WebSocket event bus is in-memory per process; Gunicorn multi-worker deployments will not share events.
- Correlation scans the in-memory recent event deque for each event.
- SQLite JSON details are stored as text, limiting efficient structured search.
- No pagination cursor model exists; only `limit` is supported.
- No retention, compaction, or archival controls exist.

## Missing Features Against XSI v2 Requirements

### Authentication

Missing:

- Login with username/password.
- Register.
- Secure password hashing.
- Refresh tokens.
- Session management.
- Multi-device sessions.
- Password reset.
- Session invalidation.
- Role-based access control.

### Device Registration

Missing:

- Certificate issuance.
- Certificate validation.
- QR enrollment.
- Device linking to users.
- Device metadata schema.
- Strict per-device isolation.

### Windows Agent

Partial only:

- PowerShell starter is generated.
- Python agent exists.

Missing:

- Production Windows service.
- Installer package.
- Signed binaries/scripts.
- Tamper protection.
- Local detection loops.
- Secure config sync.
- Dashboard shortcut installer behavior.

### Mobile Integration

Partial only:

- Mobile login with API key.
- Mobile devices/alerts/status endpoints.
- Android client starter markdown.

Missing:

- PWA manifest/service worker.
- QR enrollment.
- Android APK.
- Push/local alerts.
- Secure mobile auth flow.

### UI Modernization

Missing:

- Next.js migration.
- Tailwind.
- Framer Motion.
- Enterprise SOC visual system.
- Accessible component states.
- Device command center pages.

### SIEM Upgrade

Missing:

- Centralized multi-source collectors.
- Event correlation beyond short memory window.
- Threat hunting.
- Search engine.
- Timeline analysis.
- IOC matching.
- MITRE ATT&CK mapping.
- Windows Event/Sysmon/firewall/app log collectors.

### XDR Upgrade

Missing:

- Persistence detection.
- Suspicious behavior models beyond simple rules.
- Network anomaly detection.
- Remote quarantine/block/kill/isolate workflow.
- High-performance endpoint architecture.

### IPS Upgrade

Missing:

- Domain blocking.
- Host blocking.
- Automated response rules UI.
- Brute-force prevention rules.
- Unblock/rollback actions.

### Self-Protection

Missing:

- Tamper protection.
- Config protection.
- Rule protection.
- Service protection.
- Integrity monitoring.
- Immediate self-protection alerts.

### Web Defense

Missing:

- WAF.
- CSRF protection.
- SQL injection policy layer.
- XSS protection policy.
- Bot detection.
- Auth-specific brute-force defenses.

## Dependency and Compatibility Notes

Python dependencies:

- FastAPI `0.115.12`
- Uvicorn `0.34.2`
- httpx `0.27.2`
- psutil `7.0.0`
- Pydantic `>=2.7`
- PyYAML `>=6.0.1`
- Scapy `>=2.5.0`
- watchdog `>=4.0.0`
- gunicorn `>=22.0.0`
- psycopg binary `>=3.2.3`
- redis `>=5.0.8`

Frontend dependencies:

- React `^19.0.0`
- React DOM `^19.0.0`
- Vite `^6.0.5`
- TypeScript `^5.7.2`
- lucide-react `^0.468.0`
- `@vitejs/plugin-react` `^4.3.4`

Notes:

- Redis is installed/deployed but unused.
- RabbitMQ and MinIO are not present.
- Next.js, Tailwind, and Framer Motion are not present.
- PostgreSQL support exists but needs parity testing before migration.

## Testing Status

Existing test file:

- `tests/test_device_lifecycle.py`

Coverage areas:

- Device online/offline recovery.
- Event persistence.
- In-memory command queue.
- Mobile login/status.
- Agent registration/heartbeat/command path.

Phase 0 did not execute the full test suite because the API tests instantiate the real FastAPI app and may trigger startup behavior against configured runtime paths, including database initialization and legacy migration. This should be handled in Phase 1 with a controlled test database and explicit backup/safety step.

## Upgrade Recommendations

### Immediate Phase 1 Priorities

1. Establish a safe test profile.
   - Use temporary SQLite or isolated PostgreSQL.
   - Prevent tests from touching `data/xsi.db`.

2. Verify current build/runtime status.
   - Backend import/startup.
   - Frontend build.
   - API smoke tests.
   - WebSocket smoke test.

3. Fix stability defects before adding features.
   - Especially any test isolation issues, startup migration side effects, and frontend env handling.

4. Protect the current database.
   - Create backup before any startup, migration, compaction, or schema change.

### Architecture Recommendations

1. Keep FastAPI.
   - It is already the backend framework and matches the recommended v2 stack.

2. Add versioned migrations.
   - Alembic for PostgreSQL.
   - Explicit migration scripts for SQLite-to-PostgreSQL data migration.

3. Move command queue and WebSocket fanout out of process.
   - Redis can handle queues/pub-sub initially.
   - RabbitMQ can be added when durable workflows require it.

4. Treat PostgreSQL as the target event store.
   - Add partitioning or retention policies before migrating millions of events.

5. Add object storage only when needed.
   - MinIO should be introduced for artifacts, quarantined files, evidence bundles, and agent packages, not just for modernization.

### Security Recommendations

1. Replace default secrets before any network exposure.
2. Add full user authentication before UI expansion.
3. Remove dashboard API key from frontend runtime.
4. Require auth for all dashboard APIs.
5. Validate per-device tokens against stored hashes.
6. Add device certificate enrollment after token-based enrollment is stable.
7. Add audit logging for auth, settings, commands, and prevention actions.
8. Add CSRF protection if cookie sessions are used.

### Database Recommendations

1. Back up `data/xsi.db`, WAL, and SHM before any Phase 1 startup test.
2. Add retention/archival strategy before loading more events.
3. Add cursor pagination for events and alerts.
4. Add server-side search with indexes.
5. Avoid direct bulk migration to PostgreSQL until schema parity is complete.

### Frontend Recommendations

1. Keep the current Vite UI through stabilization.
2. Do not migrate to Next.js until backend auth/API contracts are stable.
3. Add login and authenticated API client first.
4. Add device detail pages before heavy styling work.
5. Make settings forms real and validated, not placeholders.

## Phase 0 Conclusion

Phase 0 audit is complete.

Recommended next gate:

```text
Proceed to Phase 1 - Stability Check only after confirming backup expectations for the existing 1.3 GB SQLite database.
```

Current assessed status:

```text
System Status: AUDITED, NOT YET STABILITY VERIFIED
```
