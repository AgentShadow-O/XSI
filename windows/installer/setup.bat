@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo XSI Agent Production Setup
echo ==========================================

REM 1. Prompt for Server URL
set /p SERVER_URL="Enter XSI Server URL (e.g. https://xsi-api.example.com): "
if "!SERVER_URL!"=="" (
    echo Server URL is required.
    exit /b 1
)
set /p ENROLLMENT_TOKEN="Enter XSI Enrollment Token: "

REM 2. Create directory structure
set BASE_DIR=C:\ProgramData\XSI
echo Creating directories in %BASE_DIR%...
mkdir "%BASE_DIR%" 2>nul
mkdir "%BASE_DIR%\temp" 2>nul
mkdir "%BASE_DIR%\logs" 2>nul
mkdir "%BASE_DIR%\data" 2>nul
mkdir "%BASE_DIR%\config" 2>nul
mkdir "%BASE_DIR%\modules" 2>nul
mkdir "%BASE_DIR%\cache" 2>nul
mkdir "%BASE_DIR%\queue" 2>nul

REM 3. Set Permissions
echo Applying secure permissions...
REM Admin and System get full control, Users get Read & Execute
icacls "%BASE_DIR%" /inheritance:r /grant:r "Administrators":(OI)(CI)F /grant:r "SYSTEM":(OI)(CI)F /grant:r "Users":(OI)(CI)RX /T /Q
REM Ensure config is restricted to Admin/System only
icacls "%BASE_DIR%\config" /inheritance:r /grant:r "Administrators":(OI)(CI)F /grant:r "SYSTEM":(OI)(CI)F /T /Q

REM 4. Generate initial config
echo Writing agent.json...
echo { > "%BASE_DIR%\config\agent.json"
echo   "server": "!SERVER_URL!", >> "%BASE_DIR%\config\agent.json"
echo   "token": "", >> "%BASE_DIR%\config\agent.json"
echo   "enrollment_token": "!ENROLLMENT_TOKEN!", >> "%BASE_DIR%\config\agent.json"
echo   "device_name": "%COMPUTERNAME%" >> "%BASE_DIR%\config\agent.json"
echo } >> "%BASE_DIR%\config\agent.json"

echo.
echo Setup Complete!
echo Run the agent service executable to begin enrollment.
pause
