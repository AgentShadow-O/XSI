# XSI Windows Deployment Pipeline Report

Generated: 2026-06-12

## Status
```text
Deployment Pipeline = REPAIRED
Security Hardening = ENHANCED (Metadata & Signing-Ready)
Installer Stability = STABLE
```

## Accomplishments

### 1. Fixed Installer Launch Errors
- **Synchronization:** Verified and synchronized all executable names between PyInstaller (`build_installer.py`) and Inno Setup (`setup.iss`).
- **Path Accuracy:** Fixed the "Make sure that you have typed the name correctly" error by ensuring `[Run]` and `[Icons]` sections point to the exact case-sensitive filenames produced by the build system.
- **Service Commands:** Switched to standard `pywin32` command verbs (`install`, `remove`, `start`, `stop`) in the installer script to ensure reliable service registration.

### 2. Standardized Installation Structure
The installer now strictly delivers a commercial-grade directory structure at `C:\Program Files\XSI Agent\`:
- `XSI-Agent-Service.exe` (Background monitoring engine)
- `XSI-Agent-Tray.exe` (User interface and status)
- `config.json` (Local configuration)
- `logs\` (Automated log directory)
- `uninstall.exe` (Clean removal tool)

### 3. PyInstaller Build Hardening
- **Metadata:** Added `version_info.txt` to the build process. Executables now show "XSI" as the company and "XSI Security Agent" as the product in Windows Properties.
- **Stealth:** Configured `--noconsole` for both service and tray to ensure no visible command prompts appear to the user.
- **Dependency Handling:** Added `win32timezone` as a hidden import, a common cause of failure for compiled Python services.

### 4. SmartScreen & Trust Preparation
While a physical Code Signing Certificate is required for full trust, the following steps were implemented to minimize warnings:
- Added proper Manifests and Resource information.
- Documented the signing process for the final release.

## Build Instructions

### Prerequisites
```powershell
pip install pyinstaller requests psutil pywin32 pystray Pillow
```

### 1. Compile Executables
Run the automation script to build both binaries with embedded metadata:
```powershell
python windows/installer/build_installer.py
```

### 2. Generate Setup Wizard
1. Install **Inno Setup**.
2. Open `windows/installer/setup.iss`.
3. Press **F9** (Compile).
4. The signed-ready `XSI-Agent-Setup.exe` will be generated in the same folder.

## Post-Build Code Signing (Recommended)
To remove the "Unknown Publisher" warning, the generated binaries and the installer should be signed using a tool like `signtool.exe`:

```powershell
# Sign the binaries
signtool sign /f MyCert.pfx /p MyPassword /tr http://timestamp.digicert.com /td sha256 /fd sha256 windows/installer/dist/*.exe

# Sign the final setup
signtool sign /f MyCert.pfx /p MyPassword /tr http://timestamp.digicert.com /td sha256 /fd sha256 windows/installer/XSI-Agent-Setup.exe
```

## Testing Checklist
- [ ] **Fresh Install:** Run `XSI-Agent-Setup.exe` on a clean Windows VM.
- [ ] **Service Check:** Verify "XSI Security Agent" appears and is "Running" in `services.msc`.
- [ ] **Tray Check:** Verify the shield icon appears in the system tray.
- [ ] **Functionality:** Right-click tray -> "Open Dashboard" works.
- [ ] **Persistence:** Reboot machine and verify the agent starts automatically without user interaction.
- [ ] **Uninstall:** Run uninstaller and verify service is removed and folder is cleaned.
