"""
WebRTC Handler — Server-side WebRTC voice pipeline.

Architecture:
  Browser Mic → aiortc Track → Resample 48kHz→16kHz → Deepgram STT
  Sarvam TTS (MP3) → decode→16kHz PCM → upsample→48kHz stereo → aiortc Track → Browser Speaker

Key design decisions:
  1. Output audio at 48kHz stereo s16 to match Opus codec native format exactly.
     This eliminates aiortc's internal resampler guesswork that caused static/glitches.
  2. Queue-based frame pacing (like aiortc's own PlayerStreamTrack) instead of
     manual time.time() sleep loops that suffer from Windows 15.6ms timer jitter.
  3. Barge-in support: clear the outgoing audio queue when user starts speaking.
"""

import os
import json
import asyncio
import fractions
import base64
import io
import av
import time
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from agent_engine import VoiceSession, decode_mp3_to_pcm
import agents_store
import google_service

# ─── Constants matching aiortc Opus encoder expectations ───
OPUS_SAMPLE_RATE = 48000
OPUS_CHANNELS = 1       # mono
OPUS_FRAME_DURATION = 0.02  # 20ms
OPUS_SAMPLES_PER_FRAME = int(OPUS_SAMPLE_RATE * OPUS_FRAME_DURATION)  # 960
OPUS_FRAME_BYTES = OPUS_SAMPLES_PER_FRAME * OPUS_CHANNELS * 2  # 960 * 1 * 2 = 1920 bytes

# Input from TTS is 16kHz mono
TTS_SAMPLE_RATE = 16000
TTS_CHANNELS = 1
TTS_FRAME_DURATION = 0.02
TTS_SAMPLES_PER_FRAME = int(TTS_SAMPLE_RATE * TTS_FRAME_DURATION)  # 320
TTS_FRAME_BYTES = TTS_SAMPLES_PER_FRAME * TTS_CHANNELS * 2  # 640 bytes


def _resample_16k_mono_to_48k_stereo(pcm_16k_mono: bytes) -> list:
    """
    Take raw 16kHz mono s16 PCM bytes and produce a list of av.AudioFrame objects
    at 48kHz stereo s16, each exactly OPUS_SAMPLES_PER_FRAME (960) samples.
    """
    if not pcm_16k_mono:
        return []

    # Build a single input frame from the raw bytes
    num_samples = len(pcm_16k_mono) // 2  # 2 bytes per s16 sample
    if num_samples == 0:
        return []

    input_frame = av.AudioFrame(format='s16', layout='mono', samples=num_samples)
    input_frame.sample_rate = TTS_SAMPLE_RATE
    input_frame.planes[0].update(pcm_16k_mono[:num_samples * 2])

    # Resample to 48kHz stereo in fixed 960-sample frames
    resampler = av.AudioResampler(
        format='s16',
        layout='stereo',
        rate=OPUS_SAMPLE_RATE,
        frame_size=OPUS_SAMPLES_PER_FRAME,
    )

    output_frames = []
    for resampled in resampler.resample(input_frame):
        output_frames.append(resampled)
    # Flush any buffered remainder
    for resampled in resampler.resample(None):
        output_frames.append(resampled)

    return output_frames


