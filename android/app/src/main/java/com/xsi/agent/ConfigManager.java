package com.xsi.agent;

import android.content.Context;
import android.content.SharedPreferences;

public class ConfigManager {
    private static final String PREF_NAME = "XSI_PREFS";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String KEY_AGENT_TOKEN = "agent_token";
    private static final String KEY_DEVICE_NAME = "device_name";
    private static final String KEY_DEVICE_ID = "device_id";

    private SharedPreferences prefs;

    public ConfigManager(Context context) {
        prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    public void saveConfig(String url, String token, String deviceName) {
        prefs.edit()
            .putString(KEY_SERVER_URL, url)
            .putString(KEY_AGENT_TOKEN, token)
            .putString(KEY_DEVICE_NAME, deviceName)
            .apply();
    }

    public String getServerUrl() { return prefs.getString(KEY_SERVER_URL, ""); }
    public String getAgentToken() { return prefs.getString(KEY_AGENT_TOKEN, ""); }
    public String getDeviceName() { return prefs.getString(KEY_DEVICE_NAME, ""); }
    
    public void setAgentToken(String token) { prefs.edit().putString(KEY_AGENT_TOKEN, token).apply(); }
    
    public void setDeviceId(String id) { prefs.edit().putString(KEY_DEVICE_ID, id).apply(); }
    public String getDeviceId() { return prefs.getString(KEY_DEVICE_ID, ""); }
}
