/* SPDX-License-Identifier: Apache-2.0 */
import android.hardware.security.keymint.KeyParameter;
import android.hardware.security.keymint.SecurityLevel;
import android.hardware.security.keymint.Tag;
import android.os.SystemProperties;
import android.security.KeyStore2;
import android.security.KeyStoreException;
import android.security.KeyStoreSecurityLevel;
import android.hardware.security.keymint.KeyParameterValue;
import android.system.keystore2.Domain;
import android.system.keystore2.KeyDescriptor;
import android.system.keystore2.KeyMetadata;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import javax.security.auth.x500.X500Principal;

/** Test only the five current non-unique attestation properties; never modify provisioning. */
public final class GoldAttestationParameters {
    private static final String[] NAMES = {"brand", "device", "name", "manufacturer", "model"};
    private static final int[] TAGS = {Tag.ATTESTATION_ID_BRAND, Tag.ATTESTATION_ID_DEVICE,
        Tag.ATTESTATION_ID_PRODUCT, Tag.ATTESTATION_ID_MANUFACTURER, Tag.ATTESTATION_ID_MODEL};
    private static final class Der {
        final int cls, tag; final byte[] body;
        Der(int c, int t, byte[] b) { cls=c; tag=t; body=b; }
        List<Der> children() throws Exception { return parse(body); }
        int number() { int n=0; for(byte b:body)n=(n<<8)|(b&255);return n; }
        static List<Der> parse(byte[] data) throws Exception {
            List<Der> list=new ArrayList<>();int p=0;
            while(p<data.length) {
                int b=data[p++]&255,c=b&192,t=b&31;
                if(t==31){t=0;do{if(p>=data.length)throw new Exception("truncated tag");b=data[p++]&255;t=(t<<7)|(b&127);}while((b&128)!=0);}
                if(p>=data.length)throw new Exception("truncated length");int n=data[p++]&255;
                if((n&128)!=0){int count=n&127;n=0;if(count<1||count>4||p+count>data.length)throw new Exception("invalid length");while(count-->0)n=(n<<8)|(data[p++]&255);}
                if(n<0||n>data.length-p)throw new Exception("truncated body");list.add(new Der(c,t,Arrays.copyOfRange(data,p,p+n)));p+=n;
            }return list;
        }
    }
    private static KeyParameter parameter(int tag, KeyParameterValue value) {
        KeyParameter p=new KeyParameter();p.tag=tag;p.value=value;return p;
    }
    private static JSONObject generate(KeyStore2 store, KeyStoreSecurityLevel level, int mask, boolean platform) throws Exception {
        KeyDescriptor descriptor = new KeyDescriptor();descriptor.domain=Domain.APP;descriptor.nspace=-1;
        descriptor.alias="gold-owned-property-probe-"+UUID.randomUUID();
        JSONObject result=new JSONObject().put("mask",mask).put("property_source",platform?"current_platform":"current_attestation");JSONArray requested=new JSONArray();
        List<KeyParameter> parameters=new ArrayList<>();
        parameters.add(parameter(Tag.ALGORITHM,KeyParameterValue.algorithm(3)));
        parameters.add(parameter(Tag.KEY_SIZE,KeyParameterValue.integer(256)));
        parameters.add(parameter(Tag.EC_CURVE,KeyParameterValue.ecCurve(1)));
        parameters.add(parameter(Tag.PURPOSE,KeyParameterValue.keyPurpose(2)));
        parameters.add(parameter(Tag.PURPOSE,KeyParameterValue.keyPurpose(3)));
        parameters.add(parameter(Tag.DIGEST,KeyParameterValue.digest(4)));
        parameters.add(parameter(Tag.NO_AUTH_REQUIRED,KeyParameterValue.boolValue(true)));
        parameters.add(parameter(Tag.CERTIFICATE_SERIAL,KeyParameterValue.blob(BigInteger.ONE.toByteArray())));
        parameters.add(parameter(Tag.CERTIFICATE_SUBJECT,KeyParameterValue.blob(new X500Principal("CN=Gold owned diagnostic").getEncoded())));
        parameters.add(parameter(Tag.CERTIFICATE_NOT_BEFORE,KeyParameterValue.dateTime(0)));
        parameters.add(parameter(Tag.CERTIFICATE_NOT_AFTER,KeyParameterValue.dateTime(System.currentTimeMillis()+3600000)));
        byte[] challenge=new byte[32];new SecureRandom().nextBytes(challenge);
        parameters.add(parameter(Tag.ATTESTATION_CHALLENGE,KeyParameterValue.blob(challenge)));
        byte[][] expected=new byte[5][];
        for(int i=0;i<5;i++)if((mask&(1<<i))!=0){
            String value=SystemProperties.get("ro.product."+NAMES[i]+"_for_attestation");
            if(value.isEmpty()||value.equals("unknown"))value=SystemProperties.get("ro.product.vendor."+NAMES[i]);
            if(value.isEmpty()||value.equals("unknown"))value=SystemProperties.get("ro.product."+NAMES[i]);
            if(platform)value=SystemProperties.get("ro.product."+NAMES[i]);
            if(value.isEmpty())throw new Exception("current property missing");
            expected[i]=value.getBytes(StandardCharsets.UTF_8);requested.put(NAMES[i]);
            parameters.add(parameter(TAGS[i],KeyParameterValue.blob(expected[i])));
        }
        result.put("requested_properties",requested);
        try {
            KeyMetadata metadata=level.generateKey(descriptor,null,parameters,0,new byte[32]);
            CertificateFactory factory=CertificateFactory.getInstance("X.509");
            List<Certificate> chain=new ArrayList<>();chain.add(factory.generateCertificate(new ByteArrayInputStream(metadata.certificate)));
            Collection<? extends Certificate> others=factory.generateCertificates(new ByteArrayInputStream(metadata.certificateChain));chain.addAll(others);
            for(int i=0;i<chain.size()-1;i++)chain.get(i).verify(chain.get(i+1).getPublicKey());
            List<Der> fields=Der.parse(Der.parse(((X509Certificate)chain.get(0)).getExtensionValue("1.3.6.1.4.1.11129.2.1.17")).get(0).body).get(0).children();
            if(fields.size()!=8||!Arrays.equals(fields.get(4).body,challenge))throw new Exception("challenge mismatch");
            int matched=0;
            for(Der field:fields.get(7).children())for(int i=0;i<5;i++)if(expected[i]!=null&&field.cls==128&&field.tag==(TAGS[i]&0x0fffffff)){
                if(!Arrays.equals(field.children().get(0).body,expected[i]))throw new Exception("attested property mismatch");matched|=1<<i;
            }
            if(matched!=mask)throw new Exception("requested properties absent from hardware attestation");
            result.put("generated",true).put("chain_links_verified",true).put("challenge_matches",true)
                .put("requested_values_attested",true).put("keymint_security_level",fields.get(3).number());
        }catch(KeyStoreException error){result.put("generated",false).put("keymint_error",error.getErrorCode());}
        finally {
            try{store.deleteKey(descriptor);result.put("owned_key_deleted",true);}
            catch(KeyStoreException error){if(error.getErrorCode()==7)result.put("owned_key_deleted",true);else throw error;}
        }
        return result;
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("No supplied identities accepted; current properties only");
        KeyStore2 store=KeyStore2.getInstance();KeyStoreSecurityLevel level=store.getSecurityLevel(SecurityLevel.TRUSTED_ENVIRONMENT);
        JSONArray trials=new JSONArray();
        for(int mask:new int[]{0,1,2,4,8,16,31}){JSONObject one=generate(store,level,mask,false);trials.put(one);System.out.println(one);}
        JSONObject platform=generate(store,level,31,true);trials.put(platform);System.out.println(platform);
        System.out.println(new JSONObject().put("completed",true).put("properties_changed",false).put("unique_ids_requested",false).put("trials",trials));
    }
}
