/* SPDX-License-Identifier: Apache-2.0 */
package org.lineageos.gold.hardwareprobe;

import android.app.Activity;
import android.app.KeyguardManager;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.SystemClock;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyInfo;
import android.security.keystore.KeyProperties;
import android.security.keystore.UserNotAuthenticatedException;
import android.view.WindowManager;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.SecureRandom;
import java.security.Signature;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.security.spec.ECGenParameterSpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import javax.crypto.AEADBadTagException;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.GCMParameterSpec;

/** Owned, ordinary-app credential-bound keys. The system alone handles the credential. */
public final class GoldAuthActivity extends Activity {
    private static final int VALID_SECONDS = 15;
    private final JSONObject result = new JSONObject();
    private final List<String> aliases = new ArrayList<>();
    private final CountDownLatch authenticated = new CountDownLatch(1);
    private final CancellationSignal cancellation = new CancellationSignal();
    private volatile boolean accepted, destroyed;
    private volatile int authenticationType = -1, authenticationError = -1;
    private TextView label;
    private KeyStore store;
    private KeyPair ec;
    private SecretKey aes;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        setShowWhenLocked(true);
        setTurnScreenOn(true);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        label = new TextView(this);
        label.setTextSize(21);
        label.setPadding(32, 120, 32, 32);
        setContentView(label);
        new Thread(this::runTest, "GoldOwnedAuthKeys").start();
    }

    private static void check(boolean value, String error) throws Exception {
        if (!value) throw new Exception(error);
    }

    private void save(String name, String value) throws Exception {
        try (FileOutputStream stream = new FileOutputStream(new File(getFilesDir(), name))) {
            stream.write(value.getBytes(StandardCharsets.UTF_8));
            stream.getFD().sync();
        }
    }

    private void phase(String name, String text) throws Exception {
        save("auth-phase.txt", name);
        save("auth-progress.json", result.toString());
        runOnUiThread(() -> label.setText(text));
    }

    private String alias(String kind) {
        String value = "gold-owned-auth-" + kind + "-" + UUID.randomUUID();
        aliases.add(value);
        return value;
    }

    private JSONObject keyInfo(KeyInfo info) throws Exception {
        return new JSONObject().put("security_level", info.getSecurityLevel())
            .put("authentication_required", info.isUserAuthenticationRequired())
            .put("authentication_type", info.getUserAuthenticationType())
            .put("authentication_timeout_seconds", info.getUserAuthenticationValidityDurationSeconds())
            .put("authentication_enforced_by_secure_hardware", info.isUserAuthenticationRequirementEnforcedBySecureHardware());
    }

    private JSONObject attestation(String alias, byte[] challenge) throws Exception {
        Certificate[] chain = store.getCertificateChain(alias);
        check(chain != null && chain.length >= 2, "attestation chain missing");
        for (int i = 0; i < chain.length - 1; i++) chain[i].verify(chain[i+1].getPublicKey());
        byte[] ext = ((X509Certificate) chain[0]).getExtensionValue("1.3.6.1.4.1.11129.2.1.17");
        List<GoldSecurityChecks.Der> fields = GoldSecurityChecks.Der.parse(GoldSecurityChecks.Der.parse(ext).get(0).body).get(0).children();
        check(fields.size() == 8 && Arrays.equals(challenge, fields.get(4).body), "attestation challenge mismatch");
        JSONObject out = new JSONObject().put("chain_length", chain.length).put("chain_links_verified", true)
            .put("challenge_matches", true).put("attestation_security_level", fields.get(1).number())
            .put("keymint_security_level", fields.get(3).number()).put("trust_anchor_audited", false);
        for (int index : new int[] {6, 7}) {
            JSONObject list = new JSONObject();
            for (GoldSecurityChecks.Der field : fields.get(index).children()) {
                if (field.tagClass != 128) continue;
                if (field.tag == 503) list.put("no_auth_required", true);
                if (field.tag == 504) list.put("user_auth_type", field.children().get(0).number());
                if (field.tag == 505) list.put("auth_timeout_seconds", field.children().get(0).number());
                if (field.tag == 704) {
                    List<GoldSecurityChecks.Der> root = field.children().get(0).children();
                    list.put("device_locked", root.get(1).number() != 0).put("verified_boot_state", root.get(2).number());
                }
            }
            out.put(index == 6 ? "software_enforced" : "hardware_enforced", list);
        }
        return out;
    }

    private void createKeys() throws Exception {
        String ecAlias = alias("ec");
        byte[] challenge = new byte[32];
        new SecureRandom().nextBytes(challenge);
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC", "AndroidKeyStore");
        generator.initialize(new KeyGenParameterSpec.Builder(ecAlias, KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
            .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1")).setDigests(KeyProperties.DIGEST_SHA256)
            .setAttestationChallenge(challenge).setUserAuthenticationRequired(true)
            .setUserAuthenticationParameters(VALID_SECONDS, KeyProperties.AUTH_DEVICE_CREDENTIAL).build());
        ec = generator.generateKeyPair();
        result.put("ec_key", keyInfo(KeyFactory.getInstance("EC", "AndroidKeyStore").getKeySpec(ec.getPrivate(), KeyInfo.class)));
        result.put("ec_attestation", attestation(ecAlias, challenge));
        KeyGenerator symmetric = KeyGenerator.getInstance("AES", "AndroidKeyStore");
        symmetric.init(new KeyGenParameterSpec.Builder(alias("aes"), KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true).setUserAuthenticationParameters(VALID_SECONDS, KeyProperties.AUTH_DEVICE_CREDENTIAL).build());
        aes = symmetric.generateKey();
        result.put("aes_key", keyInfo((KeyInfo) SecretKeyFactory.getInstance("AES", "AndroidKeyStore").getKeySpec(aes, KeyInfo.class)));
    }

    private void signCheck() throws Exception {
        byte[] plain = "Gold owned credential-bound message".getBytes(StandardCharsets.UTF_8);
        Signature signer = Signature.getInstance("SHA256withECDSA");
        signer.initSign(ec.getPrivate()); signer.update(plain);
        byte[] signed = signer.sign();
        signer.initVerify(ec.getPublic()); signer.update(plain);
        check(signer.verify(signed), "EC verification failed");
        plain[0] ^= 1;
        signer.initVerify(ec.getPublic()); signer.update(plain);
        check(!signer.verify(signed), "EC accepted modified message");
    }

    private void aesCheck() throws Exception {
        byte[] plain = "Gold owned credential-bound AES".getBytes(StandardCharsets.UTF_8);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, aes);
        byte[] encrypted = cipher.doFinal(plain), iv = cipher.getIV();
        cipher.init(Cipher.DECRYPT_MODE, aes, new GCMParameterSpec(128, iv));
        check(Arrays.equals(plain, cipher.doFinal(encrypted)), "AES round trip failed");
        encrypted[encrypted.length - 1] ^= 1;
        cipher.init(Cipher.DECRYPT_MODE, aes, new GCMParameterSpec(128, iv));
        boolean rejected = false;
        try { cipher.doFinal(encrypted); } catch (AEADBadTagException expected) { rejected = true; }
        check(rejected, "AES accepted modified tag");
    }

    private boolean authenticationRejected(boolean asymmetric) throws Exception {
        try { if (asymmetric) signCheck(); else aesCheck(); }
        catch (Exception error) {
            for (Throwable cause = error; cause != null; cause = cause.getCause())
                if (cause instanceof UserNotAuthenticatedException) return true;
            throw error; // A provider crash or unrelated error is not an authentication rejection.
        }
        return false;
    }

    private void authenticate() {
        new BiometricPrompt.Builder(this).setTitle("Gold 密钥认证验证")
            .setSubtitle("请使用刚设置的锁屏凭据。密码只交给系统。")
            .setAllowedAuthenticators(BiometricManager.Authenticators.DEVICE_CREDENTIAL).build()
            .authenticate(cancellation, getMainExecutor(), new BiometricPrompt.AuthenticationCallback() {
                @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult auth) {
                    authenticationType = auth.getAuthenticationType(); accepted = true; authenticated.countDown();
                }
                @Override public void onAuthenticationError(int code, CharSequence message) {
                    authenticationError = code; authenticated.countDown();
                }
            });
    }

    private void runTest() {
        try {
            KeyguardManager keyguard = getSystemService(KeyguardManager.class);
            result.put("schema_version", 1).put("device_secure", keyguard.isDeviceSecure())
                .put("initially_device_locked", keyguard.isDeviceLocked()).put("credential_changed_by_probe", false);
            check(keyguard.isDeviceSecure(), "secure lock screen is required");
            store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
            createKeys();
            phase("waiting-for-initial-expiry", "正在确认认证前密钥不可用，约17秒。请等待系统认证提示。");
            SystemClock.sleep((VALID_SECONDS + 2) * 1000L);
            check(!destroyed, "activity closed");
            boolean ecBefore = authenticationRejected(true), aesBefore = authenticationRejected(false);
            result.put("before_authentication", new JSONObject().put("ec_rejected", ecBefore).put("aes_rejected", aesBefore));
            check(ecBefore && aesBefore, "key was usable before fresh authentication");
            phase("waiting-for-user-authentication", "请在系统窗口完成锁屏认证。");
            runOnUiThread(this::authenticate);
            check(authenticated.await(180, TimeUnit.SECONDS), "authentication prompt timed out");
            result.put("authentication_succeeded", accepted).put("authentication_type", authenticationType)
                .put("authentication_error", authenticationError);
            check(accepted && !destroyed, "authentication was not completed");
            long start = SystemClock.elapsedRealtime();
            signCheck(); aesCheck();
            result.put("after_authentication", new JSONObject().put("ec_sign_verify_tamper_rejection", true)
                .put("aes_gcm_round_trip_tamper_rejection", true).put("operations_elapsed_ms", SystemClock.elapsedRealtime() - start));
            phase("waiting-for-expiry", "认证后操作通过。正在确认15秒授权到期后密钥再次拒绝使用，请暂时不要再次解锁。");
            SystemClock.sleep((VALID_SECONDS + 2) * 1000L);
            boolean ecAfter = authenticationRejected(true), aesAfter = authenticationRejected(false);
            result.put("after_expiry", new JSONObject().put("ec_rejected", ecAfter).put("aes_rejected", aesAfter));
            check(ecAfter && aesAfter, "expired authentication still accepted");
            result.put("completed", true);
        } catch (Exception error) {
            try { result.put("completed", false).put("error_class", error.getClass().getName()).put("error", error.getMessage()); }
            catch (Exception ignored) { }
        } finally {
            runOnUiThread(cancellation::cancel);
            boolean deleted = true;
            for (String name : aliases) {
                try { store.deleteEntry(name); deleted &= !store.containsAlias(name); }
                catch (Exception error) { deleted = false; }
            }
            try {
                result.put("owned_keys_deleted", deleted).put("owned_key_count", aliases.size());
                save("auth-result.json", result.toString()); save("auth-phase.txt", "done");
            } catch (Exception error) { android.util.Log.e("GoldAuthProbe", "result save failed", error); }
            runOnUiThread(this::finish);
        }
    }

    @Override protected void onDestroy() {
        destroyed = true; cancellation.cancel(); authenticated.countDown(); super.onDestroy();
    }
}