class TTSAudioTrack(MediaStreamTrack):
    """
    Custom outgoing audio track for agent's TTS voice.

    Design:
    - Maintains an asyncio.Queue of pre-built av.AudioFrame (48kHz stereo s16).
    - recv() pulls from queue or yields silence. Pacing is controlled by
      waiting on the queue with a timeout matching frame duration.
    - add_pcm_bytes() accepts 16kHz mono PCM, resamples to 48kHz stereo,
      and enqueues the resulting frames.
    - clear_queue() supports barge-in by flushing all pending audio.
    """
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue()
        self._pts = 0
        self._started = False
        self._raw_buffer = bytearray()
        self._resampled_bytes_buffer = bytearray()
        self._resampler = av.AudioResampler(
            format='s16',
            layout='mono',
            rate=OPUS_SAMPLE_RATE,
        )
        self._prebuffering = True
        self._flushed = False
        self._is_speaking = False  # True while agent is generating/playing a response

    def add_pcm_bytes(self, data: bytes):
        """Accept 16kHz mono PCM bytes, buffer, resample, and slice into 48kHz mono frames."""
        if not data:
            return
        self._raw_buffer.extend(data)
        
        while len(self._raw_buffer) >= TTS_FRAME_BYTES:
            chunk = bytes(self._raw_buffer[:TTS_FRAME_BYTES])
            del self._raw_buffer[:TTS_FRAME_BYTES]
            
            input_frame = av.AudioFrame(format='s16', layout='mono', samples=TTS_SAMPLES_PER_FRAME)
            input_frame.sample_rate = TTS_SAMPLE_RATE
            input_frame.planes[0].update(chunk)
            
            try:
                resampled_frames = self._resampler.resample(input_frame)
                for frame in resampled_frames:
                    self._resampled_bytes_buffer.extend(bytes(frame.planes[0]))
            except Exception as e:
                print(f"[WebRTC] Resampling error: {e}")

        # Slice the resampled bytes into complete Opus frames (1920 bytes)
        while len(self._resampled_bytes_buffer) >= OPUS_FRAME_BYTES:
            frame_data = bytes(self._resampled_bytes_buffer[:OPUS_FRAME_BYTES])
            del self._resampled_bytes_buffer[:OPUS_FRAME_BYTES]
            
            frame = av.AudioFrame(format='s16', layout='mono', samples=OPUS_SAMPLES_PER_FRAME)
            frame.sample_rate = OPUS_SAMPLE_RATE
            frame.planes[0].update(frame_data)
            self._queue.put_nowait(frame)

        # Once we buffer enough frames, start playback and reset the pacing clock
        if self._prebuffering and self._queue.qsize() >= 4:
            self._prebuffering = False
            self._started = False

    def flush(self):
        """Flush any remaining buffered audio and pad to complete frames."""
        try:
            # 1. Handle leftover bytes in raw buffer
            if len(self._raw_buffer) > 0:
                pad_len = TTS_FRAME_BYTES - len(self._raw_buffer)
                self._raw_buffer.extend(b'\x00' * pad_len)
                
                chunk = bytes(self._raw_buffer)
                self._raw_buffer.clear()
                
                input_frame = av.AudioFrame(format='s16', layout='mono', samples=TTS_SAMPLES_PER_FRAME)
                input_frame.sample_rate = TTS_SAMPLE_RATE
                input_frame.planes[0].update(chunk)
                
                resampled_frames = self._resampler.resample(input_frame)
                for frame in resampled_frames:
                    self._resampled_bytes_buffer.extend(bytes(frame.planes[0]))
            
            # 2. Flush the resampler itself
            flushed_frames = self._resampler.resample(None)
            for frame in flushed_frames:
                self._resampled_bytes_buffer.extend(bytes(frame.planes[0]))
                
            # 3. Handle leftover bytes in the resampled buffer by padding with silence
            if len(self._resampled_bytes_buffer) > 0:
                pad_len = OPUS_FRAME_BYTES - (len(self._resampled_bytes_buffer) % OPUS_FRAME_BYTES)
                if pad_len < OPUS_FRAME_BYTES:
                    self._resampled_bytes_buffer.extend(b'\x00' * pad_len)
                    
            while len(self._resampled_bytes_buffer) >= OPUS_FRAME_BYTES:
                frame_data = bytes(self._resampled_bytes_buffer[:OPUS_FRAME_BYTES])
                del self._resampled_bytes_buffer[:OPUS_FRAME_BYTES]
                
                frame = av.AudioFrame(format='s16', layout='mono', samples=OPUS_SAMPLES_PER_FRAME)
                frame.sample_rate = OPUS_SAMPLE_RATE
                frame.planes[0].update(frame_data)
                self._queue.put_nowait(frame)
                
        except Exception as e:
            print(f"[WebRTC] Resampler flush error: {e}")
        finally:
            self._flushed = True
            self._prebuffering = False  # Start playing immediately whatever is left

    def clear_queue(self):
        """Flush all pending audio frames (barge-in support) and reset buffers."""
        self._is_speaking = False
        self._raw_buffer.clear()
        self._resampled_bytes_buffer.clear()
        self._resampler = av.AudioResampler(
            format='s16',
            layout='mono',
            rate=OPUS_SAMPLE_RATE,
        )
        self._prebuffering = True
        self._flushed = False
        self._started = False  # Reset pacing clock
        
        dropped = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:
                break
        if dropped:
            print(f"[WebRTC] Barge-in: cleared {dropped} queued audio frames")

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        use_silence = True
        frame = None

        if not self._prebuffering:
            try:
                frame = self._queue.get_nowait()
                use_silence = False
            except asyncio.QueueEmpty:
                # Underflow: transition back to prebuffering and reset pacing clock
                self._prebuffering = True
                self._flushed = False
                self._started = False

        if use_silence:
            # No audio available or prebuffering — generate a silent frame
            frame = av.AudioFrame(
                format='s16', layout='mono', samples=OPUS_SAMPLES_PER_FRAME
            )
            frame.sample_rate = OPUS_SAMPLE_RATE
            frame.planes[0].update(b'\x00' * OPUS_FRAME_BYTES)

        # Assign contiguous PTS to prevent timestamp gaps
        frame.pts = self._pts
        frame.sample_rate = OPUS_SAMPLE_RATE
        frame.time_base = fractions.Fraction(1, OPUS_SAMPLE_RATE)
        self._pts += OPUS_SAMPLES_PER_FRAME

        # Pace: sleep for one frame duration to maintain real-time playback
        # aiortc calls recv() in a tight loop; we must throttle it.
        if not self._started:
            self._started = True
            self._start_wall = time.monotonic()
            self._start_pts = self._pts - OPUS_SAMPLES_PER_FRAME

        # Calculate expected wall time for this frame
        elapsed_pts = (self._pts - self._start_pts) / OPUS_SAMPLE_RATE
        target_wall = self._start_wall + elapsed_pts
        wait = target_wall - time.monotonic()
        if wait > 0.007:
            await asyncio.sleep(wait)

        return frame


