/* SPDX-License-Identifier: Apache-2.0 */
package org.lineageos.gold.hardwareprobe;

import android.app.Activity;
import android.content.Context;
import android.content.pm.ActivityInfo;
import android.content.res.Resources;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.Bundle;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyInfo;
import android.security.keystore.KeyProperties;
import android.view.Choreographer;
import android.view.Display;
import android.view.View;
import android.view.WindowManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import javax.crypto.AEADBadTagException;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.GCMParameterSpec;

/** Exercises only this disposable app's keys, generated view and window settings. */
public final class MainActivity extends Activity {
    private final JSONObject result = new JSONObject();
    private final ArrayList<String> aliases = new ArrayList<>();
    private KeyStore store;
    private ProbeView view;
    private volatile boolean cancelled;

    private final class ProbeView extends View {
        final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        String label = "Gold hardware validation";
        int frame;
        ProbeView() { super(MainActivity.this); }
        @Override protected void onDraw(Canvas canvas) {
            canvas.drawColor(Color.rgb(242, 246, 250));
            paint.setColor(Color.rgb(20, 40, 70));
            paint.setTextSize(42);
            canvas.drawText(label, 70, 220, paint);
            canvas.drawText("Only generated test content", 70, 285, paint);
            paint.setColor(Color.rgb(30, 140, 210));
            float x = 70 + (frame++ % 120) * Math.max(1, (getWidth() - 300) / 120f);
            canvas.drawRect(x, 350, x + 160, 510, paint);
        }
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        setShowWhenLocked(true);
        setTurnScreenOn(true);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        WindowManager.LayoutParams attr = getWindow().getAttributes();
        attr.screenBrightness = .35f;
        getWindow().setAttributes(attr);
        view = new ProbeView();
        setContentView(view);
        new Thread(this::runTests, "GoldOwnedHardwareTests").start();
    }

    private String alias(String kind) { String a = "gold-owned-" + kind + "-" + UUID.randomUUID(); aliases.add(a); return a; }
    private void write(String name, String text) throws Exception {
        try (FileOutputStream stream = new FileOutputStream(new File(getFilesDir(), name))) {
            stream.write(text.getBytes(StandardCharsets.UTF_8));
            stream.getFD().sync();
        }
    }
    private static void check(boolean value, String message) throws Exception {
        if (!value) throw new Exception(message);
    }

    private JSONObject sign(String algorithm) throws Exception {
        String name = alias(algorithm);
        KeyPairGenerator generator = KeyPairGenerator.getInstance(algorithm, "AndroidKeyStore");
        KeyGenParameterSpec.Builder spec = new KeyGenParameterSpec.Builder(name, KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
            .setDigests(KeyProperties.DIGEST_SHA256).setUserAuthenticationRequired(false);
        if (algorithm.equals("EC")) spec.setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"));
        else spec.setKeySize(2048).setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1);
        generator.initialize(spec.build());
        KeyPair pair = generator.generateKeyPair();
        KeyInfo info = KeyFactory.getInstance(algorithm, "AndroidKeyStore").getKeySpec(pair.getPrivate(), KeyInfo.class);
        byte[] message = "Gold disposable key test".getBytes(StandardCharsets.UTF_8);
        String type = algorithm.equals("EC") ? "SHA256withECDSA" : "SHA256withRSA";
        Signature signature = Signature.getInstance(type);
        signature.initSign(pair.getPrivate()); signature.update(message);
        byte[] signed = signature.sign();
        signature.initVerify(pair.getPublic()); signature.update(message);
        check(signature.verify(signed), "signature verification failed");
        message[0] ^= 1;
        signature.initVerify(pair.getPublic()); signature.update(message);
        check(!signature.verify(signed), "changed message verified");
        return new JSONObject().put("algorithm", algorithm).put("security_level", info.getSecurityLevel())
            .put("key_bits", info.getKeySize()).put("sign_verify_and_tamper_rejection", true);
    }

    private JSONObject aes() throws Exception {
        String name = alias("AES");
        KeyGenerator generator = KeyGenerator.getInstance("AES", "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(name, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(false).build());
        SecretKey key = generator.generateKey();
        KeyInfo info = (KeyInfo) SecretKeyFactory.getInstance("AES", "AndroidKeyStore").getKeySpec(key, KeyInfo.class);
        byte[] plain = "Gold owned AES data".getBytes(StandardCharsets.UTF_8);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key); byte[] encrypted = cipher.doFinal(plain), iv = cipher.getIV();
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        check(Arrays.equals(plain, cipher.doFinal(encrypted)), "AES roundtrip failed");
        encrypted[encrypted.length - 1] ^= 1;
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        boolean rejected = false;
        try { cipher.doFinal(encrypted); } catch (AEADBadTagException expected) { rejected = true; }
        check(rejected, "changed GCM tag was accepted");
        return new JSONObject().put("algorithm", "AES-GCM").put("security_level", info.getSecurityLevel())
            .put("key_bits", info.getKeySize()).put("encrypt_decrypt_and_tamper_rejection", true);
    }

