# XSI v2 Phase 1 Stability Report

Generated: 2026-06-11

## Scope

This report covers Phase 1 stability verification after the Phase 0 audit. The existing `data/xsi.db` backup was confirmed by the user before running stability checks.

No source-code fixes were required during this phase.

## System Status

```text
System Status = STABLE
```

The current system builds and its existing tested backend/API/database/dashboard artifact paths are operational. This status applies to the current XSI v1-style functionality, not to missing XSI v2 features identified in `AUDIT_REPORT.md`.

## Verification Summary

| Area | Result | Notes |
|---|---:|---|
| Python backend compilation | PASS | `python -m compileall -q backend tests` completed successfully. |
| Backend unit/API tests | PASS | `python -m unittest discover -s tests -v` ran 4 tests successfully. |
| Backend startup | PASS | FastAPI app lifecycle started and stopped through `TestClient`. |
| Database connection | PASS | SQLite database opened and API summary queries completed. |
| Frontend production build | PASS | `npm.cmd run build` completed successfully outside the sandbox. |
| Frontend production load | PASS | Vite preview served built frontend with HTTP 200. |
| APIs | PASS | Core API smoke checks returned HTTP 200. |
| Authentication | PASS | Existing mobile API-key-to-JWT flow and agent token flow passed tests. |
| Dashboard artifact | PASS | Built frontend includes root app document and JS/CSS assets. |
| Settings | PASS | Existing settings endpoint returned config JSON. |
| Alerts | PASS | Existing alerts endpoint returned data from SQLite. |

## Commands Run

### Backend Tests

```powershell
python -m unittest discover -s tests -v
```

Result:

```text
Ran 4 tests in 0.339s
OK
```

Covered:

- Agent registration.
- Agent heartbeat.
- Agent command queue.
- Mobile login.
- Mobile authenticated status.
- Device online/offline recovery.
- Event persistence.

### Python Compilation

```powershell
python -m compileall -q backend tests
```

Result:

```text
PASS
```

### Frontend Build

Initial command:

```powershell
npm run build
```

Result:

```text
FAILED - PowerShell execution policy blocked npm.ps1
```

Corrected command:

```powershell
npm.cmd run build
```

Sandbox result:

```text
FAILED - EPERM while writing frontend/dist/index.html
```

The same project build was then rerun outside the sandbox because the failure was a workspace file-write permission issue, not a source compilation issue.

Final result:

```text
PASS - Vite built successfully
```

Built artifacts:

```text
frontend/dist/index.html
frontend/dist/assets/index.css
frontend/dist/assets/index.js
```

### Frontend Load Check

The built frontend was served with Vite preview through a short-lived local process.

Result:

```text
HTTP 200
contains root app element: true
```

### API Smoke Checks

Core endpoints were checked through FastAPI `TestClient`.

| Endpoint | Result |
|---|---:|
| `GET /api/health` | 200 |
| `GET /api/summary` | 200 |
| `GET /api/devices?limit=5` | 200 |
| `GET /api/events?limit=5` | 200 |
| `GET /api/alerts?limit=5` | 200 |
| `GET /api/settings` | 200 |
| `GET /api/downloads` | 200 |
| `POST /api/mobile/login` | 200 |
| `GET /api/mobile/status` | 200 |

## Database Status

Database file:

```text
data/xsi.db
```

Post-check table counts:

```text
devices 1
events 3550862
alerts 3528076
actions 2969
settings 1
```

The test run did not increase the event, alert, action, or settings counts. The API tests did exercise the existing `api-desktop-1` device record.

## Feature Stability Assessment

### Project Builds Successfully

Status: PASS

- Backend Python files compile.
- Frontend Vite production build succeeds when not blocked by sandbox file permissions.

### Backend Starts Successfully

Status: PASS

- FastAPI app lifecycle starts.
- Engine initializes storage.
- Existing legacy migration marker prevents duplicate migration.
- App shuts down cleanly.

### Frontend Loads Successfully

Status: PASS

- Production build generated.
- Local preview returned HTTP 200.
- Root app element was present.

### APIs Function Correctly

Status: PASS

- Core read APIs returned HTTP 200.
- Agent command test passed.
- Mobile status test passed.

### Authentication Works

Status: PASS for existing authentication.

Verified:

- API-key mobile login returns JWT.
- Bearer JWT grants mobile status access.
- Shared agent token allows agent registration and heartbeat.

Not part of current functionality:

- User login.
- User registration.
- Password hashing.
- Refresh tokens.
- Session invalidation.

### Database Connections Work

Status: PASS

- SQLite opened successfully.
- Summary and list queries completed against the existing large database.

### Existing Dashboard Works

Status: PASS for build/load artifact.

- Production frontend builds.
- Preview serves the SPA shell.
- Browser-level visual/UI interaction testing was not performed in this phase.

### Existing Settings Work

Status: PASS for current behavior.

- `GET /api/settings` returned current config.
- Settings are currently read-only JSON.

### Existing Alerts Work

Status: PASS

- `GET /api/alerts` returned data.
- Summary reports active alert count.

## Stability Issues Found and Resolved

No source-code stability bugs were found that required implementation changes.

Environment/tooling issues encountered:

1. `npm run build` failed under PowerShell because `npm.ps1` is blocked by the local execution policy.
   - Resolution: use `npm.cmd run build`.

2. `npm.cmd run build` failed inside the sandbox with `EPERM` when writing `frontend/dist/index.html`.
   - Resolution: reran the same command outside the sandbox with approval.
   - Result: build passed.

3. PowerShell `Start-Process` failed with a duplicate `Path`/`PATH` environment-key error while attempting to launch Vite preview.
   - Resolution: used a short Python `subprocess` harness to launch and stop the preview process.
   - Result: frontend served HTTP 200.

## Remaining Stability Risks

These do not block Phase 1, but should be addressed before major v2 migration:

- Tests instantiate the real FastAPI app and can touch the configured runtime database.
- Startup runs backup/migration routines automatically.
- SQLite database is already large and needs retention, pagination, and migration planning.
- Frontend relies on browser-exposed `VITE_API_KEY`.
- PostgreSQL storage is not fully equivalent to SQLite storage.
- WebSocket and command queues are in-memory and not multi-worker safe.

## Phase 1 Conclusion

The existing system is stable enough to proceed to Phase 2 backup and migration safety work.

```text
System Status = STABLE
Next Phase = PHASE 2 - BACKUP & MIGRATION SAFETY
```
