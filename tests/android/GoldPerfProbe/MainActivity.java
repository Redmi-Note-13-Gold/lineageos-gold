/* SPDX-License-Identifier: Apache-2.0 */
package org.lineageos.gold.perfprobe;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Color;
import android.os.BatteryManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;
import android.view.FrameMetrics;
import android.view.Window;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

/** An owned, synthetic scrolling workload; no network or user-data permissions. */
public final class MainActivity extends Activity {
    private final Object lock = new Object();
    private final ArrayList<long[]> frames = new ArrayList<>();
    private final ArrayList<long[]> battery = new ArrayList<>();
    private final Handler main = new Handler();
    private HandlerThread worker;
    private Handler sampleHandler;
    private BatteryManager batteryManager;
    private long createdNs, durationMs;
    private int droppedCallbacks;
    private String sample;
    private boolean saved;
    private float refreshRate;
    private final Window.OnFrameMetricsAvailableListener frameListener = (window, metrics, dropped) -> {
        synchronized (lock) {
            droppedCallbacks += dropped;
            if (!saved && frames.size() < 12000) {
                frames.add(new long[] {metrics.getMetric(FrameMetrics.INTENDED_VSYNC_TIMESTAMP),
                        metrics.getMetric(FrameMetrics.TOTAL_DURATION),
                        metrics.getMetric(FrameMetrics.DEADLINE),
                        metrics.getMetric(FrameMetrics.FIRST_DRAW_FRAME)});
            }
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        createdNs = SystemClock.elapsedRealtimeNanos();
        sample = getIntent().getStringExtra("sample");
        durationMs = getIntent().getIntExtra("duration_ms", 15000);
        if (sample == null || !sample.matches("[A-Za-z0-9_-]{1,60}")
                || durationMs < 2500 || durationMs > 90000) {
            finish();
            return;
        }
        // Show only this test's generated content above the keyguard. This does
        // not unlock the device or expose any other app or personal content.
        setShowWhenLocked(true);
        setTurnScreenOn(true);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        WindowManager.LayoutParams attributes = getWindow().getAttributes();
        attributes.screenBrightness = 0.35f;
        getWindow().setAttributes(attributes);
        refreshRate = getDisplay().getMode().getRefreshRate();
        worker = new HandlerThread("GoldPerfMetrics");
        worker.start();
        sampleHandler = new Handler(worker.getLooper());
        batteryManager = (BatteryManager) getSystemService(Context.BATTERY_SERVICE);
        getWindow().addOnFrameMetricsAvailableListener(frameListener, sampleHandler);

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setBackgroundColor(Color.WHITE);
        Button stop = new Button(this);
        stop.setText("结束性能测试");
        stop.setOnClickListener(view -> end("user_cancelled"));
        content.addView(stop);
        for (int i = 0; i < 250; ++i) {
            TextView row = new TextView(this);
            row.setText("Sample " + i + "\n固定的滚动测试内容，测试结束后自动返回。");
            row.setTextSize(16);
            row.setTextColor(Color.rgb(30, 40, 50));
            int padding = (int) (16 * getResources().getDisplayMetrics().density + 0.5f);
            row.setPadding(padding, padding, padding, padding);
            content.addView(row);
        }
        ScrollView scroll = new ScrollView(this);
        scroll.addView(content);
        setContentView(scroll);
        scroll.post(this::reportFullyDrawn);
        sampleHandler.post(new Runnable() {
            @Override public void run() {
                synchronized (lock) {
                    if (saved) return;
                    sampleBattery();
                }
                sampleHandler.postDelayed(this, 1000);
            }
        });
        main.postDelayed(() -> end("completed"), durationMs);
    }

    private void sampleBattery() {
        Intent status = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (status == null) return;
        battery.add(new long[] {SystemClock.elapsedRealtimeNanos(),
                batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER),
                batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW),
                status.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
                status.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1),
                status.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1)});
    }

    private void save(String reason) {
        synchronized (lock) {
            if (saved || worker == null) return;
            sampleBattery();
            saved = true;
            try {
                JSONObject result = new JSONObject();
                result.put("schema_version", 1);
                result.put("sample", sample);
                result.put("reason", reason);
                result.put("created_elapsed_ns", createdNs);
                result.put("ended_elapsed_ns", SystemClock.elapsedRealtimeNanos());
                result.put("requested_duration_ms", durationMs);
                result.put("window_brightness", 0.35);
                result.put("initial_refresh_hz", refreshRate);
                result.put("dropped_frame_callbacks", droppedCallbacks);
                result.put("frame_columns", new JSONArray(new String[] {
                        "intended_vsync_ns", "total_duration_ns", "deadline_ns", "first_draw"}));
                JSONArray frameRows = new JSONArray();
                for (long[] row : frames) frameRows.put(new JSONArray(row));
                result.put("frames", frameRows);
                result.put("battery_columns", new JSONArray(new String[] {
                        "elapsed_ns", "charge_uah", "current_ua", "voltage_mv", "temperature_decic", "plugged"}));
                JSONArray batteryRows = new JSONArray();
                for (long[] row : battery) batteryRows.put(new JSONArray(row));
                result.put("battery", batteryRows);
                File output = new File(getFilesDir(), sample + ".json");
                try (FileOutputStream stream = new FileOutputStream(output)) {
                    stream.write(result.toString().getBytes(StandardCharsets.UTF_8));
                    stream.getFD().sync();
                }
            } catch (Exception error) {
                android.util.Log.e("GoldPerfProbe", "Cannot save sample", error);
            }
        }
    }

    private void end(String reason) {
        save(reason);
        finish();
    }

    @Override public void onDestroy() {
        main.removeCallbacksAndMessages(null);
        save("destroyed_before_deadline");
        if (worker != null) {
            getWindow().removeOnFrameMetricsAvailableListener(frameListener);
            worker.quitSafely();
        }
        super.onDestroy();
    }
}
