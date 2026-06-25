@echo off
echo Building XSI Agent Service...
cd %~dp0
mkdir dist 2>nul

python -m PyInstaller --noconsole --onefile --name XSI-Agent-Service ^
    --paths "%~dp0.." ^
    --hidden-import win32timezone ^
    --hidden-import backend.agents.common.api_client ^
    --hidden-import backend.agents.common.temp_manager ^
    --collect-submodules backend ^
    --collect-data backend ^
    --add-data "%~dp0..\config.yaml;." ^
    --distpath dist ^
    service/xsi_service.py

echo Done. Check windows/dist/XSI-Agent-Service.exe
