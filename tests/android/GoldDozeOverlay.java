/* SPDX-License-Identifier: Apache-2.0 */
import android.os.IBinder;
import android.os.Process;

/** Remove only the owned, temporary AOD component overlay through OverlayManager. */
public final class GoldDozeOverlay {
    public static void main(String[] args) throws Exception {
        if (Process.myUid() != 0 || args.length != 1 || !args[0].equals("remove"))
            throw new IllegalArgumentException("root: remove");
        Class<?> identifier = Class.forName("android.content.om.OverlayIdentifier");
        Object own = identifier.getConstructor(String.class, String.class)
            .newInstance("com.android.shell", "GoldDozeProbe20260922");
        Class<?> builder = Class.forName("android.content.om.OverlayManagerTransaction$Builder");
        Object b = builder.getConstructor().newInstance();
        builder.getMethod("unregisterFabricatedOverlay", identifier).invoke(b, own);
        Object transaction = builder.getMethod("build").invoke(b);
        IBinder binder = (IBinder) Class.forName("android.os.ServiceManager")
            .getMethod("getService", String.class).invoke(null, "overlay");
        Class<?> service = Class.forName("android.content.om.IOverlayManager");
        Object manager = Class.forName("android.content.om.IOverlayManager$Stub")
            .getMethod("asInterface", IBinder.class).invoke(null, binder);
        service.getMethod("commit", Class.forName("android.content.om.OverlayManagerTransaction"))
            .invoke(manager, transaction);
        System.out.println("owned_overlay_unregistered=true");
    }
}
