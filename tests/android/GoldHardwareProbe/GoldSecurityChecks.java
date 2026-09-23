/* SPDX-License-Identifier: Apache-2.0 */
package org.lineageos.gold.hardwareprobe;

import android.app.KeyguardManager;
import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyInfo;
import android.security.keystore.KeyProperties;
import org.json.JSONObject;
import org.json.JSONArray;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.SecureRandom;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.security.spec.ECGenParameterSpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

/** Ordinary application attestation. No IDs, certificates or boot key bytes are exported. */
final class GoldSecurityChecks {
    static final class Der {
        final int tagClass, tag;
        final byte[] body;
        Der(int c, int t, byte[] b) { tagClass=c;tag=t;body=b; }
        List<Der> children() throws Exception { return parse(body); }
        int number() { int n=0; for(byte b:body)n=(n<<8)|(b&255);return n; }
        static List<Der> parse(byte[] data) throws Exception {
            List<Der> list=new ArrayList<>(); int p=0;
            while(p<data.length) {
                int b=data[p++]&255, cls=b&192, t=b&31;
                if(t==31) {t=0;do{if(p>=data.length)throw new Exception("DER tag truncated");b=data[p++]&255;t=(t<<7)|(b&127);}while((b&128)!=0);}
                if(p>=data.length)throw new Exception("DER length truncated");
                int n=data[p++]&255;
                if((n&128)!=0){int count=n&127;n=0;if(count<1||count>4||p+count>data.length)throw new Exception("DER length invalid");while(count-->0)n=(n<<8)|(data[p++]&255);}
                if(n<0||n>data.length-p)throw new Exception("DER body truncated");
                list.add(new Der(cls,t,Arrays.copyOfRange(data,p,p+n)));p+=n;
            }
            return list;
        }
    }
    private static JSONObject attest(KeyStore store, boolean includeProperties) throws Exception {
        String alias="gold-owned-attestation-"+UUID.randomUUID();
        JSONObject r=new JSONObject().put("device_properties_requested",includeProperties);
        byte[] challenge=new byte[32];new SecureRandom().nextBytes(challenge);
        try {
            KeyPairGenerator generator=KeyPairGenerator.getInstance("EC","AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_SIGN|KeyProperties.PURPOSE_VERIFY)
                .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1")).setDigests(KeyProperties.DIGEST_SHA256)
                .setAttestationChallenge(challenge).setDevicePropertiesAttestationIncluded(includeProperties).build());
            KeyPair pair=generator.generateKeyPair();
            KeyInfo info=KeyFactory.getInstance("EC","AndroidKeyStore").getKeySpec(pair.getPrivate(),KeyInfo.class);
            Certificate[] chain=store.getCertificateChain(alias);
            if(chain==null||chain.length<2)throw new Exception("No attestation chain");
            for(int i=0;i<chain.length-1;i++)chain[i].verify(chain[i+1].getPublicKey());
            byte[] extension=((X509Certificate)chain[0]).getExtensionValue("1.3.6.1.4.1.11129.2.1.17");
            List<Der> fields=Der.parse(Der.parse(extension).get(0).body).get(0).children();
            if(fields.size()!=8||!Arrays.equals(fields.get(4).body,challenge))throw new Exception("attestation challenge mismatch");
            r.put("generated",true).put("chain_length",chain.length).put("chain_links_verified",true)
                .put("challenge_matches",true).put("keyinfo_security_level",info.getSecurityLevel())
                .put("attestation_security_level",fields.get(1).number()).put("keymint_security_level",fields.get(3).number());
            for(Der field:fields.get(7).children()) {
                if(field.tagClass==128&&field.tag==704) {
                    List<Der> root=field.children().get(0).children();
                    r.put("device_locked",root.get(1).number()!=0).put("verified_boot_state",root.get(2).number());
                }
            }
        } catch(Exception error) {
            r.put("generated",false);
            JSONArray errors=new JSONArray();
            for(Throwable e=error;e!=null;e=e.getCause())errors.put(e.getClass().getName()+": "+e.getMessage());
            r.put("errors",errors);
        } finally {
            if(store.containsAlias(alias))store.deleteEntry(alias);
            r.put("owned_key_deleted",!store.containsAlias(alias));
        }
        return r;
    }
    static JSONObject run(Context context) throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        boolean secure=context.getSystemService(KeyguardManager.class).isDeviceSecure();
        JSONObject r=new JSONObject().put("device_secure",secure);
        r.put("attestation",new JSONArray().put(attest(store,false)).put(attest(store,true)));
        // Do not create or replace the user's lock credential. A positive auth-bound test needs it.
        r.put("authentication_bound_test",secure?"requires_user_authentication_window":"not_run_no_secure_lock");
        return r;
    }
}
