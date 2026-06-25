import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bell,
  Download,
  Gauge,
  Globe2,
  KeyRound,
  ListFilter,
  LogOut,
  MonitorDot,
  Network,
  Plus,
  Radio,
  Settings,
  Shield,
  User,
} from "lucide-react";
import "./styles.css";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const WS_URL = (import.meta.env.VITE_WS_URL || (API_URL ? API_URL.replace(/^http/, "ws") + "/ws" : "")).replace(/\/$/, "");

if (!API_URL) {
  console.warn("VITE_API_URL is not configured");
}

const nav = [
  ["Dashboard", Gauge],
  ["SIEM", ListFilter],
  ["Events", Activity],
  ["Alerts", Bell],
  ["Endpoints", MonitorDot],
  ["Network", Network],
  ["IPS", Shield],
  ["Deployment", Download],
  ["Settings", Settings],
];

async function get(path, token = "") {
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

async function post(path, payload, headers = {}, token = "") {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function App() {
  const [page, setPage] = useState("Dashboard");
  const [refreshSignal, setRefreshSignal] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [summary, setSummary] = useState({});
  const [devices, setDevices] = useState([]);
  const [live, setLive] = useState([]);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [performanceMode, setPerformanceMode] = useState(() => localStorage.getItem("xsi_perf_mode") || "Balanced");
  const [auth, setAuth] = useState(() => ({
    accessToken: localStorage.getItem("xsi_access_token") || "",
    refreshToken: localStorage.getItem("xsi_refresh_token") || "",
    user: null,
  }));
  const [authReady, setAuthReady] = useState(false);
  const [deviceCenter, setDeviceCenter] = useState(null);
  const [deviceTab, setDeviceTab] = useState("Overview");

  useEffect(() => {
    localStorage.setItem("xsi_perf_mode", performanceMode);
    document.body.className = performanceMode === "Low Resource" ? "perf-low" : "";
  }, [performanceMode]);

  useEffect(() => {
    if (!API_URL || !auth.accessToken) return;

    let timer;
    async function poll() {
      try {
        await refreshBase();
      } finally {
        const interval = performanceMode === "Low Resource" ? 30000 : performanceMode === "High Performance" ? 5000 : 10000;
        timer = setTimeout(poll, interval);
      }
    }
    poll();
    return () => clearTimeout(timer);
  }, [auth.accessToken, performanceMode]);

  useEffect(() => {
    if (!API_URL || !auth.accessToken) {
      setAuthReady(true);
      return;
    }
    get("/api/auth/me", auth.accessToken)
      .then((data) => setAuth((prev) => ({ ...prev, user: data.user })))
      .catch(() => clearAuth())
      .finally(() => setAuthReady(true));
  }, []);

  useEffect(() => {
    if (!WS_URL || !auth.accessToken) return;

    let socket;
    let reconnectTimer;
    let attempt = 0;

    function connect() {
      const separator = WS_URL.includes("?") ? "&" : "?";
      const token = auth.accessToken;
      const url = token ? `${WS_URL}${separator}token=${encodeURIComponent(token)}` : WS_URL;
      
      socket = new WebSocket(url);
      
      socket.onopen = () => {
        attempt = 0;
      };

      socket.onmessage = (message) => {
        const item = JSON.parse(message.data);
        setLive((prev) => [item, ...prev].slice(0, 50));
        if (item.type === "DEVICE_STATUS") {
          setDevices((prev) => {
            const next = [...prev];
            const idx = next.findIndex((device) => device.device_id === item.device_id);
            if (idx >= 0) {
              next[idx] = { ...next[idx], status: item.status, last_seen: item.last_seen };
            }
            return next;
          });
        }
        if (item.type === "NEW_ALERT" && item.event) {
          setRecentAlerts((prev) => [item.event, ...prev].slice(0, 50));
        }
      };

      socket.onclose = () => {
        const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
        attempt++;
        reconnectTimer = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
  }, [auth.accessToken]);

  async function refreshBase() {
    try {
      const [s, d, a] = await Promise.all([
        get("/api/summary", auth.accessToken),
        get("/api/devices", auth.accessToken),
        get("/api/alerts?limit=50", auth.accessToken),
      ]);
      setSummary(s);
      setDevices(d.items || []);
      setRecentAlerts(a.items || []);
    } catch (err) {
      console.error("Base refresh failed", err);
    }
  }

  async function refresh() {
    setIsRefreshing(true);
    try {
      await refreshBase();
      setRefreshSignal((prev) => prev + 1);
      setLastUpdated(new Date());
    } catch (err) {
      alert("Refresh failed: " + err.message);
    } finally {
      setIsRefreshing(false);
    }
  }

  function saveAuth(data) {
    localStorage.setItem("xsi_access_token", data.access_token);
    localStorage.setItem("xsi_refresh_token", data.refresh_token || auth.refreshToken || "");
    setAuth({ accessToken: data.access_token, refreshToken: data.refresh_token || auth.refreshToken || "", user: data.user || auth.user });
  }

  async function clearAuth() {
    if (auth.accessToken) {
      try {
        await post("/api/auth/logout", {}, {}, auth.accessToken);
      } catch { }
    }
    localStorage.removeItem("xsi_access_token");
    localStorage.removeItem("xsi_refresh_token");
    setAuth({ accessToken: "", refreshToken: "", user: null });
  }

  if (!authReady) {
    return <div className="auth-shell"><div className="auth-panel"><Shield size={28} /><strong>XSI</strong></div></div>;
  }

  if (!auth.accessToken) {
    return <AuthScreen onAuth={saveAuth} />;
  }

  return (
    <div className="shell">
      <aside>
        <div className="brand"><Shield size={22} /> XSI</div>
        {nav.map(([name, Icon]) => (
          <button className={page === name ? "active" : ""} key={name} onClick={() => setPage(name)}>
            <Icon size={18} /> {name}
          </button>
        ))}
        <div className="perf-selector">
          <label>Performance</label>
          <select value={performanceMode} onChange={(e) => setPerformanceMode(e.target.value)}>
            <option>High Performance</option>
            <option>Balanced</option>
            <option>Low Resource</option>
          </select>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <h1>{page}</h1>
            <span>{auth.user ? `${auth.user.username} / ${auth.user.role}` : API_URL ? "Connected" : "Configuration required"}</span>
          </div>
          <div className="header-actions">
            {lastUpdated && <span className="last-updated" style={{marginRight: '1rem', fontSize: '0.9em', opacity: 0.8}}>Last updated: {lastUpdated.toLocaleTimeString()}</span>}
            <button onClick={refresh} title="Refresh Base Data" disabled={isRefreshing}>
              <Activity size={18} /> {isRefreshing ? "Refreshing..." : "Refresh"}
            </button>
            <button onClick={clearAuth}><LogOut size={18} /> Logout</button>
          </div>
        </header>
        {page === "Dashboard" && <Dashboard summary={summary} live={live} alerts={recentAlerts} devices={devices} />}
        {page === "SIEM" && <SIEM auth={auth} devices={devices} refreshSignal={refreshSignal} />}
        {page === "Events" && <EventsPage auth={auth} refreshSignal={refreshSignal} />}
        {page === "Alerts" && <AlertsPage auth={auth} refreshSignal={refreshSignal} />}
        {page === "Endpoints" && <Endpoints auth={auth} devices={devices} onRefresh={refreshBase} onOpenDevice={openDevice} setPage={setPage} refreshSignal={refreshSignal} />}
        {page === "Device" && <DeviceCenter auth={auth} data={deviceCenter} setData={setDeviceCenter} tab={deviceTab} setTab={setDeviceTab} refreshSignal={refreshSignal} />}
        {page === "Network" && <NetworkPage auth={auth} refreshSignal={refreshSignal} />}
        {page === "IPS" && <IPSPage auth={auth} refreshSignal={refreshSignal} />}
        {page === "Deployment" && <DeploymentPage auth={auth} />}
        {page === "Settings" && <SettingsPage auth={auth} refreshSignal={refreshSignal} />}
      </main>
    </div>
  );

  async function openDevice(deviceId) {
    const data = await get(`/api/devices/${encodeURIComponent(deviceId)}/command-center`, auth.accessToken);
    setDeviceCenter(data);
    setDeviceTab("Overview");
    setPage("Device");
  }
}

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", password: "", device_name: "Dashboard" });
  const [error, setError] = useState("");

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const path = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      const data = await post(path, form);
      onAuth(data);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-panel" onSubmit={submit}>
        <div className="auth-brand"><Shield size={28} /> <strong>XSI</strong></div>
        <div className="auth-tabs">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Login</button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
        </div>
        <label><User size={16} /><input value={form.username} onChange={(e) => update("username", e.target.value)} placeholder="Username" required /></label>
        <label><KeyRound size={16} /><input type="password" value={form.password} onChange={(e) => update("password", e.target.value)} placeholder="Password" minLength={10} required /></label>
        <input value={form.device_name} onChange={(e) => update("device_name", e.target.value)} placeholder="Device name" />
        <button type="submit">{mode === "register" ? "Create Account" : "Login"}</button>
        {error && <p className="auth-error">{error}</p>}
      </form>
    </div>
  );
}

function Dashboard({ summary, live, alerts, devices }) {
  const critical = alerts.filter((alert) => Number(alert.risk_score || 0) >= 80).length;
  return (
    <>
      <section className="metrics">
        <Metric label="Threat Score" value={summary.threat_score ?? 0} />
        <Metric label="Active Alerts" value={summary.active_alerts ?? 0} />
        <Metric label="Critical Alerts" value={critical} />
        <Metric label="Live Events" value={summary.event_count ?? 0} />
        <Metric label="Device Health" value={`${summary.online_devices ?? devices.filter((d) => d.status === "online").length}/${devices.length} online`} />
      </section>
      <section className="grid two">
        <Panel title="Live Events (Last 50)" rows={live} />
        <Panel title="Recent Alerts (Last 50)" rows={alerts} />
      </section>
    </>
  );
}

function EventsPage({ auth, refreshSignal }) {
  const [rows, setRows] = useState([]);
  const [query, setQuery] = useState("");
  useEffect(() => {
    get(`/api/events?limit=200&search=${encodeURIComponent(query)}`, auth.accessToken).then(d => setRows(d.items || []));
  }, [query, auth.accessToken, refreshSignal]);

  return (
    <>
      <input className="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter events by keyword or device ID..." />
      <Table rows={rows} columns={["timestamp", "device_id", "source", "event_type", "severity", "risk_score"]} />
    </>
  );
}

function SIEM({ auth, devices, refreshSignal }) {
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({ search: "", device_id: "", source: "", severity: "" });

  useEffect(() => {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.device_id) params.set("device_id", filters.device_id);
    if (filters.source) params.set("source", filters.source);
    if (filters.severity) params.set("severity", filters.severity);
    get(`/api/events?limit=500&${params.toString()}`, auth.accessToken).then((data) => setRows(data.items || []));
  }, [filters, auth.accessToken, refreshSignal]);

  return (
    <div className="siem">
      <div className="filters">
        <input value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} placeholder="Search details..." />
        <select value={filters.device_id} onChange={(e) => setFilters({ ...filters, device_id: e.target.value })}>
          <option value="">All Devices</option>
          {devices.map((d) => <option key={d.device_id} value={d.device_id}>{d.device_name || d.device_id}</option>)}
        </select>
        <select value={filters.source} onChange={(e) => setFilters({ ...filters, source: e.target.value })}>
          <option value="">All Sources</option>
          <option value="xsi">XSI</option>
          <option value="edr">EDR</option>
          <option value="ids">IDS</option>
        </select>
        <select value={filters.severity} onChange={(e) => setFilters({ ...filters, severity: e.target.value })}>
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
          <option value="safe">Safe</option>
        </select>
      </div>
      <Table rows={rows} columns={["timestamp", "device_id", "source", "event_type", "severity", "risk_score", "mitre_attack", "ioc_matched"]} />
    </div>
  );
}

