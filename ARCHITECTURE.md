# XSI System Architecture

XSI follows a modern, modular architecture optimized for security operations.

## Core Components
- **API Backend (FastAPI):** Centralized RESTful API handling authentication, device management, and security intelligence.
- **Engine (XSIEngine):** Orchestrates event ingestion, correlation, threat detection, and prevention actions.
- **Database (SQLite/PostgreSQL):** Persistent storage for devices, events, alerts, and settings.
- **Sensors/Agents:** Lightweight agents installed on endpoints for EDR/IDS capability.
- **Frontend (React/Vite):** A secure dashboard for security analysts.

## Data Flow
1. **Agents** send telemetry (heartbeats, process logs, network activity) via API.
2. **Backend Engine** ingests, processes, correlates, and scores events.
3. **Prevention Rules** are evaluated, and automated actions (block IP, stop process) are triggered if necessary.
4. **Dashboard** visualizes events, alerts, and device status in real-time.
