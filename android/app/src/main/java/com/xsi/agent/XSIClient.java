package com.xsi.agent;

import android.util.Log;
import android.os.Build;
import org.json.JSONObject;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.TimeZone;

public class XSIClient {
    private static final String TAG = "XSIClient";
    private ConfigManager config;

    public XSIClient(ConfigManager config) {
        this.config = config;
    }

    public void sendHeartbeat(JSONObject health) {
        String serverUrl = config.getServerUrl();
        String token = config.getAgentToken();
        String deviceId = config.getDeviceId();
        
        if (serverUrl.isEmpty() || token.isEmpty()) return;
        if (deviceId.isEmpty()) {
            register();
            return;
        }

        try {
            URL url = new URL(serverUrl + "/api/agents/heartbeat");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            JSONObject json = new JSONObject();
            json.put("device_id", deviceId);
            json.put("status", "online");
            json.put("token", token);
            json.put("agent_version", "0.4.0");
            json.put("health", health);
            
            addAuthHeaders(conn, json.toString(), token);

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = json.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }

            int code = conn.getResponseCode();
            Log.d(TAG, "Heartbeat response: " + code);
            if (code == 401) {
                Log.w(TAG, "Unauthorized heartbeat. Retrying registration.");
                config.setAgentToken("");
                register();
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Heartbeat failed", e);
        }
    }

    public void sendProcesses(org.json.JSONArray processes) {
        String serverUrl = config.getServerUrl();
        String token = config.getAgentToken();
        String deviceId = config.getDeviceId();
        if (deviceId.isEmpty()) return;

        try {
            URL url = new URL(serverUrl + "/api/agents/processes");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            JSONObject json = new JSONObject();
            json.put("device_id", deviceId);
            json.put("token", token);
            json.put("processes", processes);
            
            addAuthHeaders(conn, json.toString(), token);

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = json.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }
            conn.getResponseCode();
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Process telemetry failed", e);
        }
    }

    public void sendNetwork(org.json.JSONArray activity) {
        String serverUrl = config.getServerUrl();
        String token = config.getAgentToken();
        String deviceId = config.getDeviceId();
        if (deviceId.isEmpty()) return;

        try {
            URL url = new URL(serverUrl + "/api/agents/network");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            JSONObject json = new JSONObject();
            json.put("device_id", deviceId);
            json.put("token", token);
            json.put("activity", activity);
            
            addAuthHeaders(conn, json.toString(), token);

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = json.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }
            conn.getResponseCode();
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Network telemetry failed", e);
        }
    }

    public void register() {
        Log.i(TAG, "Enrollment started");
        String serverUrl = config.getServerUrl();
        String token = config.getAgentToken();
        if (token == null || token.isEmpty()) {
            Log.e(TAG, "Enrollment token is required");
            return;
        }
        String name = config.getDeviceName();
        if (name.isEmpty()) name = Build.MODEL;

        try {
            URL url = new URL(serverUrl + "/api/agents/register");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSXXX");
            sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
            String timestamp = sdf.format(new Date());
            
            String deviceId = "xsi-" + name.toLowerCase().replaceAll("[^a-z0-9]", "");
            String message = deviceId + timestamp;
            String signature = "";
            if (token != null && !token.isEmpty()) {
                Mac mac = Mac.getInstance("HmacSHA256");
                SecretKeySpec secretKey = new SecretKeySpec(token.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
                mac.init(secretKey);
                byte[] hash = mac.doFinal(message.getBytes(StandardCharsets.UTF_8));
                StringBuilder hexString = new StringBuilder();
                for (byte b : hash) {
                    String hex = Integer.toHexString(0xff & b);
                    if(hex.length() == 1) hexString.append('0');
                    hexString.append(hex);
                }
                signature = hexString.toString();
            }

            JSONObject json = new JSONObject();
            json.put("device_id", deviceId);
            json.put("device_name", name);
            json.put("device_type", "mobile");
            json.put("os", "Android");
            json.put("hostname", name);
            json.put("platform", "Android");
            json.put("version", Build.VERSION.RELEASE);
            json.put("agent_version", "0.4.0");
            json.put("token", token);
            json.put("timestamp", timestamp);
            json.put("signature", signature);
            
            // Only add headers for non-registration requests typically, but we still need Content-Type
            // For registration, we removed addAuthHeaders and just use the payload fields.

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = json.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }

            int code = conn.getResponseCode();
            if (code == 200) {
                java.io.InputStream is = conn.getInputStream();
                java.util.Scanner s = new java.util.Scanner(is).useDelimiter("\\A");
                String resp = s.hasNext() ? s.next() : "";
                JSONObject resJson = new JSONObject(resp);
                config.setDeviceId(resJson.optString("endpoint_id", resJson.optString("device_id")));
                if (resJson.has("session_token")) {
                    config.setAgentToken(resJson.getString("session_token"));
                }
                
                String enrollmentStatus = resJson.optString("enrollment_status", "");
                int nextInterval = resJson.optInt("next_heartbeat_interval", 30);
                Log.i(TAG, "Enrollment successful: status=" + enrollmentStatus + ", next_interval=" + nextInterval);
                
                // Explicitly send heartbeat after successful registration
                sendHeartbeat(new JSONObject());
            } else {
                Log.e(TAG, "Enrollment failed: HTTP " + code);
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Enrollment failed", e);
        }
    }
    
    private void addAuthHeaders(HttpURLConnection conn, String payload, String token) throws Exception {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSXXX");
        sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
        String timestamp = sdf.format(new Date());

        conn.setRequestProperty("X-Agent-Timestamp", timestamp);
        conn.setRequestProperty("X-Device-Id", config.getDeviceId());
        
        if (token != null && !token.isEmpty()) {
            conn.setRequestProperty("Authorization", "Bearer " + token);
            String message = timestamp + payload;
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec secretKey = new SecretKeySpec(token.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
            mac.init(secretKey);
            byte[] hash = mac.doFinal(message.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if(hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            conn.setRequestProperty("X-Agent-Signature", hexString.toString());
        }
    }

    public void checkVersion() {
        String serverUrl = config.getServerUrl();
        if (serverUrl.isEmpty()) return;
        try {
            URL url = new URL(serverUrl + "/api/agents/version");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Accept", "application/json");

            int code = conn.getResponseCode();
            if (code == 200) {
                java.io.InputStream is = conn.getInputStream();
                java.util.Scanner s = new java.util.Scanner(is).useDelimiter("\\A");
                String resp = s.hasNext() ? s.next() : "";
                JSONObject resJson = new JSONObject(resp);
                String currentVersion = resJson.optString("current_agent_version", "");
                if (!currentVersion.isEmpty() && !currentVersion.equals("0.4.0")) {
                    Log.w(TAG, "Agent version is outdated. Current server version: " + currentVersion + ", Local version: 0.4.0");
                } else {
                    Log.i(TAG, "Agent version is up to date.");
                }
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Failed to check version", e);
        }
    }
}
