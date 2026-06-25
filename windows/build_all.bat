@echo off
echo Building all XSI Agent components...
cd %~dp0

call build_service.bat
call build_tray.bat
call build_installer.bat

echo.
echo ========================================
echo Build complete.
echo Executables are in windows/dist/
echo ========================================
echo ========================================
