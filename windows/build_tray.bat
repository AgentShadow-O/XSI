@echo off
echo Building XSI Agent Tray...
cd %~dp0
mkdir dist 2>nul

python -m PyInstaller --noconsole --onefile --name XSI-Agent-Tray ^
    --distpath dist ^
    tray/tray_app.py

echo Done. Check windows/dist/XSI-Agent-Tray.exe