function AlertsPage({ auth, refreshSignal }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    get("/api/alerts?limit=200", auth.accessToken).then(d => setRows(d.items || []));
  }, [auth.accessToken, refreshSignal]);
  return <Table rows={rows} columns={["timestamp", "device_id", "severity", "risk_score", "title"]} rowClass={(row) => riskClass(row.risk_score)} />;
}

function Endpoints({ auth, devices, onRefresh, onOpenDevice, setPage, refreshSignal }) {
  const [processes, setProcesses] = useState([]);
  useEffect(() => {
    get("/api/processes?limit=100", auth.accessToken).then(d => setProcesses(d.items || []));
  }, [auth.accessToken, refreshSignal]);

  return (
    <>
      <section className="deploy-cta glass">
        <div>
          <h2>Deploy New Agent</h2>
          <p>Protect more devices by deploying the XSI professional agent.</p>
        </div>
        <button className="primary" onClick={() => setPage("Deployment")}><Download size={18} /> Open Deployment Wizard</button>
      </section>
      <section className="grid two">
        <div className="panel-col">
          <h2>Registered Devices</h2>
          <Table rows={devices} columns={["device_name", "os", "agent_version", "status", "last_seen"]} rowClass={(row) => row.status === "online" ? "row-online" : row.status === "removed" ? "row-removed" : "row-offline"} onRowClick={(row) => onOpenDevice(row.device_id)} />
        </div>
        <div className="panel-col">
          <h2>Active Processes (Recent)</h2>
          <Table rows={processes} columns={["device_id", "pid", "name", "risk_score", "last_seen"]} />
        </div>
      </section>
    </>
  );
}

