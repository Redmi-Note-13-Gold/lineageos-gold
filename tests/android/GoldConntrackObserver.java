/* SPDX-License-Identifier: Apache-2.0 */
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructTimeval;
import dalvik.system.PathClassLoader;
import java.io.FileDescriptor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.SocketAddress;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.HashSet;

/** Bounded, receive-only conntrack multicast observer; does not request dumps or change state. */
public final class GoldConntrackObserver {
    public static void main(String[] args) throws Exception {
        if (args.length != 5 || !args[0].startsWith("/apex/") || !args[0].endsWith(".apk")) {
            throw new IllegalArgumentException("APK client-IPv4 server-IPv4 ports seconds required");
        }
        int duration = Integer.parseInt(args[4]);
        if (duration < 1 || duration > 180) throw new IllegalArgumentException("duration outside 1..180");
        InetAddress client = InetAddress.getByName(args[1]), server = InetAddress.getByName(args[2]);
        HashSet<Integer> ports = new HashSet<>();
        for (String p : args[3].split(",")) ports.add(Integer.parseInt(p));
        PathClassLoader loader = new PathClassLoader(args[0], ClassLoader.getSystemClassLoader());
        String base = "com.android.networkstack.tethering.util.";
        Class<?> headerClass = loader.loadClass(base + "netlink.StructNlMsgHdr");
        Class<?> messageClass = loader.loadClass(base + "netlink.ConntrackMessage");
        Class<?> eventClass = loader.loadClass(base + "ip.ConntrackMonitor$ConntrackEvent");
        if (messageClass.getClassLoader() != loader) throw new AssertionError("wrong parser origin");
        Method headerParse = headerClass.getMethod("parse", ByteBuffer.class);
        Method messageParse = messageClass.getMethod("parse", headerClass, ByteBuffer.class);
        Method established = eventClass.getMethod("isEstablishedNatSession", messageClass);
        Method dying = eventClass.getMethod("isDyingNatSession", messageClass);
        FileDescriptor socket = Os.socket(16, OsConstants.SOCK_DGRAM | OsConstants.SOCK_CLOEXEC, 12);
        try {
            Os.setsockoptInt(socket, OsConstants.SOL_SOCKET, OsConstants.SO_RCVBUF, 1048576);
            Os.setsockoptTimeval(socket, OsConstants.SOL_SOCKET, OsConstants.SO_RCVTIMEO, StructTimeval.fromMillis(250));
            SocketAddress address = (SocketAddress) Class.forName("android.system.NetlinkSocketAddress")
                .getConstructor(int.class, int.class).newInstance(0, 7);
            Os.bind(socket, address);
            System.out.println("{\"ready\":true,\"receive_only\":true}");
            System.out.flush();
            long until = System.nanoTime() + duration * 1000000000L;
            byte[] data = new byte[65536];
            while (System.nanoTime() < until) {
                int bytes;
                try { bytes = Os.read(socket, data, 0, data.length); }
                catch (ErrnoException e) {
                    if (e.errno == OsConstants.EAGAIN || e.errno == OsConstants.EINTR) continue;
                    throw e;
                }
                for (int offset = 0; offset + 16 <= bytes;) {
                    int len = ByteBuffer.wrap(data, offset, 4).order(ByteOrder.nativeOrder()).getInt();
                    if (len < 16 || offset + len > bytes) throw new AssertionError("truncated netlink message");
                    byte[] raw = Arrays.copyOfRange(data, offset, offset + len);
                    offset += (len + 3) & ~3;
                    ByteBuffer buffer = ByteBuffer.wrap(raw).order(ByteOrder.nativeOrder());
                    Object header = headerParse.invoke(null, buffer);
                    int type = headerClass.getField("nlmsg_type").getShort(header) & 65535;
                    if ((type >> 8) != 1 || raw.length < 20 || raw[16] != 2) continue;
                    Object msg = messageParse.invoke(null, header, buffer);
                    if (msg == null) throw new AssertionError("installed conntrack parser rejected message");
                    Object tuple = messageClass.getField("tupleOrig").get(msg);
                    if (tuple == null) continue;
                    Class<?> tc = tuple.getClass();
                    int port = ((Number) tc.getField("srcPort").get(tuple)).intValue() & 65535;
                    if (!client.equals(tc.getField("srcIp").get(tuple)) || !server.equals(tc.getField("dstIp").get(tuple))
                            || !ports.contains(port)) continue;
                    int state = messageClass.getField("tcpState").getInt(msg);
                    int timeout = messageClass.getField("timeoutSec").getInt(msg);
                    int status = messageClass.getField("status").getInt(msg);
                    System.out.println("{\"elapsed_ns\":" + System.nanoTime() + ",\"type\":" + type
                        + ",\"port\":" + port + ",\"tcp_state\":" + state + ",\"timeout\":" + timeout
                        + ",\"status\":" + status + ",\"monitor_established\":" + established.invoke(null,msg)
                        + ",\"monitor_dying\":" + dying.invoke(null,msg) + "}");
                    StringBuilder hex = new StringBuilder();
                    for (byte b : raw) hex.append(String.format("%02x", b & 255));
                    System.out.println("HEX=" + hex);
                    System.out.flush();
                }
            }
            System.out.println("{\"completed\":true}");
        } finally { Os.close(socket); }
    }
}
