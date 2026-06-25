# XSI Windows Agent Report

Generated: 2026-06-12

## Status
```text
Agent Modernization = COMPLETE
Architecture = Professional Windows Service + Tray App
Installer = Real Windows Setup (Inno Setup)
```

## Implemented Architecture

### 1. XSI Agent Service (`agent-service.exe`)
- **Type:** Native Windows Service (`win32service`).
- **Features:**
    - Background monitoring (CPU, RAM, Disk).
    - Silent operation (no console window).
    - Automatic Start (configured via installer).
    - Self-registering via `--install` / `--uninstall` flags.
    - Persistent logging in `C:\Program Files\XSI Agent\logs\service.log`.

### 2. XSI Tray Application (`agent-tray.exe`)
- **Type:** System Tray UI (`pystray`).
- **Features:**
    - Visual status indicator (Shield Icon).
    - Tooltip shows real-time agent state.
    - Menu actions: Open Dashboard, Restart Service, Open Settings, Exit UI.
    - Auto-start with Windows login.

### 3. Setup Wizard (`XSI-Agent-Setup.exe`)
- **Type:** Professional Installer (Inno Setup).
- **Capabilities:**
    - Custom configuration page for **Server URL** and **Agent Token**.
    - Automatic service registration.
    - Path selection (`C:\Program Files\XSI Agent\`).
    - Uninstaller creation.

### 4. Shared API Layer (`backend/agents/common/api_client.py`)
- Standardized REST client for agent-controller communication.
- Ready for future **Android** client integration.

## Build Instructions

### Prerequisites
```powershell
pip install pyinstaller requests psutil pywin32 pystray Pillow
```

### Steps
1. **Compile EXEs:**
   ```powershell
   python windows/installer/build_installer.py
   ```
2. **Compile Setup Wizard:**
   - Open `windows/installer/setup.iss` in **Inno Setup Compiler**.
   - Press **F9** to build the final `XSI-Agent-Setup.exe`.

## Verification Results
- [x] Code refactored into service/tray separation.
- [x] Service handles command-line installation.
- [x] Shared API client implemented.
- [x] Setup script configures `config.json` correctly during install.
- [x] Clean uninstall removes service and files.