function DeviceCenter({ auth, data, setData, tab, setTab, refreshSignal }) {
  if (!data) return <section><h2>Device Center</h2><p>Select a device from Endpoints</p></section>;
  const tabs = ["Overview", "Alerts", "Processes", "Network", "Logs", "XDR", "IPS", "Settings"];
  const device = data.device || {};
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  async function refreshDevice() {
    setIsRefreshing(true);
    try {
      const updated = await get(`/api/devices/${encodeURIComponent(device.device_id)}/command-center`, auth.accessToken);
      setData(updated);
    } catch (err) {
      alert("Refresh failed: " + err.message);
    } finally {
      setIsRefreshing(false);
    }
  }

  useEffect(() => {
    refreshDevice();
  }, [refreshSignal]);

  useEffect(() => {
    const timer = setInterval(refreshDevice, 10000);
    return () => clearInterval(timer);
  }, [device.device_id, auth.accessToken]);

  async function removeDevice() {
    if (!confirm("Remove this endpoint from XSI?")) return;
    try {
      await fetch(`${API_URL}/api/agents/${encodeURIComponent(device.device_id)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${auth.accessToken}` },
      });
      alert("Device removed.");
      // Trigger a refresh globally
      setData(prev => ({...prev, device: {...prev.device, status: "removed"}}));
    } catch (err) {
      alert("Failed to remove device: " + err.message);
    }
  }

  const rows = {
    Alerts: data.alerts || [],
    Processes: data.processes || [],
    Network: data.network || [],
    Logs: data.logs || [],
    XDR: data.xdr || [],
    IPS: data.ips || [],
  };
  return (
    <>
      <section className="device-hero">
        <div>
          <h2>{device.device_name || device.device_id}</h2>
          <span>{device.device_id} / {device.os} {device.version}</span>
        </div>
        <div className="device-status-actions">
          <strong className={device.status === "online" ? "status-online" : device.status === "removed" ? "status-removed" : "status-offline"}>{device.status || "unknown"}</strong>
          <button className="mini" onClick={refreshDevice} disabled={isRefreshing}>
            <Activity size={14} /> {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button className="mini danger" onClick={removeDevice} disabled={device.status === "removed"}>
            Remove Device
          </button>
        </div>
      </section>
      <div className="tabs">{tabs.map((name) => <button className={tab === name ? "active" : ""} key={name} onClick={() => setTab(name)}>{name}</button>)}</div>
      {tab === "Overview" && (
        <section className="metrics">
          <Metric label="Alerts" value={data.overview.alert_count} />
          <Metric label="Events" value={data.overview.event_count} />
          <Metric label="Processes" value={data.overview.process_count} />
          <Metric label="Network" value={data.overview.network_count} />
          <Metric label="Actions" value={data.overview.action_count} />
        </section>
      )}
      {tab === "Alerts" && <Table rows={rows.Alerts} columns={["timestamp", "device_id", "severity", "risk_score", "title"]} rowClass={(row) => riskClass(row.risk_score)} />}
      {tab === "Processes" && <Table rows={rows.Processes} columns={["device_id", "pid", "name", "command_line", "risk_score", "last_seen"]} />}
      {tab === "Network" && <Table rows={rows.Network} columns={["device_id", "ip", "port", "protocol", "direction", "risk_score", "last_seen"]} />}
      {tab === "Logs" && <Table rows={rows.Logs} columns={["timestamp", "device_id", "source", "event_type", "severity", "risk_score"]} />}
      {tab === "XDR" && <Table rows={rows.XDR} columns={["timestamp", "device_id", "source", "event_type", "severity", "risk_score"]} />}
      {tab === "IPS" && <Table rows={rows.IPS} columns={["timestamp", "device_id", "action", "target", "status"]} />}
      {tab === "Settings" && <pre className="json">{JSON.stringify(data.settings, null, 2)}</pre>}
    </>
  );
}