    private void ui(Runnable operation) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        runOnUiThread(() -> { try { operation.run(); } finally { done.countDown(); } });
        check(done.await(5, TimeUnit.SECONDS), "UI operation timed out");
    }

    private JSONObject displayMode(Display.Mode requested) throws Exception {
        ui(() -> {
            WindowManager.LayoutParams attr = getWindow().getAttributes();
            attr.preferredDisplayModeId = requested.getModeId();
            attr.preferredRefreshRate = requested.getRefreshRate();
            getWindow().setAttributes(attr);
            view.label = "Display " + requested.getRefreshRate() + " Hz";
            view.invalidate();
        });
        Thread.sleep(1500);
        ArrayList<Long> times = new ArrayList<>();
        CountDownLatch done = new CountDownLatch(1);
        ui(() -> Choreographer.getInstance().postFrameCallback(new Choreographer.FrameCallback() {
            @Override public void doFrame(long nanos) {
                times.add(nanos); view.invalidate();
                if (!cancelled && times.size() < 91) Choreographer.getInstance().postFrameCallback(this);
                else done.countDown();
            }
        }));
        check(done.await(5, TimeUnit.SECONDS) && !cancelled, "display frame sampling interrupted");
        ArrayList<Long> deltas = new ArrayList<>();
        for (int i = 1; i < times.size(); ++i) deltas.add(times.get(i) - times.get(i - 1));
        Collections.sort(deltas);
        Display.Mode observed = getDisplay().getMode();
        return new JSONObject().put("requested_mode_id", requested.getModeId()).put("requested_hz", requested.getRefreshRate())
            .put("observed_mode_id", observed.getModeId()).put("observed_hz", observed.getRefreshRate())
            .put("vsync_samples", times.size()).put("median_vsync_hz", 1e9 / deltas.get(deltas.size() / 2))
            .put("mode_request_honored", requested.getModeId() == observed.getModeId());
    }

    private JSONObject dimensions() throws Exception {
        JSONObject values = new JSONObject();
        for (String pkg : new String[] {"android", "com.android.systemui"}) {
            Resources r = createPackageContext(pkg, 0).getResources();
            for (String name : new String[] {"rounded_corner_content_padding", "status_bar_padding_start", "status_bar_padding_end",
                    "status_bar_clock_starting_padding", "status_bar_icons_padding_end"}) {
                int id = r.getIdentifier(name, "dimen", pkg);
                if (id != 0) values.put(pkg + ":" + name, r.getDimension(id));
            }
        }
        return values;
    }

    private void runTests() {
        try {
            result.put("schema_version", 1);
            store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
            if ("security".equals(getIntent().getStringExtra("mode"))) {
                result.put("security", GoldSecurityChecks.run(this)).put("completed", true);
                return;
            }
            JSONArray crypto = new JSONArray();
            crypto.put(sign("EC")); crypto.put(sign("RSA")); crypto.put(aes());
            result.put("keystore", crypto);
            JSONArray display = new JSONArray();
            for (Display.Mode mode : getDisplay().getSupportedModes()) {
                if (mode.getPhysicalWidth() == 1080 && mode.getPhysicalHeight() == 2400) display.put(displayMode(mode));
            }
            result.put("display", display);
            result.put("density", getResources().getDisplayMetrics().density);
            result.put("effective_dimensions_px", dimensions());
            for (int orientation : new int[] {ActivityInfo.SCREEN_ORIENTATION_PORTRAIT, ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE}) {
                String label = orientation == ActivityInfo.SCREEN_ORIENTATION_PORTRAIT ? "portrait" : "landscape";
                ui(() -> { setRequestedOrientation(orientation); view.label = "Layout " + label; view.invalidate(); });
                Thread.sleep(1500); write("phase.txt", label); Thread.sleep(4000);
            }
            result.put("completed", true);
        } catch (Exception error) {
            try { result.put("completed", false).put("error", error.getClass().getName() + ": " + error.getMessage()); }
            catch (Exception ignored) {}
        } finally {
            boolean removed = true;
            for (String name : aliases) {
                try { store.deleteEntry(name); removed &= !store.containsAlias(name); }
                catch (Exception error) { removed = false; }
            }
            try {
                result.put("owned_keys_deleted", removed).put("owned_key_count", aliases.size());
                write("result.json", result.toString()); write("phase.txt", "done");
            } catch (Exception error) { android.util.Log.e("GoldHardwareProbe", "save failed", error); }
            runOnUiThread(this::finish);
        }
    }

    @Override protected void onDestroy() { cancelled = true; super.onDestroy(); }
}
