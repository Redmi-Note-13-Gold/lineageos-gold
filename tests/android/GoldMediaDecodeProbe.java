/* SPDX-License-Identifier: Apache-2.0 */
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.os.SystemClock;
import java.nio.ByteBuffer;

/** Bounded hardware decoder exercise for an explicitly supplied local test clip. */
public final class GoldMediaDecodeProbe {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("local test clip path required");
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec codec = null;
        try {
            extractor.setDataSource(args[0]);
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
        } finally {
            if (codec != null) codec.release();
            extractor.release();
        }
    }
}