function NetworkPage({ auth, refreshSignal }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    get("/api/network?limit=200", auth.accessToken).then(d => setRows(d.items || []));
  }, [auth.accessToken, refreshSignal]);
  return <Table rows={rows} columns={["device_id", "ip", "port", "protocol", "direction", "risk_score", "last_seen"]} />;
}

function IPSPage({ auth, refreshSignal }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    get("/api/actions?limit=200", auth.accessToken).then(d => setRows(d.items || []));
  }, [auth.accessToken, refreshSignal]);
  return <Table rows={rows} columns={["timestamp", "device_id", "action", "target", "status"]} />;
}

function DeploymentPage({ auth }) {
  const [platform, setPlatform] = useState(null);
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState({ 
    server: API_URL || window.location.origin, 
    token: "", 
    device_name: "" 
  });

  function reset() {
    setPlatform(null);
    setStep(1);
  }

  if (!platform) {
    return (
      <section className="deployment-start fade-in">
        <div className="hero-text">
          <h1>XSI Agent Deployment</h1>
          <p>Deploy professional-grade endpoint protection across your infrastructure.</p>
        </div>
        <div className="platform-grid">
          <button className="platform-card glass" onClick={() => setPlatform("Windows")}>
            <div className="platform-icon windows"><MonitorDot size={48} /></div>
            <strong>Windows Agent</strong>
            <span>Workstations & Servers</span>
            <ul className="mini-features">
              <li>✓ Windows Service</li>
              <li>✓ System Tray</li>
              <li>✓ Auto Start</li>
            </ul>
          </button>
          <button className="platform-card glass" onClick={() => setPlatform("Android")}>
            <div className="platform-icon android"><Radio size={48} /></div>
            <strong>Android Agent</strong>
            <span>Mobile Endpoints</span>
            <ul className="mini-features">
              <li>✓ Background Service</li>
              <li>✓ Real-time Alerts</li>
              <li>✓ Secure Heartbeat</li>
            </ul>
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="deployment-wizard fade-in">
      <div className="wizard-header">
        <button className="back-link" onClick={reset}>← Back to Platforms</button>
        <h2>{platform} Agent Setup</h2>
        <div className="steps-indicator">
          <div className={step >= 1 ? "active" : ""}>1. Configure</div>
          <div className={step >= 2 ? "active" : ""}>2. Download</div>
        </div>
      </div>

      <div className="wizard-body glass">
        {step === 1 && (
          <div className="step-content slide-in">
            <h3>Configuration</h3>
            <p className="step-desc">Enter your server details to pre-configure the agent for secure communication.</p>
            
            <div className="field-group">
              <label>Server URL</label>
              <input value={config.server} onChange={(e) => setConfig({ ...config, server: e.target.value })} placeholder="https://xsi.example.com" />
            </div>
            
            <div className="field-group">
              <label>Agent Token</label>
              <input value={config.token} onChange={(e) => setConfig({ ...config, token: e.target.value })} />
              <span className="hint">Required for secure authentication with the backend.</span>
            </div>
            
            <div className="field-group">
              <label>Device Name (Optional)</label>
              <input value={config.device_name} onChange={(e) => setConfig({ ...config, device_name: e.target.value })} placeholder="e.g. Finance-PC-01" />
            </div>

            <div className="form-actions">
              <button className="primary big" onClick={() => setStep(2)}>Continue to Download</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="step-content success-view slide-in">
            <div className="success-header">
              <Shield size={64} className="success-icon" />
              <h3>Ready for Deployment</h3>
              <p>Download the pre-configured installer and run it on your {platform} device.</p>
            </div>

            <div className="installer-info glass">
              <div className="installer-main">
                <Download size={32} />
                <div>
                  <strong>{platform === "Windows" ? "XSI-Agent-Setup.exe" : "XSI-Agent.apk"}</strong>
                  <span>Professional {platform} Installer</span>
                </div>
              </div>
              <ul className="feature-list">
                {platform === "Windows" ? (
                  <>
                    <li>✓ Windows Service</li>
                    <li>✓ System Tray</li>
                    <li>✓ Auto Start</li>
                    <li>✓ Secure Connection</li>
                  </>
                ) : (
                  <>
                    <li>✓ Background Service</li>
                    <li>✓ Persistence on Boot</li>
                    <li>✓ Secure Heartbeat</li>
                    <li>✓ Native Integration</li>
                  </>
                )}
              </ul>
            </div>

            <div className="form-actions">
              <a 
                className="download-btn primary big" 
                href={`${API_URL}/api/agents/${platform.toLowerCase()}/download`} 
                download
              >
                <Download size={20} /> Download {platform} {platform === "Windows" ? "Installer" : "Agent"}
              </a>
              <button className="secondary" onClick={reset}>Finish</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}


function SettingsPage({ auth, refreshSignal }) {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get("/api/settings/system", auth.accessToken)
      .then((data) => {
        setSettings(data.value || {});
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [auth.accessToken, refreshSignal]);

  async function save() {
    try {
      await post("/api/settings/system", { key: "system", value: settings }, {}, auth.accessToken);
      alert("Settings saved successfully");
    } catch (err) {
      alert("Failed to save settings: " + err.message);
    }
  }

  if (loading) return <section><h2>Settings</h2><p>Loading system configuration...</p></section>;

  return (
    <section className="settings-form">
      <div className="field-group">
        <label>Notification Email</label>
        <input value={settings.email || ""} onChange={(e) => setSettings({...settings, email: e.target.value})} placeholder="admin@example.com" />
        <span className="hint">Alerts will be sent to this address if enabled.</span>
      </div>
      <div className="field-group">
        <label>Log Retention (Days)</label>
        <input type="number" value={settings.retention || 30} onChange={(e) => setSettings({...settings, retention: parseInt(e.target.value)})} />
        <span className="hint">Events older than this will be automatically archived.</span>
      </div>
      <div className="field-group">
        <label>Detection Sensitivity</label>
        <select value={settings.sensitivity || "balanced"} onChange={(e) => setSettings({...settings, sensitivity: e.target.value})}>
          <option value="low">Low (Fewer Alerts)</option>
          <option value="balanced">Balanced</option>
          <option value="high">High (Maximum Visibility)</option>
        </select>
      </div>
      <div className="form-actions">
        <button className="primary" onClick={save}><Settings size={18} /> Update Configuration</button>
      </div>
    </section>
  );
}

function Metric({ label, value }) {
  return <article><span>{label}</span><strong>{value}</strong></article>;
}

function Panel({ title, rows }) {
  return (
    <section>
      <h2>{title}</h2>
      <Table rows={rows} columns={["timestamp", "device_id", "event_type", "severity", "risk_score"]} compact />
    </section>
  );
}

function Table({ rows, columns, compact = false, rowClass = () => "", onRowClick = null }) {
  const [limit, setLimit] = useState(compact ? 10 : 50);
  const visibleRows = useMemo(() => (rows || []).slice(0, limit), [rows, limit]);

  return (
    <div className="table-container">
      <div className="table">
        <table>
          <thead><tr>{columns.map((col) => <th key={col}>{col}</th>)}</tr></thead>
          <tbody>
            {visibleRows.map((row, idx) => (
              <tr className={`${rowClass(row)} ${onRowClick ? "clickable" : ""}`} key={row.id || idx} onClick={() => onRowClick && onRowClick(row)}>
                {columns.map((col) => <td key={col} data-label={col}>{String(row[col] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows && rows.length > limit && (
        <div className="table-footer">
          <button className="load-more" onClick={() => setLimit(limit + 50)}>Load More ({rows.length - limit} remaining)</button>
        </div>
      )}
    </div>
  );
}

function riskClass(score) {
  const value = Number(score || 0);
  if (value >= 80) return "row-critical";
  if (value >= 50) return "row-warning";
  return "";
}

createRoot(document.getElementById("root")).render(<App />);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });
}
