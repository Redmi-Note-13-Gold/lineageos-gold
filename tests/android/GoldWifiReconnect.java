/* SPDX-License-Identifier: Apache-2.0 */
import android.os.IBinder;
import android.os.Process;
import java.lang.reflect.Method;

/** Explicitly select one existing saved network without reading its credentials. */
public final class GoldWifiReconnect {
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || Process.myUid() != 0) {
            throw new IllegalArgumentException("authorized adb root and an existing network ID required");
        }
        int id = Integer.parseInt(args[0]);
        if (id < 0) throw new IllegalArgumentException("negative network ID");
        // The public SDK intentionally omits these privileged Binder interfaces.
        // Resolve named methods from this installed framework, never transaction IDs.
        Class<?> manager = Class.forName("android.os.ServiceManager");
        IBinder binder = (IBinder) manager.getMethod("getService", String.class)
                .invoke(null, "wifi");
        if (binder == null) throw new IllegalStateException("Wi-Fi service is unavailable");
        Class<?> stub = Class.forName("android.net.wifi.IWifiManager$Stub");
        Object service = stub.getMethod("asInterface", IBinder.class).invoke(null, binder);
        Class<?> api = Class.forName("android.net.wifi.IWifiManager");
        Method select = api.getMethod("enableNetwork", int.class, boolean.class, String.class);
        boolean accepted = (Boolean) select.invoke(service, id, true, "com.android.shell");
        if (!accepted) throw new IllegalStateException("framework rejected saved-network selection");
        // Acceptance only starts selection. The coordinator must separately check
        // association, DHCP, connectivity and framework network validation.
        System.out.println("SELECTION_REQUEST_ACCEPTED network_id=" + id);
    }
}
