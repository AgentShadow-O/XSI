import os
import subprocess
import shutil
from pathlib import Path

# Requirements:
# pip install pyinstaller requests psutil pywin32 pystray Pillow

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = PROJECT_ROOT / "windows" / "dist"
ASSETS_DIR = PROJECT_ROOT / "windows" / "assets"

def build_exes():
    print("Building XSI Agent executables...")
    
    # Ensure dist and assets exist
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    version_service = PROJECT_ROOT / "windows" / "installer" / "version_info_service.txt"
    version_tray = PROJECT_ROOT / "windows" / "installer" / "version_info_tray.txt"

    # 1. Build Service
    print("-> Building XSI-Agent-Service.exe...")
    subprocess.run([
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--name", "XSI-Agent-Service",
        "--version-file", str(version_service),
        "--hidden-import", "win32timezone",
        "--distpath", str(DIST_DIR),
        str(PROJECT_ROOT / "windows" / "service" / "xsi_service.py")
    ], check=True)

    # 2. Build Tray
    print("-> Building XSI-Agent-Tray.exe...")
    subprocess.run([
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--name", "XSI-Agent-Tray",
        "--version-file", str(version_tray),
        "--distpath", str(DIST_DIR),
        str(PROJECT_ROOT / "windows" / "tray" / "tray_app.py")
    ], check=True)
    
    # 3. Copy Assets
    print("-> Packaging assets...")
    shutil.copytree(ASSETS_DIR, DIST_DIR / "assets", dirs_exist_ok=True)
    
    print(f"Build complete. Files located in: {DIST_DIR}")
    print("\nNext step: Open 'windows/installer/setup.iss' in Inno Setup and Compile (F9).")

if __name__ == "__main__":
    build_exes()
