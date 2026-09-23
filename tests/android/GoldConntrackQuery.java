/* SPDX-License-Identifier: Apache-2.0 */
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructTimeval;
import dalvik.system.PathClassLoader;
import java.io.FileDescriptor;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.Inet4Address;
import java.net.SocketAddress;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;

/** Queries only explicit owned TCP tuples. No dumps, timeout updates or deletion requests. */
public final class GoldConntrackQuery {
    public static void main(String[] args) throws Exception {
        if(args.length!=5 || !args[0].startsWith("/apex/") || !args[0].endsWith(".apk"))
            throw new IllegalArgumentException("installed APK client-IP server-IP owned-source-ports server-port");
        String[] ports=args[3].split(",");
        if(ports.length<1||ports.length>8)throw new IllegalArgumentException("one to eight owned flows only");
        InetAddress client=InetAddress.getByName(args[1]),server=InetAddress.getByName(args[2]);
        if(client.getAddress().length!=4||server.getAddress().length!=4)throw new IllegalArgumentException("IPv4 only");
        int dstPort=Integer.parseInt(args[4]);
        PathClassLoader loader=new PathClassLoader(args[0],ClassLoader.getSystemClassLoader());
        String base="com.android.networkstack.tethering.util.netlink.";
        Class<?> message=loader.loadClass(base+"ConntrackMessage"),header=loader.loadClass(base+"StructNlMsgHdr");
        Method create=message.getMethod("newIPv4TimeoutUpdateRequest",int.class,Inet4Address.class,int.class,Inet4Address.class,int.class,int.class);
        Method parseHeader=header.getMethod("parse",ByteBuffer.class),parse=message.getMethod("parse",header,ByteBuffer.class);
        for(int n=0;n<ports.length;n++) {
            int srcPort=Integer.parseInt(ports[n]);
            if(srcPort<1||srcPort>65535||dstPort<1||dstPort>65535)throw new IllegalArgumentException("port range");
            byte[] template=(byte[])create.invoke(null,6,client,srcPort,server,dstPort,1);
            ByteBuffer original=ByteBuffer.wrap(template).order(ByteOrder.nativeOrder());
            int cursor=20,endTuple=-1;
            while(cursor+4<=template.length) {
                int length=original.getShort(cursor)&65535,type=original.getShort(cursor+2)&16383;
                if(length<4||cursor+length>template.length)throw new AssertionError("invalid attribute");
                if(type==1&&cursor==20)endTuple=cursor+((length+3)&~3);
                else if(type!=7)throw new AssertionError("unexpected request attribute");
                cursor+=(length+3)&~3;
            }
            if(endTuple<24)throw new AssertionError("original tuple not found");
            byte[] request=Arrays.copyOf(template,endTuple);
            ByteBuffer b=ByteBuffer.wrap(request).order(ByteOrder.nativeOrder());
            b.putInt(0,request.length).putShort(4,(short)257).putShort(6,(short)1).putInt(8,42+n).putInt(12,0);
            // CT_GET + NLM_F_REQUEST and the original tuple only: no CTA_TIMEOUT or mutation flags.
            FileDescriptor fd=Os.socket(16,OsConstants.SOCK_DGRAM|OsConstants.SOCK_CLOEXEC,12);
            try {
                Os.setsockoptTimeval(fd,OsConstants.SOL_SOCKET,OsConstants.SO_RCVTIMEO,StructTimeval.fromMillis(1000));
                SocketAddress address=(SocketAddress)Class.forName("android.system.NetlinkSocketAddress")
                    .getConstructor(int.class,int.class).newInstance(0,0);
                Os.connect(fd,address);Os.write(fd,request,0,request.length);
                byte[] bytes=new byte[4096];int length=Os.read(fd,bytes,0,bytes.length);
                ByteBuffer reply=ByteBuffer.wrap(bytes,0,length).order(ByteOrder.nativeOrder());
                Object h=parseHeader.invoke(null,reply);
                int seq=header.getField("nlmsg_seq").getInt(h),type=header.getField("nlmsg_type").getShort(h)&65535;
                if(seq!=42+n)throw new AssertionError("sequence mismatch");
                if(type==2) {
                    int error=reply.getInt();
                    System.out.println("{\"flow_index\":"+n+",\"query_only\":true,\"errno\":"+(-error)+",\"absent\":"+(error==-OsConstants.ENOENT)+"}");
                } else {
                    Object m=parse.invoke(null,h,reply);
                    if(m==null)throw new AssertionError("reply parser rejected CT_GET");
                    Object tuple=message.getField("tupleOrig").get(m);
                    Class<?> tc=tuple.getClass();
                    boolean matched=client.equals(tc.getField("srcIp").get(tuple))
                        && server.equals(tc.getField("dstIp").get(tuple))
                        && (tc.getField("srcPort").getShort(tuple)&65535)==srcPort
                        && (tc.getField("dstPort").getShort(tuple)&65535)==dstPort
                        && tc.getField("protoNum").getByte(tuple)==6;
                    if(!matched)throw new AssertionError("response tuple differs from explicit request at index "+n);
                    System.out.println("{\"flow_index\":"+n+",\"query_only\":true,\"absent\":false,\"tuple_verified\":true,\"status\":"+message.getField("status").getInt(m)+",\"tcp_state\":"+message.getField("tcpState").getInt(m)+",\"timeout\":"+message.getField("timeoutSec").getInt(m)+"}");
                }
            } finally {Os.close(fd);}
        }
    }
}
