package com.xsi.agent;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    private EditText etServerUrl, etAgentToken, etDeviceName;
    private Button btnSave;
    private ConfigManager configManager;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        configManager = new ConfigManager(this);
        
        etServerUrl = findViewById(R.id.etServerUrl);
        etAgentToken = findViewById(R.id.etAgentToken);
        etDeviceName = findViewById(R.id.etDeviceName);
        btnSave = findViewById(R.id.btnSave);

        // Load existing config
        etServerUrl.setText(configManager.getServerUrl());
        etAgentToken.setText(configManager.getAgentToken());
        etDeviceName.setText(configManager.getDeviceName());

        btnSave.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String url = etServerUrl.getText().toString().trim();
                String token = etAgentToken.getText().toString().trim();
                String name = etDeviceName.getText().toString().trim();

                if (url.isEmpty()) {
                    Toast.makeText(MainActivity.this, "Server URL is required", Toast.LENGTH_SHORT).show();
                    return;
                }

                configManager.saveConfig(url, token, name);
                
                // Start the service
                Intent serviceIntent = new Intent(MainActivity.this, XSIForegroundService.class);
                startForegroundService(serviceIntent);

                Toast.makeText(MainActivity.this, "Agent Started", Toast.LENGTH_SHORT).show();
            }
        });
    }
}
