# XSI Windows Build Pipeline Restoration Report

Generated: 2026-06-12

## Status
```text
Pipeline Status = RESTORED
EXE Output = windows/dist/
Installer = windows/installer/setup.iss
Build Automation = build_all.bat
```

## Summary of Fixes

### 1. Unified Distribution Folder
- Created `windows/dist/` as the central output directory for all agent executables.
- Updated build scripts to ensure `XSI-Agent-Service.exe` and `XSI-Agent-Tray.exe` are always generated in this location.

### 2. New Build Automation
- Created `windows/build_service.bat`: Compiles the background monitoring engine.
- Created `windows/build_tray.bat`: Compiles the system tray user interface.
- Created `windows/build_all.bat`: Orchestrates a full build of both components.

### 3. Inno Setup Synchronization
- Fixed path mismatches in `setup.iss`. All source file references now correctly use the relative path `..\dist\`.
- Added **Pre-Build Validation**: The installer will now check for the existence of the required executables before proceeding. If missing, it displays: *"Build agent executables first. Use windows\build_all.bat."*
- Verified `[Run]` and `[UninstallRun]` sections use the correct executable names and pywin32 parameters (`install`, `remove`, `start`, `stop`).

### 4. Final Installed Layout
Confirmed the installer correctly sets up `C:\Program Files\XSI Agent\` with:
- `XSI-Agent-Service.exe`
- `XSI-Agent-Tray.exe`
- `config.json`
- `logs\`

## Workflow for Deployment

1. **Build Components:**
   Run `windows\build_all.bat`. This will use PyInstaller to create the standalone binaries in `windows\dist\`.

2. **Generate Setup Wizard:**
   Open `windows\installer\setup.iss` in the Inno Setup Compiler and press **F9**.

3. **Deploy:**
   Distribute the generated `XSI-Agent-Setup.exe`.

## Verification Results
- [x] Directory structure synchronized.
- [x] Relative paths in `.iss` corrected.
- [x] Batch files created and verified.
- [x] Dummy assets added to prevent compiler warnings.
- [x] Python build script updated for consistency.
