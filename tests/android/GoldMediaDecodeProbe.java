/* SPDX-License-Identifier: Apache-2.0 */
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.media.Image;
import android.os.SystemClock;
import java.io.File;
import java.nio.ByteBuffer;

/** Hardware codec exercise; synthetic roundtrips never read user media. */
public final class GoldMediaDecodeProbe {
    public static void main(String[] args) throws Exception {
        if (args.length == 3 && args[0].equals("--roundtrip")) {
            File directory = new File(args[1]);
            int cycles = Integer.parseInt(args[2]);
            if (!directory.isDirectory() || cycles < 1 || cycles > 20) {
                throw new IllegalArgumentException("owned test directory and 1..20 cycles required");
            }
            for (int cycle = 0; cycle < cycles; ++cycle) {
                File clip = File.createTempFile("gold-codec2-", ".mp4", directory);
                try {
                    int encoded = encode(clip.getAbsolutePath());
                    int decoded = decode(clip.getAbsolutePath());
                    if (decoded != encoded) {
                        throw new IllegalStateException("frame count differs: " + encoded + "/" + decoded);
                    }
                    System.out.println("PASS roundtrip=" + (cycle + 1) + " frames=" + decoded);
                } finally {
                    if (!clip.delete()) throw new IllegalStateException("cannot remove own test clip");
                }
            }
            return;
        }
        if (args.length != 1) {
            throw new IllegalArgumentException("local clip, or --roundtrip owned-directory cycles");
        }
        decode(args[0]);
    }

    private static int encode(String path) throws Exception {
        final int width = 640, height = 360, frameCount = 24;
        MediaCodec codec = null;
        MediaMuxer muxer = null;
        boolean muxerStarted = false;
        int inputFrames = 0, outputFrames = 0, track = -1;
        try {
            codec = MediaCodec.createByCodecName("c2.mtk.avc.encoder");
            System.out.println("encoder=" + codec.getName());
            if (!codec.getCodecInfo().isHardwareAccelerated()) {
                throw new IllegalStateException("test requires hardware encoder");
            }
            MediaFormat format = MediaFormat.createVideoFormat("video/avc", width, height);
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT,
                    MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
            format.setInteger(MediaFormat.KEY_BIT_RATE, 1000000);
            format.setInteger(MediaFormat.KEY_FRAME_RATE, 30);
            format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
            muxer = new MediaMuxer(path, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
            codec.start();
            boolean inputEnded = false, outputEnded = false;
            long deadline = SystemClock.elapsedRealtime() + 20000;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            while (!outputEnded && SystemClock.elapsedRealtime() < deadline) {
                if (!inputEnded) {
                    int index = codec.dequeueInputBuffer(10000);
                    if (index >= 0) {
                        if (inputFrames == frameCount) {
                            codec.queueInputBuffer(index, 0, 0, inputFrames * 1000000L / 30,
                                    MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputEnded = true;
                        } else {
                            Image image = codec.getInputImage(index);
                            if (image == null) throw new IllegalStateException("no flexible YUV input image");
                            try {
                                Image.Plane[] planes = image.getPlanes();
                                if (planes.length != 3) throw new IllegalStateException("not YUV420");
                                for (int n = 0; n < planes.length; ++n) {
                                    Image.Plane plane = planes[n];
                                    ByteBuffer data = plane.getBuffer();
                                    int origin = data.position();
                                    int rows = n == 0 ? height : height / 2;
                                    int columns = n == 0 ? width : width / 2;
                                    byte value = (byte) (n == 0 ? 16 + inputFrames * 8 : 128);
                                    for (int y = 0; y < rows; ++y) {
                                        for (int x = 0; x < columns; ++x) {
                                            data.put(origin + y * plane.getRowStride()
                                                    + x * plane.getPixelStride(), value);
                                        }
                                    }
                                }
                            } finally {
                                image.close();
                            }
                            codec.queueInputBuffer(index, 0, width * height * 3 / 2,
                                    inputFrames * 1000000L / 30, 0);
                            ++inputFrames;
                        }
                    }
                }
                int index = codec.dequeueOutputBuffer(info, 10000);
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    if (muxerStarted) throw new IllegalStateException("encoder format changed twice");
                    track = muxer.addTrack(codec.getOutputFormat());
                    muxer.start();
                    muxerStarted = true;
                } else if (index >= 0) {
                    try {
                        if (info.size > 0 && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
                            if (!muxerStarted) throw new IllegalStateException("encoded output before format");
                            ByteBuffer data = codec.getOutputBuffer(index);
                            data.position(info.offset);
                            data.limit(info.offset + info.size);
                            muxer.writeSampleData(track, data, info);
                            ++outputFrames;
                        }
                        outputEnded = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    } finally {
                        codec.releaseOutputBuffer(index, false);
                    }
                }
            }
            if (!outputEnded || outputFrames != frameCount) {
                throw new IllegalStateException("encoder timeout or frame loss: " + outputFrames);
            }
            muxer.stop();
            muxerStarted = false;
            System.out.println("PASS encoded_frames=" + outputFrames + " eos=true");
            return outputFrames;
        } finally {
            try {
                if (codec != null) codec.release();
            } finally {
                if (muxer != null) muxer.release();
            }
        }
    }

    private static int decode(String path) throws Exception {
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec codec = null;
        try {
            extractor.setDataSource(path);
            MediaFormat format = null;
            for (int i = 0; i < extractor.getTrackCount(); ++i) {
                MediaFormat candidate = extractor.getTrackFormat(i);
                String mime = candidate.getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("video/")) {
                    extractor.selectTrack(i);
                    format = candidate;
                    break;
                }
            }
            if (format == null) throw new IllegalArgumentException("no video track");
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));
            System.out.println("decoder=" + codec.getName());
            if (!codec.getName().startsWith("c2.mtk.")) {
                throw new IllegalStateException("test requires the matched MTK hardware decoder");
            }
            codec.configure(format, null, null, 0);
            codec.start();
            boolean inputEnded = false;
            boolean outputEnded = false;
            int frames = 0;
            long start = SystemClock.elapsedRealtime();
            long deadline = start + 20000;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            while (!outputEnded && SystemClock.elapsedRealtime() < deadline) {
                if (!inputEnded) {
                    int inputIndex = codec.dequeueInputBuffer(10000);
                    if (inputIndex >= 0) {
                        ByteBuffer input = codec.getInputBuffer(inputIndex);
                        int size = extractor.readSampleData(input, 0);
                        if (size < 0) {
                            codec.queueInputBuffer(inputIndex, 0, 0, 0,
                                    MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputEnded = true;
                        } else {
                            codec.queueInputBuffer(inputIndex, 0, size, extractor.getSampleTime(), 0);
                            extractor.advance();
                        }
                    }
                }
                int outputIndex = codec.dequeueOutputBuffer(info, 10000);
                if (outputIndex >= 0) {
                    if (info.size > 0) ++frames;
                    outputEnded = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    codec.releaseOutputBuffer(outputIndex, false);
                }
            }
            long elapsed = SystemClock.elapsedRealtime() - start;
            if (!outputEnded || frames == 0) {
                throw new IllegalStateException("decoder timeout or empty output; frames=" + frames);
            }
            System.out.println("PASS frames=" + frames + " elapsed_ms=" + elapsed + " eos=true");
            // This exercises the codec/callers; it is not a playback FPS or energy benchmark.
            return frames;
        } finally {
            if (codec != null) codec.release();
            extractor.release();
        }
    }
}
