/* SPDX-License-Identifier: Apache-2.0 */
import dalvik.system.PathClassLoader;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Synthetic netlink messages through the installed Tethering APK's actual parser.
 * Does not open sockets, change network configuration or write BPF maps.
 */
public final class GoldConntrackProbe {
    private static byte[] packet(int state, int payloadBytes, boolean nested) {
        int attribute = payloadBytes < 0 ? 0 : 8 + ((4 + payloadBytes + 3) & ~3);
        ByteBuffer b = ByteBuffer.allocate(20 + attribute).order(ByteOrder.nativeOrder());
        b.putInt(b.capacity()).putShort((short) 0x100).putShort((short) 0).putInt(1).putInt(0);
        b.put((byte) 2).put((byte) 0).putShort((short) 0);
        if (attribute != 0) {
            b.putShort((short) attribute).putShort((short) (nested ? 0x8004 : 4));
            b.putShort((short) (attribute - 4)).putShort((short) 0x8001);
            b.putShort((short) (4 + payloadBytes)).putShort((short) 1);
            for (int n = 0; n < payloadBytes; ++n) b.put((byte) state);
        }
        return b.array();
    }

    public static void main(String[] args) {
        try { run(args); }
        catch (Throwable failure) { failure.printStackTrace(System.err); System.exit(1); }
    }

    private static void run(String[] args) throws Exception {
        if (args.length != 1 || !args[0].startsWith("/apex/") || !args[0].endsWith(".apk")) {
            throw new IllegalArgumentException("explicit installed Tethering APEX APK required");
        }
        System.out.println("Loading installed Tethering classes");
        ClassLoader loader = new PathClassLoader(args[0], ClassLoader.getSystemClassLoader());
        Class<?> headerClass = loader.loadClass("com.android.networkstack.tethering.util.netlink.StructNlMsgHdr");
        Class<?> messageClass = loader.loadClass("com.android.networkstack.tethering.util.netlink.ConntrackMessage");
        Class<?> eventClass = loader.loadClass("com.android.networkstack.tethering.util.ip.ConntrackMonitor$ConntrackEvent");
        if (headerClass.getClassLoader() != loader || messageClass.getClassLoader() != loader
                || eventClass.getClassLoader() != loader) {
            throw new AssertionError("test must use the selected installed APK, not a parent copy");
        }
        System.out.println("Installed APK class origin verified");
        Method headerParse = headerClass.getMethod("parse", ByteBuffer.class);
        Method messageParse = messageClass.getMethod("parse", headerClass, ByteBuffer.class);
        Constructor<?> eventConstructor = eventClass.getConstructor(messageClass);
        Field messageState = messageClass.getField("tcpState"), eventState = eventClass.getField("tcpState");
        int[][] cases = {{1,1,1,1},{2,1,1,2},{3,1,1,3},{4,1,1,4},{5,1,1,5},
            {6,1,1,6},{7,1,1,7},{8,1,1,8},{255,1,1,255},
            {3,-1,1,-1},{3,0,1,-1},{3,4,1,-1},{3,1,0,-1}};
        for (int[] test : cases) {
            System.out.println("Parsing state=" + test[0] + " payloadBytes=" + test[1] + " nested=" + test[2]);
            byte[] raw = packet(test[0], test[1], test[2] != 0);
            ByteBuffer buffer = ByteBuffer.wrap(raw).order(ByteOrder.nativeOrder());
            Object message = messageParse.invoke(null, headerParse.invoke(null, buffer), buffer);
            if (message == null || messageState.getInt(message) != test[3]
                    || eventState.getInt(eventConstructor.newInstance(message)) != test[3]
                    || buffer.position() != raw.length) {
                throw new AssertionError("installed parser/event mismatch, state=" + test[0] + " length=" + test[1]);
            }
        }
        System.out.println("{\"passed\":true,\"installed_parser_and_event_cases\":" + cases.length
            + ",\"tcp_states\":[1,2,3,4,5,6,7,8,255],\"missing_and_malformed_fail_unknown\":true,"
            + "\"bpf_rule_lifecycle_tested\":false}");
        System.exit(0);
    }
}
