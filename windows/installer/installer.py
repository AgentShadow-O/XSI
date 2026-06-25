import os
import sys
import shutil
import json
import subprocess
from pathlib import Path
import ctypes
import argparse
import time

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    parser = argparse.ArgumentParser(description="XSI Agent Installer")
    parser.add_argument("--server", type=str, default=os.getenv("XSI_SERVER_URL", ""), help="Backend Server URL")
    parser.add_argument("--token", type=str, default=os.getenv("XSI_AGENT_TOKEN", ""), help="Enrollment Token")
    args = parser.parse_args()

    if not args.server:
        print("Error: --server or XSI_SERVER_URL is required.")
        time.sleep(3)
        sys.exit(1)

    if not is_admin():
        print("Elevating privileges...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    print("XSI Agent Installer")
    print("===================")
    
    install_dir = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "XSI Agent"
    data_dir = Path(os.environ.get("ProgramData", "C:\\ProgramData")) / "XSI"
    config_dir = data_dir / "config"
    config_path = config_dir / "agent.json"
    
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Failed to create directories: {e}")
        time.sleep(3)
        sys.exit(1)
        
    if hasattr(sys, '_MEIPASS'):
        bundle_dir = Path(sys._MEIPASS)
    else:
        bundle_dir = Path(__file__).parent.parent / "dist"

    src_service = bundle_dir / "XSI-Agent-Service.exe"
    src_tray = bundle_dir / "XSI-Agent-Tray.exe"
        
    if not src_service.exists():
        print(f"Error: {src_service} not found. Cannot proceed.")
        time.sleep(3)
        sys.exit(1)
        
    target_service = install_dir / "XSI-Agent-Service.exe"
    target_tray = install_dir / "XSI-Agent-Tray.exe"
    
    print("Stopping existing service if running...")
    subprocess.run(["sc", "stop", "XSI Agent"], capture_output=True)
    time.sleep(2)
    subprocess.run([str(target_service), "remove"], capture_output=True)
    time.sleep(1)
    
    print(f"Copying files to {install_dir}...")
    try:
        shutil.copy2(src_service, target_service)
        if src_tray.exists():
            shutil.copy2(src_tray, target_tray)
    except Exception as e:
        print(f"Failed to copy executable: {e}")
        time.sleep(3)
        sys.exit(1)
        
    print("Configuring agent...")
    config = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            config = {}
    config.update({
        "server": config.get("server") or args.server,
        "enrollment_token": config.get("enrollment_token") or args.token,
        "has_initial_scan": bool(config.get("has_initial_scan", False))
    })
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
            
    print("Registering Windows Service...")
    subprocess.run([str(target_service), "install"], capture_output=True)
    
    subprocess.run(["sc", "failure", "XSI Agent", "actions=", "restart/60000/restart/60000/restart/60000", "reset=", "86400"], capture_output=True)
    subprocess.run(["sc", "config", "XSI Agent", "start=", "auto"], capture_output=True)
    
    print("Starting service...")
    subprocess.run(["sc", "start", "XSI Agent"], capture_output=True)
    
    print("Installation complete! The agent is running in the background.")
    time.sleep(2)

if __name__ == "__main__":
    main()
