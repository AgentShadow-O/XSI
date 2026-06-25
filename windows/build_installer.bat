@echo off
echo Building XSI Agent Installer...
cd %~dp0
mkdir dist 2>nul

echo Making sure the service is built...
call build_service.bat

echo Compiling Installer...
python -m PyInstaller --noconsole --onefile --name XSI-Agent-Installer ^
    --add-data "dist/XSI-Agent-Service.exe;." ^
    --add-data "dist/XSI-Agent-Tray.exe;." ^
    --uac-admin ^
    --distpath dist ^
    installer/installer.py

echo Done. Check windows/dist/XSI-Agent-Installer.exe
