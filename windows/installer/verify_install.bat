@echo off
echo =========================================
echo XSI Agent Installation Verification
echo =========================================
echo.

set AGENT_EXE="%~dp0..\dist\XSI-Agent-Service.exe"

if not exist %AGENT_EXE% (
    echo [ERROR] Agent executable not found at %AGENT_EXE%.
    echo Please run build_service.bat first.
    exit /b 1
)

echo Running Agent Self-Test...
echo.
%AGENT_EXE% --self-test
echo.
echo Verification Complete.
pause
