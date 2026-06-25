# XSI API Documentation

All API endpoints are prefixed with `/api`.

## Authentication
- `POST /api/auth/register`: Create a new admin/analyst user.
- `POST /api/auth/login`: Authenticate and receive tokens.
- `POST /api/auth/refresh`: Refresh access token.

## Devices & Agents
- `GET /api/devices`: List all devices.
- `GET /api/devices/{device_id}/command-center`: Get device-specific security telemetry.
- `POST /api/agents/register`: Agent-initiated registration.
- `POST /api/agents/heartbeat`: Agent heartbeat.

## SIEM & Events
- `GET /api/events`: List events with optional filters (`search`, `device_id`, `source`, `severity`).
- `POST /api/events`: Ingest new event (normalized format).

## Settings
- `GET /api/settings/{key}`: Retrieve system settings.
- `POST /api/settings/{key}`: Update system settings.
