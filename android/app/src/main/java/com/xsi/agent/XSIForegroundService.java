package com.xsi.agent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.util.Log;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import androidx.core.app.NotificationCompat;
import java.util.Timer;
import java.util.TimerTask;

public class XSIForegroundService extends Service {
    private static final String CHANNEL_ID = "XSI_SERVICE_CHANNEL";
    private Timer timer;
    private XSIClient xsiClient;
    private ConfigManager configManager;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        configManager = new ConfigManager(this);
        xsiClient = new XSIClient(configManager);
        new Thread(() -> xsiClient.checkVersion()).start();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("XSI Agent Active")
                .setContentText("Monitoring endpoint security...")
                .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
                .build();

        startForeground(1, notification);

        startTelemetry();

        return START_STICKY;
    }

    private void startTelemetry() {
        if (timer != null) timer.cancel();
        timer = new Timer();
        timer.scheduleAtFixedRate(new TimerTask() {
            int iteration = 0;
            @Override
            public void run() {
                try {
                    // 1. Heartbeat every 30s
                    if (iteration % 3 == 0) {
                        xsiClient.sendHeartbeat(getHealthMetrics());
                    }
                    
                    // 2. Processes every 60s
                    if (iteration % 6 == 0) {
                        xsiClient.sendProcesses(getProcesses());
                    }
                    
                    // 3. Network every 60s
                    if (iteration % 6 == 3) {
                        xsiClient.sendNetwork(getNetworkActivity());
                    }
                    
                    iteration++;
                } catch (Exception e) {
                    Log.e("XSIService", "Telemetry error", e);
                }
            }
        }, 0, 10000); // Check every 10 seconds
    }

    private org.json.JSONObject getHealthMetrics() {
        org.json.JSONObject health = new org.json.JSONObject();
        try {
            android.os.BatteryManager bm = (android.os.BatteryManager) getSystemService(BATTERY_SERVICE);
            health.put("battery", bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY));
            
            android.net.ConnectivityManager cm = (android.net.ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            android.net.NetworkInfo ni = cm.getActiveNetworkInfo();
            health.put("network_type", ni != null ? ni.getTypeName() : "none");
            health.put("os_version", android.os.Build.VERSION.RELEASE);
        } catch (Exception ignored) {}
        return health;
    }

    private org.json.JSONArray getProcesses() {
        org.json.JSONArray arr = new org.json.JSONArray();
        try {
            // Placeholder: In real Android, this is restricted
            // We'd use UsageStatsManager or a native component
            org.json.JSONObject p = new org.json.JSONObject();
            p.put("pid", 1001);
            p.put("name", "com.xsi.agent");
            p.put("command_line", "android.process.xsi");
            arr.put(p);
        } catch (Exception ignored) {}
        return arr;
    }

    private org.json.JSONArray getNetworkActivity() {
        org.json.JSONArray arr = new org.json.JSONArray();
        try {
            org.json.JSONObject n = new org.json.JSONObject();
            n.put("ip", "1.1.1.1");
            n.put("port", 443);
            n.put("protocol", "TCP");
            n.put("direction", "outbound");
            arr.put(n);
        } catch (Exception ignored) {}
        return arr;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel serviceChannel = new NotificationChannel(
                    CHANNEL_ID,
                    "XSI Agent Service Channel",
                    NotificationManager.IMPORTANCE_LOW
            );
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(serviceChannel);
        }
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (timer != null) timer.cancel();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