class WebRTCSessionManager:
    _instance = None

    def __init__(self):
        self.active_pcs = set()
        # Map session → (out_track, response_task) for barge-in cancellation
        self._session_tracks = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def handle_offer(
        self,
        sdp: str,
        sdp_type: str,
        agent_id: str,
        user_id: str,
        spreadsheet_id: str = None,
        sheet_name: str = None,
        lead_row: int = None,
        lead_id: str = None
    ) -> dict:
        pc = RTCPeerConnection()
        self.active_pcs.add(pc)

        # 1. Fetch agent configuration
        agent_config = agents_store.get_agent(agent_id, user_id=user_id)
        if not agent_config:
            raise Exception("Agent not found")

        # 2. Initialize voice session in WebRTC mode
        session = VoiceSession(agent_config)
        session.is_webrtc = True
        await session.prepare_session(spreadsheet_id, sheet_name, lead_row, lead_id=lead_id)

        # 3. Create out-track for agent's voice
        out_track = TTSAudioTrack()
        pc.addTrack(out_track)
        self._session_tracks[id(session)] = {
            "out_track": out_track,
            "response_task": None,
            "session": session,
        }

        # 4. Handle incoming browser mic track
        @pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                asyncio.create_task(self._process_incoming_mic(track, session))

        @pc.on("datachannel")
        def on_datachannel(channel):
            print(f"[WebRTC] Data channel established: {channel.label}")
            session.webrtc_channel = channel

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"[WebRTC] Connection state: {pc.connectionState}")
            if pc.connectionState in ["closed", "failed", "disconnected"]:
                await self._cleanup_session(pc, session)

        # 5. Set Remote Description
        offer = RTCSessionDescription(sdp=sdp, type=sdp_type)
        await pc.setRemoteDescription(offer)

        # 6. Create Answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # 7. Start greeting in the background
        asyncio.create_task(self._play_greeting(session))

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

    def _get_track_info(self, session: VoiceSession) -> dict:
        return self._session_tracks.get(id(session))

    async def _process_incoming_mic(self, track: MediaStreamTrack, session: VoiceSession):
        """Receive WebRTC audio frames, resample to 16kHz mono, feed to Deepgram STT."""
        print("[WebRTC] Mic track active. Starting STT connection.")
        stt_ws = await session.connect_stt()
        if not stt_ws:
            print("[WebRTC] Failed to connect to Deepgram STT.")
            return

        # Start LLM transcript receiver task
        asyncio.create_task(self._read_transcripts_loop(session))

        # Resample browser's 48kHz stereo to 16kHz mono for Deepgram
        resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)

        try:
            while True:
                frame = await track.recv()
                resampled_frames = resampler.resample(frame)
                for r_frame in resampled_frames:
                    pcm_data = bytes(r_frame.planes[0])
                    await session.process_audio_chunk(pcm_data)
        except MediaStreamError:
            print("[WebRTC] Mic track ended (MediaStreamError).")
        except Exception as e:
            print(f"[WebRTC] Incoming mic stream error: {e}")

    async def _play_greeting(self, session: VoiceSession):
        """Generate greeting TTS and push into the outgoing track."""
        # Wait a beat for WebRTC ICE to stabilize
        await asyncio.sleep(1.0)
        print(f"[WebRTC] Speaking greeting: {session.first_message}")

        track_info = self._get_track_info(session)
        if not track_info:
            return

        out_track = track_info["out_track"]
        greeting_audio = await session.generate_greeting_audio()
        if greeting_audio:
            out_track.add_pcm_bytes(greeting_audio)
            out_track.flush()

            # Send assistant greeting transcript via data channel
            if hasattr(session, "webrtc_channel") and session.webrtc_channel:
                try:
                    session.webrtc_channel.send(json.dumps({
                        "type": "transcript",
                        "role": "assistant",
                        "text": session.first_message,
                        "is_final": True
                    }))
                except Exception as dce:
                    print(f"[WebRTC] Failed to send greeting transcript: {dce}")

    async def _handle_barge_in(self, session: VoiceSession):
        """Clear outgoing audio and cancel active response generation."""
        track_info = self._get_track_info(session)
        if not track_info:
            return

        # 1. Clear the audio queue
        track_info["out_track"].clear_queue()

        # 2. Cancel active response task
        task = track_info.get("response_task")
        if task and not task.done():
            task.cancel()
            print("[WebRTC] Barge-in: cancelled active response task")

    async def _read_transcripts_loop(self, session: VoiceSession):
        """Poll STT transcripts, run LLM response, synthesize TTS, push to track."""
        track_info = self._get_track_info(session)
        if not track_info:
            return
        out_track = track_info["out_track"]

        try:
            async for stt_msg in session.receive_transcripts():
                # Stream user real-time transcripts via data channel
                if stt_msg["type"] in ["interim", "final"]:
                    # If user speaks while agent is speaking → barge-in
                    if stt_msg["type"] == "interim" and out_track._is_speaking:
                        print("[WebRTC] Barge-in: user started speaking while agent is speaking")
                        await self._handle_barge_in(session)

                    if hasattr(session, "webrtc_channel") and session.webrtc_channel:
                        try:
                            session.webrtc_channel.send(json.dumps({
                                "type": "transcript",
                                "role": "user",
                                "text": stt_msg["text"],
                                "is_final": stt_msg["type"] == "final"
                            }))
                        except Exception as dce:
                            print(f"[WebRTC] Failed to send user transcript: {dce}")

                elif stt_msg["type"] == "utterance_end":
                    user_text = stt_msg["text"].strip()
                    if not user_text:
                        continue

                    print(f"[WebRTC] User said: {user_text}")

                    # Cancel any in-flight response before starting a new one
                    await self._handle_barge_in(session)

                    # Launch response generation as a cancellable task
                    task = asyncio.create_task(
                        self._generate_and_speak(session, out_track, user_text)
                    )
                    track_info["response_task"] = task

                    # Wait for it to complete (or get cancelled by barge-in)
                    try:
                        await task
                    except asyncio.CancelledError:
                        print("[WebRTC] Response generation was cancelled (barge-in)")

        except Exception as e:
            print(f"[WebRTC] Transcripts loop exception: {e}")

    async def _generate_and_speak(
        self, session: VoiceSession, out_track: TTSAudioTrack, user_text: str
    ):
        """Generate AI response chunk-by-chunk and stream TTS audio to track.
        
        Contains explicit cancellation checkpoints after every LLM chunk and 
        TTS chunk to ensure barge-in stops audio immediately.
        """
        out_track._is_speaking = True
        full_response = ""
        try:
            async for response_chunk in session.generate_response(user_text):
                # ── Cancellation checkpoint: check after each LLM chunk ──
                if asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()

                full_response += response_chunk + " "

                # Send interim assistant transcript
                if hasattr(session, "webrtc_channel") and session.webrtc_channel:
                    try:
                        session.webrtc_channel.send(json.dumps({
                            "type": "transcript",
                            "role": "assistant",
                            "text": full_response.strip(),
                            "is_final": False
                        }))
                    except Exception:
                        pass

                # Synthesize TTS and push audio frames
                async for pcm_chunk in session.stream_synthesize_speech(response_chunk):
                    # ── Cancellation checkpoint: check after each TTS chunk ──
                    if asyncio.current_task().cancelled():
                        raise asyncio.CancelledError()
                    out_track.add_pcm_bytes(pcm_chunk)

            out_track.flush()
            print(f"[WebRTC] AI responded: {full_response.strip()}")

            # Send final assistant transcript
            if hasattr(session, "webrtc_channel") and session.webrtc_channel:
                try:
                    session.webrtc_channel.send(json.dumps({
                        "type": "transcript",
                        "role": "assistant",
                        "text": full_response.strip(),
                        "is_final": True
                    }))
                except Exception as dce:
                    print(f"[WebRTC] Failed to send final assistant transcript: {dce}")
        except asyncio.CancelledError:
            print(f"[WebRTC] _generate_and_speak cancelled (barge-in), partial: {full_response.strip()[:80]}...")
            raise  # Re-raise so the caller's except CancelledError catches it
        finally:
            out_track._is_speaking = False

    def _find_pc_by_session(self, session: VoiceSession) -> RTCPeerConnection:
        for pc in self.active_pcs:
            for sender in pc.getSenders():
                if isinstance(sender.track, TTSAudioTrack):
                    track_info = self._get_track_info(session)
                    if track_info and track_info["out_track"] is sender.track:
                        return pc
        return None

    async def _cleanup_session(self, pc: RTCPeerConnection, session: VoiceSession):
        """Close connection and clean up session states."""
        try:
            # Cancel any active response task
            track_info = self._get_track_info(session)
            if track_info:
                task = track_info.get("response_task")
                if task and not task.done():
                    task.cancel()
                del self._session_tracks[id(session)]

            self.active_pcs.discard(pc)
            await pc.close()
            await session.close()
            print("[WebRTC] Session cleaned up successfully.")
        except Exception as e:
            print(f"[WebRTC] Error during cleanup: {e}")
