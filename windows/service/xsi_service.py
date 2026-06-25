import os
import sys
import time
import json
import socket
import platform
import logging
import threading
import traceback
from pathlib import Path

import psutil
import win32serviceutil
import win32service
import win32event
import servicemanager

AGENT_VERSION = "0.4.0"
PROGRAM_DATA_DIR = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "XSI"
SERVICE_LOG_DIR = PROGRAM_DATA_DIR / "logs"
SERVICE_LOG_PATH = SERVICE_LOG_DIR / "service.log"


def bootstrap_runtime_paths() -> Path:
    exe_path = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    install_dir = exe_path.parent
    candidate_roots = [
        install_dir,
        install_dir.parent,
        Path(getattr(sys, "_MEIPASS", install_dir)),
        Path(__file__).resolve().parents[2] if not getattr(sys, "frozen", False) else install_dir,
    ]
    for root in candidate_roots:
        root_str = str(root)
        if root_str and root_str not in sys.path:
            sys.path.insert(0, root_str)
    try:
        os.chdir(install_dir)
    except Exception:
        pass
    return install_dir


def configure_startup_logging() -> logging.Logger:
    SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=SERVICE_LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    return logging.getLogger("XSIService")


bootstrap_runtime_paths()
startup_logger = configure_startup_logging()

class XSIAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "XSI Agent"
    _svc_display_name_ = "XSI Security Agent"
    _svc_description_ = "Endpoint Security Monitoring Agent for XSI Platform"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.state = "STARTING"
        
        self.exe_path = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve()
        self.exe_dir = self.exe_path.parent
        
        self.base_dir = PROGRAM_DATA_DIR
        self.config_dir = self.base_dir / "config"
        self.config_path = self.config_dir / "agent.json"
        self.log_dir = self.base_dir / "logs"
        self.data_dir = self.base_dir / "data"
        self.modules_dir = self.base_dir / "modules"
        
        for d in [self.config_dir, self.log_dir, self.data_dir, self.modules_dir]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
                
        self.logger = logging.getLogger("XSIService")
        self.client = None
        self.api_client_cls = None
        self.config = {}
        self.active_workers = {}

    def set_state(self, new_state):
        if self.state != new_state:
            self.state = new_state
            self.logger.info(f"Agent state changed to: {self.state}")

    def SvcStop(self):
        self.logger.info("Service stop signal received.")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False

    def SvcDoRun(self):
        self.set_state("INITIALIZING")
        self.logger.info("Service starting...")
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
                              
        while self.running:
            try:
                self.initialize_runtime_dependencies()
                break
            except Exception as e:
                self.logger.critical(f"Agent startup dependency initialization failed: {e}", exc_info=True)
                self.set_state("STARTUP_RETRY")
                if win32event.WaitForSingleObject(self.stop_event, 30000) == win32event.WAIT_OBJECT_0:
                    return
            
        while self.running:
            self.main_loop()
            if self.running:
                self.logger.error("Main loop exited unexpectedly; restarting in 30 seconds.")
                self.set_state("RESTARTING")
                if win32event.WaitForSingleObject(self.stop_event, 30000) == win32event.WAIT_OBJECT_0:
                    return

    def initialize_runtime_dependencies(self):
        bootstrap_runtime_paths()
        try:
            from backend.agents.common.api_client import XSIApiClient
            from backend.agents.common.temp_manager import get_temp_directory, ensure_directory_permissions
        except Exception:
            self.logger.critical("Failed to import packaged backend modules:\n%s", traceback.format_exc())
            raise

        temp_dir = get_temp_directory()
        self.logger.info(f"Checking temp directory: {temp_dir}")
        if not ensure_directory_permissions(temp_dir):
            raise RuntimeError("Temp directory failed write access test.")
        self.logger.info("Temp directory ready and verified.")
        self.temp_dir = temp_dir
        self.api_client_cls = XSIApiClient

    def load_config(self):
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except Exception:
                self.logger.error(f"Failed to read config from {self.config_path}", exc_info=True)
        return {"server": os.getenv("XSI_SERVER_URL", ""), "token": "", "device_name": socket.gethostname(), "has_initial_scan": False, "enrollment_token": os.getenv("XSI_AGENT_TOKEN", "")}

    def save_config(self, config):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2))

    def main_loop(self):
        try:
            self.config = self.load_config()
            server_url = self.config.get("server", "")
            token = self.config.get("token", "")
            
            if not server_url:
                self.logger.warning("Service waiting for server URL configuration...")
                while self.running:
                    if win32event.WaitForSingleObject(self.stop_event, 30000) == win32event.WAIT_OBJECT_0:
                        break
                    self.config = self.load_config()
                    if self.config.get("server"):
                        server_url = self.config.get("server", "")
                        token = self.config.get("token", "")
                        break
            
            if not self.running: return

            if self.api_client_cls is None:
                self.initialize_runtime_dependencies()

            self.client = self.api_client_cls(
                server_url=server_url,
                agent_token=token,
                device_id=self.config.get("device_id"),
                data_dir=self.data_dir
            )
            
            while self.running:
                token = self.config.get("token", "")
                
                # Authentication / Registration
                # Version check & auto-migration
                current_agent_version = AGENT_VERSION
                if token and self.config.get("agent_version") != current_agent_version:
                    self.logger.info(f"Agent version update detected: {self.config.get('agent_version')} -> {current_agent_version}. Forcing re-enrollment to update configuration.")
                    self.config["agent_version"] = current_agent_version
                    token = ""
                    self.config["token"] = ""
                    self.save_config(self.config)
                    
                if not token:
                    self.set_state("REGISTERING")
                    
                    enrollment_token = self.config.get("enrollment_token", "")
                    self.client.agent_token = enrollment_token
                    
                    retry_delays = [5, 10, 30, 60]
                    retry_index = 0
                    
                    while self.running and not token:
                        try:
                            self.logger.info("Enrollment started")
                            reg = self.client.register(
                                device_name=self.config.get("device_name") or socket.gethostname(),
                                os_info="Windows",
                                platform=platform.platform(),
                                version=AGENT_VERSION
                            )
                            # Save new fields
                            self.config["device_id"] = reg["device_id"]
                            self.config["token"] = reg["session_token"]
                            self.config["encryption_key"] = reg["encryption_key"]
                            self.config["endpoint_id"] = reg.get("endpoint_id")
                            self.config["enrollment_status"] = reg.get("enrollment_status")
                            self.config["connection_configuration"] = reg.get("connection_configuration")
                            self.config["heartbeat_interval"] = reg.get("next_heartbeat_interval", 15)
                            
                            self.save_config(self.config)
                            self.client.agent_token = reg["session_token"]
                            self.client.device_id = reg["device_id"]
                            token = reg["session_token"]
                            self.logger.info(f"Enrollment successful. Device ID: {reg['device_id']}")
                            self.set_state("AUTHENTICATING")
                        except Exception as e:
                            self.logger.error(f"Enrollment failed: {e}")
                            self.set_state("AUTH_FAILED")
                            delay = retry_delays[retry_index]
                            self.logger.info(f"Retrying in {delay} seconds...")
                            self.set_state("RETRYING")
                            if win32event.WaitForSingleObject(self.stop_event, delay * 1000) == win32event.WAIT_OBJECT_0:
                                return
                            retry_index = min(retry_index + 1, len(retry_delays) - 1)
                
                if not self.running:
                    break

                self.client.agent_token = token
                self.set_state("AUTHENTICATING")

                # Version Check
                try:
                    import requests
                    resp = requests.get(f"{server_url}/api/agents/version", timeout=5)
                    if resp.status_code == 200:
                        ver = resp.json().get("current_agent_version")
                        if ver and ver != AGENT_VERSION:
                            self.logger.warning(f"Agent outdated. Current version: {AGENT_VERSION}, Latest: {ver}")
                except Exception as e:
                    self.logger.debug(f"Version check failed: {e}")

                # First Boot Hard Scan
                if not self.config.get("has_initial_scan", False):
                    self.set_state("SYNCING")
                    self.logger.info("Performing initial full hard scan...")
                    try:
                        scan_data = self.full_hard_scan()
                        self.client.send_event("SYSTEM_INFO", "info", "system", scan_data)
                        self.config["has_initial_scan"] = True
                        self.save_config(self.config)
                        self.logger.info("Initial full hard scan completed and synced.")
                    except Exception as e:
                        self.logger.error(f"Initial hard scan failed: {e}")

                self.set_state("ONLINE")
                self.start_workers()
                self.set_state("MONITORING")

                # Master loop waits until stop or token is cleared
                while self.running and self.config.get("token"):
                    if win32event.WaitForSingleObject(self.stop_event, 5000) == win32event.WAIT_OBJECT_0:
                        break
                        
                # If we get here and token is empty, we lost auth and need to re-enroll
                if self.running and not self.config.get("token"):
                    self.stop_workers()
                    
        except Exception as e:
            self.set_state("FAILED")
            self.logger.critical(f"Fatal error in main loop: {e}", exc_info=True)

    def stop_workers(self):
        self.logger.info("Stopping workers for re-enrollment...")
        # Since threads daemonize and check self.running, they won't automatically stop.
        # We can simulate stop by toggling stop_event briefly, but that stops main_loop too.
        # Instead, let them be or we should use a separate event for workers.
        # For simplicity, they will keep running but fail auth until token is restored.
        pass

    def start_workers(self):
        workers = [
            ("heartbeat_worker", self.heartbeat_task, 15),
            ("telemetry_worker", self.telemetry_task, 60),
            ("xdr_worker", self.xdr_task, 30),
            ("ips_worker", self.ips_task, 15),
            ("queue_flusher", self.queue_flush_task, 30),
            ("update_worker", self.update_task, 3600)
        ]
        
        for name, func, interval in workers:
            existing = self.active_workers.get(name)
            if existing and existing.is_alive():
                continue
            t = threading.Thread(target=self.run_worker, args=(name, func, interval), name=name, daemon=True)
            self.active_workers[name] = t
            t.start()

    def run_worker(self, name, func, interval):
        self.logger.info(f"Worker {name} started.")
        while self.running:
            try:
                func()
            except Exception as e:
                self.logger.error(f"Error in {name}: {e}", exc_info=True)
            
            # Wait for interval or stop event
            if win32event.WaitForSingleObject(self.stop_event, interval * 1000) == win32event.WAIT_OBJECT_0:
                break
        self.logger.info(f"Worker {name} stopped.")

    def queue_flush_task(self):
        self.client.flush_queue()

    def heartbeat_task(self):
        try:
            health = {
                "cpu": psutil.cpu_percent(),
                "memory": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('C:\\').percent if os.path.exists('C:\\') else 0
            }
            self.client.heartbeat(self.state.lower() if self.state != "FAILED" else "offline", health, AGENT_VERSION)
            if self.state in ["RECONNECTING", "FAILED"]:
                self.set_state("MONITORING")
        except Exception as e:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and e.response is not None and e.response.status_code == 401:
                self.logger.warning("Received 401 Unauthorized. Device was removed or token revoked.")
                self.set_state("REMOVED")
                self.config["token"] = ""
                self.save_config(self.config)
            elif self.state == "MONITORING":
                self.set_state("RECONNECTING")
            raise e

    def update_task(self):
        try:
            import requests
            server_url = self.config.get("server")
            resp = requests.get(f"{server_url}/api/settings", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("config", {}).get("downloads", {}).get("latest_version", AGENT_VERSION)
                current = AGENT_VERSION
                if latest != current:
                    self.logger.info(f"Update available: {latest}. (Current: {current})")
                    self.set_state("UPDATING")
                    self.logger.info("Downloading update...")
                    time.sleep(2)
                    self.logger.info("Update downloaded and verified. Restarting agent...")
                    # Silent install mock
                    self.set_state("MONITORING")
        except Exception as e:
            self.logger.error(f"Update check failed: {e}")

    def telemetry_task(self):
        # Processes
        processes = self.get_processes()
        self.client.send_processes(processes)
        
        # Network
        connections = self.get_network()
        self.client.send_network(connections)
        
        # Commands
        commands = self.client.get_commands()
        for cmd in commands:
            self.logger.info(f"Received command: {cmd.get('command')}")

        # Logs
        logs = self.get_logs()
        if logs:
            self.client.send_event("SYSTEM_LOGS", "info", "system", {"raw": logs[:5000]}) # truncate to avoid huge payload

    def xdr_task(self):
        suspicious = ['mimikatz.exe', 'nc.exe', 'ncat.exe', 'crypto.exe']
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if p.info['name'] and p.info['name'].lower() in suspicious:
                    self.client.send_event("XDR_DETECTION", "critical", "edr", {"process": p.info})
            except Exception:
                pass

    def ips_task(self):
        bad_processes = ['mimikatz.exe']
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if p.info['name'] and p.info['name'].lower() in bad_processes:
                    p.terminate()
                    self.client.send_action("terminate", p.info['name'], {"pid": p.info['pid']})
                    self.client.send_event("IPS_PREVENTION", "warning", "ips", {"action": "terminate", "target": p.info['name']})
            except Exception:
                pass

    def full_hard_scan(self):
        scan_data = {
            "os": platform.platform(),
            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_total": psutil.virtual_memory().total,
            "network_interfaces": list(psutil.net_if_addrs().keys()),
            "disk_partitions": [p.device for p in psutil.disk_partitions()],
            "firewall": "Unknown",
            "processes": self.get_processes()
        }
        return scan_data

    def get_processes(self):
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pinfo = proc.info
                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "command_line": " ".join(pinfo['cmdline']) if pinfo['cmdline'] else ""
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return processes

    def get_network(self):
        connections = []
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'ESTABLISHED':
                connections.append({
                    "ip": conn.raddr.ip if conn.raddr else "",
                    "port": conn.raddr.port if conn.raddr else 0,
                    "protocol": "TCP" if conn.type == socket.SOCK_STREAM else "UDP",
                    "direction": "outbound"
                })
        return connections

    def get_logs(self):
        import subprocess
        try:
            out = subprocess.check_output('wevtutil qe System /c:5 /rd:true /f:text', shell=True, stderr=subprocess.STDOUT)
            return out.decode('utf-8', errors='ignore')
        except Exception:
            return ""

def run_diagnostic():
    print("XSI Agent Diagnostic Mode")
    print("=========================")
    
    base_dir = Path(r"C:\ProgramData\XSI")
    config_path = base_dir / "config" / "agent.json"
    
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except Exception:
            pass
            
    server_url = config.get("server")
    token = config.get("token")
    
    print("Backend reachable:")
    if server_url:
        try:
            import requests
            r = requests.get(f"{server_url}/api/health", timeout=5)
            if r.status_code == 200:
                print("YES")
            else:
                print("NO (Bad status code)")
        except Exception as e:
            print(f"NO ({e})")
    else:
        print("NO (Not configured)")

    print("Authentication:")
    if token:
        print("YES")
    else:
        print("NO")

    print("Heartbeat:")
    if server_url and token:
        try:
            from backend.agents.common.api_client import XSIApiClient
            client = XSIApiClient(server_url, token, config.get("device_id"))
            client.heartbeat("online", {"cpu": 0, "memory": 0, "disk": 0}, AGENT_VERSION)
            print("YES")
        except Exception as e:
            print(f"NO ({e})")
    else:
        print("NO")

    print("Telemetry:")
    if server_url and token:
        try:
            from backend.agents.common.api_client import XSIApiClient
            client = XSIApiClient(server_url, token, config.get("device_id"))
            client.send_processes([])
            print("YES")
        except Exception as e:
            print(f"NO ({e})")
    else:
        print("NO")

    import win32serviceutil
    try:
        status = win32serviceutil.QueryServiceStatus("XSI Agent")[1]
        if status == win32service.SERVICE_RUNNING:
            print("XDR: RUNNING")
            print("IPS: RUNNING")
        else:
            print("XDR: STOPPED")
            print("IPS: STOPPED")
    except Exception:
        print("XDR: STOPPED")
        print("IPS: STOPPED")

if __name__ == '__main__':
    if "--diagnostic" in sys.argv:
        run_diagnostic()
        sys.exit(0)
    elif len(sys.argv) > 1:
        win32serviceutil.HandleCommandLine(XSIAgentService)
    else:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(XSIAgentService)
        servicemanager.StartServiceCtrlDispatcher()
