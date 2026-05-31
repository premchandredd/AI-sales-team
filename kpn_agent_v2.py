"""
KPN Promoters AI Voice Agent v2 — Streaming Architecture
=========================================================
Fully streaming pipeline: Deepgram STT → Groq LLM (streaming) → Sarvam TTS (WebSocket)
Targets sub-1-second voice-to-voice latency.
"""

import os
import sys
import json
import time
import base64
import asyncio
import threading
import io
import re
import numpy as np
from dotenv import load_dotenv

# ─── 1. Load Environment Variables ──────────────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

missing = []
if not GROQ_API_KEY:
    missing.append("GROQ_API_KEY")
if not SARVAM_API_KEY:
    missing.append("SARVAM_API_KEY")
if not DEEPGRAM_API_KEY:
    missing.append("DEEPGRAM_API_KEY")

if missing:
    print(f"❌ Missing API keys: {', '.join(missing)}")
    print("Please set them in your .env file.")
    print("  Get a FREE Deepgram key at: https://console.deepgram.com/signup")
    sys.exit(1)

# ─── 2. Imports (after env check so errors are clear) ───────────────────────────
try:
    from groq import AsyncGroq
    import sounddevice as sd
    import pygame
    import websockets
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Run:  pip install groq sounddevice pygame websockets deepgram-sdk numpy python-dotenv")
    sys.exit(1)

def _ws_is_open(ws):
    """Check if a websocket connection is open (compatible with all versions)."""
    if ws is None:
        return False
    # websockets v14+ uses .state instead of .open
    if hasattr(ws, 'open'):
        return ws.open
    try:
        from websockets.protocol import State
        return ws.state is State.OPEN
    except (ImportError, AttributeError):
        return True  # assume open if we can't check

# ─── 3. Initialize Clients ─────────────────────────────────────────────────────
groq_client = AsyncGroq(api_key=GROQ_API_KEY)
pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

# ─── 4. Conversation State ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Priya, a friendly AI sales consultant for KPN Promoters in Chennai.

PERSONALITY:
- Warm, professional, and genuinely helpful
- Speak naturally like a real person, not a robot
- Use conversational fillers occasionally ("Well,", "You know,", "Actually,")
- Show enthusiasm about the properties

RULES:
- Keep EVERY response to 1-2 SHORT sentences maximum (this is a phone call!)
- Never use bullet points, lists, or long explanations
- Ask ONE question at a time
- If the customer seems uninterested, gracefully acknowledge and don't push

CONVERSATION FLOW:
1. Greet warmly and introduce yourself
2. Ask if they're looking for a home in Chennai
3. Mention Omega Town (premium plots in ECR/OMR area)
4. Highlight: DTCP approved, gated community, starting at ₹15L
5. Goal: Get them to agree to a FREE site visit this weekend
6. If they agree, ask for preferred day (Saturday/Sunday) and time

OBJECTION HANDLING:
- "Too expensive" → "I understand! We actually have flexible payment plans. Would you like to know more?"
- "Not interested" → "No problem at all! Can I just share our brochure on WhatsApp for future reference?"
- "Already bought" → "That's wonderful! Congratulations! Are any of your friends or family looking?"

IMPORTANT: You are on a phone call. Be brief. Be natural. Sound human."""

conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ─── 5. Global State ───────────────────────────────────────────────────────────
playback_interrupted = False
is_agent_speaking = False
current_playback_chunks = []  # Buffer for audio chunks being played


# ─── 6. Deepgram Streaming STT ─────────────────────────────────────────────────
class StreamingSTT:
    """Real-time speech-to-text using Deepgram WebSocket streaming."""
    
    def __init__(self):
        self.ws = None
        self.transcript_buffer = []
        self.final_transcript = ""
        self.is_listening = False
        self.utterance_complete = asyncio.Event()
        self.audio_stream = None
        self._ws_url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?model=nova-2"
            f"&encoding=linear16"
            f"&sample_rate=16000"
            f"&channels=1"
            f"&punctuate=true"
            f"&interim_results=true"
            f"&endpointing=400"
            f"&utterance_end_ms=1200"
            f"&vad_events=true"
            f"&smart_format=true"
        )
    
    async def connect(self):
        """Establish WebSocket connection to Deepgram."""
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        self.ws = await websockets.connect(
            self._ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        )
        self.is_listening = True
        self.transcript_buffer = []
        self.final_transcript = ""
        self.utterance_complete.clear()
        print("🎤 Listening... (speak now)")
    
    async def send_audio(self):
        """Capture microphone audio and stream to Deepgram in real-time."""
        loop = asyncio.get_event_loop()
        audio_queue = asyncio.Queue()
        
        def audio_callback(indata, frames, time_info, status):
            """Called by sounddevice for each audio chunk (runs in separate thread)."""
            if self.is_listening:
                # Put raw bytes into the async queue
                loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))
        
        # Open microphone stream — 16kHz, mono, 16-bit
        self.audio_stream = sd.RawInputStream(
            samplerate=16000,
            channels=1,
            dtype='int16',
            blocksize=512,  # ~32ms chunks for low latency
            callback=audio_callback,
        )
        self.audio_stream.start()
        
        try:
            while self.is_listening:
                try:
                    data = await asyncio.wait_for(audio_queue.get(), timeout=0.1)
                    if self.ws and _ws_is_open(self.ws):
                        await self.ws.send(data)
                except asyncio.TimeoutError:
                    continue
        finally:
            self.audio_stream.stop()
            self.audio_stream.close()
    
    async def receive_transcripts(self):
        """Receive and process transcription results from Deepgram."""
        try:
            async for message in self.ws:
                data = json.loads(message)
                msg_type = data.get("type", "")
                
                if msg_type == "Results":
                    alt = data.get("channel", {}).get("alternatives", [{}])[0]
                    transcript = alt.get("transcript", "")
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)
                    
                    if transcript:
                        if is_final:
                            self.transcript_buffer.append(transcript)
                            print(f"  📝 {transcript}")
                            
                            if speech_final:
                                # User finished speaking! 
                                self.final_transcript = " ".join(self.transcript_buffer)
                                self.utterance_complete.set()
                                return
                        else:
                            # Interim result — show for feedback but don't store
                            print(f"  💭 {transcript}", end="\r")
                
                elif msg_type == "UtteranceEnd":
                    # Backup trigger: Deepgram detected utterance end
                    if self.transcript_buffer:
                        self.final_transcript = " ".join(self.transcript_buffer)
                        self.utterance_complete.set()
                        return
                        
        except websockets.exceptions.ConnectionClosed:
            if self.transcript_buffer:
                self.final_transcript = " ".join(self.transcript_buffer)
                self.utterance_complete.set()
    
    async def listen_for_utterance(self):
        """Listen for a complete user utterance. Returns the transcript text."""
        await self.connect()
        
        # Run audio sending and transcript receiving concurrently
        send_task = asyncio.create_task(self.send_audio())
        recv_task = asyncio.create_task(self.receive_transcripts())
        
        # Wait for utterance to complete
        await self.utterance_complete.wait()
        
        # Clean up
        self.is_listening = False
        
        # Send close signal to Deepgram
        if self.ws and _ws_is_open(self.ws):
            await self.ws.send(json.dumps({"type": "CloseStream"}))
            await self.ws.close()
        
        # Cancel tasks
        send_task.cancel()
        recv_task.cancel()
        try:
            await send_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await recv_task
        except (asyncio.CancelledError, Exception):
            pass
        
        return self.final_transcript.strip()


# ─── 7. Groq Streaming LLM ─────────────────────────────────────────────────────
async def get_llm_response_streaming(user_text):
    """
    Stream LLM response token-by-token using Groq asynchronously.
    Yields text chunks suitable for TTS as they arrive.
    """
    conversation_history.append({"role": "user", "content": user_text})
    
    # Use streaming for token-by-token response
    stream = await groq_client.chat.completions.create(
        messages=conversation_history,
        model="llama-3.3-70b-versatile",
        stream=True,
        temperature=0.7,
        max_tokens=500,  # Keep responses short for phone calls, but enough for Indic scripts
    )
    
    full_response = ""
    sentence_buffer = ""
    sentence_endings = re.compile(r'[.!?,;:\n।॥]')
    
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            full_response += token
            sentence_buffer += token
            
            # Yield chunks at sentence boundaries for natural TTS
            if sentence_endings.search(sentence_buffer) and len(sentence_buffer.strip()) > 10:
                yield sentence_buffer.strip()
                sentence_buffer = ""
    
    # Yield any remaining text
    if sentence_buffer.strip():
        yield sentence_buffer.strip()
    
    # Save full response to conversation history
    conversation_history.append({"role": "assistant", "content": full_response})
    print(f"\n🤖 AI: {full_response}")


# ─── 8. Sarvam WebSocket Streaming TTS ─────────────────────────────────────────
class StreamingTTS:
    """Real-time text-to-speech using Sarvam WebSocket API."""
    
    def __init__(self):
        self.ws = None
        self.audio_queue = asyncio.Queue()
        self.is_connected = False
    
    async def connect(self):
        """Initialize TTS — uses REST API (Sarvam WebSocket is unreliable)."""
        self.is_connected = False
    
    async def synthesize_streaming(self, text_chunk):
        """Send a text chunk for synthesis and receive audio chunks."""
        if not self.is_connected or not self.ws or not _ws_is_open(self.ws):
            # Fallback: use REST API
            await self._synthesize_rest(text_chunk)
            return
        
        try:
            # Send text for synthesis
            message = {
                "type": "text",
                "data": {"text": text_chunk}
            }
            await self.ws.send(json.dumps(message))
            
            # Send flush to get audio back
            await self.ws.send(json.dumps({"type": "flush"}))
            
            # Receive audio chunks
            while True:
                try:
                    response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "audio" and "data" in data:
                        audio_b64 = data["data"].get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await self.audio_queue.put(audio_bytes)
                    
                    elif data.get("type") in ("flush_complete", "done", "completion"):
                        break
                        
                except asyncio.TimeoutError:
                    break
                    
        except Exception as e:
            print(f"⚠️ WebSocket TTS error: {e}, falling back to REST")
            await self._synthesize_rest(text_chunk)
    
    async def _synthesize_rest(self, text_chunk):
        """Fallback: REST API synthesis using Deepgram Aura (Ultra-fast)."""
        import requests
        
        # Using Deepgram Aura for ultra-low latency TTS
        url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
        payload = {"text": text_chunk}
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, headers=headers, timeout=10)
            )
            
            if response.status_code == 200:
                # Deepgram returns raw MP3 bytes directly
                await self.audio_queue.put(response.content)
            else:
                print(f"❌ Deepgram TTS Error: {response.status_code} - {response.text[:100]}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot reach Deepgram TTS API — check your internet connection!")
        except Exception as e:
            print(f"❌ TTS REST Error: {e}")
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.ws and _ws_is_open(self.ws):
            await self.ws.close()
        self.is_connected = False


# ─── 9. Audio Playback Engine ──────────────────────────────────────────────────
class AudioPlayer:
    """Plays audio chunks from a queue with barge-in support."""
    
    def __init__(self):
        self.is_playing = False
        self.interrupted = False
    
    async def play_queue(self, audio_queue, interrupt_check=None):
        """Play audio chunks from queue. Stops if interrupted."""
        global is_agent_speaking
        self.is_playing = True
        self.interrupted = False
        is_agent_speaking = True
        
        while True:
            try:
                audio_bytes = await asyncio.wait_for(audio_queue.get(), timeout=3.0)
            except asyncio.TimeoutError:
                break
            
            # None is the sentinel value indicating stream is complete
            if audio_bytes is None:
                break
            
            if self.interrupted:
                break
            
            # Play audio chunk in memory (no disk I/O!)
            try:
                audio_io = io.BytesIO(audio_bytes)
                
                # Run pygame in executor to not block async loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._play_chunk_sync, audio_io)
                
            except Exception as e:
                print(f"⚠️ Playback error: {e}")
                continue
        
        self.is_playing = False
        is_agent_speaking = False
    
    def _play_chunk_sync(self, audio_io):
        """Synchronous audio playback (runs in thread pool)."""
        try:
            pygame.mixer.music.load(audio_io)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if self.interrupted:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.02)  # 20ms check interval
            
            pygame.mixer.music.unload()
        except Exception:
            pass
    
    def interrupt(self):
        """Signal to stop playback immediately."""
        self.interrupted = True
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


# ─── 10. Main Orchestrator (Always-Listening) ──────────────────────────────────

class PersistentListener:
    """
    Keeps the microphone ALWAYS open and Deepgram ALWAYS connected.
    This eliminates dead zones between conversation turns.
    """
    
    def __init__(self):
        self.ws = None
        self.audio_stream = None
        self.is_running = False
        self.muted = False  # Mute mic-to-Deepgram while AI speaks (prevents echo)
        self.transcript_buffer = []
        self.utterance_ready = asyncio.Event()
        self.final_transcript = ""
        self._audio_queue = asyncio.Queue()
        self._ws_url = (
            "wss://api.deepgram.com/v1/listen"
            "?model=nova-2"
            "&encoding=linear16"
            "&sample_rate=16000"
            "&channels=1"
            "&punctuate=true"
            "&interim_results=true"
            "&endpointing=800"
            "&utterance_end_ms=1500"
            "&vad_events=true"
            "&smart_format=true"
        )
    
    async def start(self):
        """Start the persistent microphone + Deepgram connection."""
        self.is_running = True
        
        # Start microphone
        loop = asyncio.get_event_loop()
        
        def audio_callback(indata, frames, time_info, status):
            if self.is_running and not self.muted:
                try:
                    loop.call_soon_threadsafe(self._audio_queue.put_nowait, bytes(indata))
                except RuntimeError:
                    pass  # Event loop closed during shutdown
        
        self.audio_stream = sd.RawInputStream(
            samplerate=16000,
            channels=1,
            dtype='int16',
            blocksize=512,
            callback=audio_callback,
        )
        self.audio_stream.start()
        
        # Connect to Deepgram
        await self._connect_deepgram()
        
        # Start background tasks
        self._send_task = asyncio.create_task(self._send_audio_loop())
        self._recv_task = asyncio.create_task(self._receive_loop())
        
        print("🎤 Microphone is always on — speak anytime!")
    
    async def _connect_deepgram(self):
        """Connect (or reconnect) to Deepgram."""
        try:
            if self.ws:
                try:
                    await self.ws.close()
                except Exception:
                    pass
            
            headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
            self.ws = await websockets.connect(
                self._ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
            )
        except Exception as e:
            print(f"⚠️ Deepgram connection error: {e}")
    
    async def _send_audio_loop(self):
        """Continuously send microphone audio to Deepgram."""
        while self.is_running:
            try:
                data = await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
                if not self.muted and self.ws and _ws_is_open(self.ws):
                    await self.ws.send(data)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("🔄 Reconnecting to Deepgram...")
                await self._connect_deepgram()
            except Exception:
                continue
    
    async def _receive_loop(self):
        """Continuously receive transcripts from Deepgram."""
        while self.is_running:
            try:
                if not self.ws or not _ws_is_open(self.ws):
                    await asyncio.sleep(0.5)
                    await self._connect_deepgram()
                    continue
                
                message = await self.ws.recv()
                data = json.loads(message)
                msg_type = data.get("type", "")
                
                if msg_type == "Results":
                    alt = data.get("channel", {}).get("alternatives", [{}])[0]
                    transcript = alt.get("transcript", "")
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)
                    
                    if transcript:
                        if is_final:
                            self.transcript_buffer.append(transcript)
                            print(f"  📝 {transcript}")
                            
                            if speech_final:
                                self.final_transcript = " ".join(self.transcript_buffer)
                                self.transcript_buffer = []
                                self.utterance_ready.set()
                        else:
                            print(f"  💭 {transcript}     ", end="\r")
                
                elif msg_type == "UtteranceEnd":
                    if self.transcript_buffer:
                        self.final_transcript = " ".join(self.transcript_buffer)
                        self.transcript_buffer = []
                        self.utterance_ready.set()
                        
            except websockets.exceptions.ConnectionClosed:
                print("🔄 Reconnecting to Deepgram...")
                await self._connect_deepgram()
            except Exception:
                continue
    
    def mute(self):
        """Mute mic→Deepgram to prevent echo while AI speaks."""
        self.muted = True
        # Drain any queued audio so stale data doesn't get sent later
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except Exception:
                break
    
    def unmute(self):
        """Resume sending mic audio to Deepgram."""
        self.muted = False
        # Clear any stale transcripts from while AI was speaking
        self.transcript_buffer = []
    
    async def wait_for_utterance(self):
        """Wait for the user to finish speaking. Returns transcript."""
        self.utterance_ready.clear()
        self.final_transcript = ""
        self.transcript_buffer = []  # Clear stale buffer
        print("\n🎤 Listening... (speak now)")
        
        await self.utterance_ready.wait()
        return self.final_transcript.strip()
    
    async def stop(self):
        """Stop listening."""
        self.is_running = False
        
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
        
        if self.ws and _ws_is_open(self.ws):
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass
        
        self._send_task.cancel()
        self._recv_task.cancel()


# Global reference to listener so TTS functions can mute/unmute
_listener = None

async def respond_with_tts(text):
    """Generate TTS for text and play it."""
    if _listener:
        _listener.mute()
    
    tts = StreamingTTS()
    player = AudioPlayer()
    await tts.connect()
    
    playback_task = asyncio.create_task(player.play_queue(tts.audio_queue))
    await tts.synthesize_streaming(text)
    await tts.audio_queue.put(None)
    
    try:
        await asyncio.wait_for(playback_task, timeout=15.0)
    except asyncio.TimeoutError:
        player.interrupt()
    await tts.close()
    
    if _listener:
        _listener.unmute()


async def respond_streaming(user_text):
    """Stream LLM response and play TTS concurrently."""
    if _listener:
        _listener.mute()
    
    tts = StreamingTTS()
    player = AudioPlayer()
    await tts.connect()
    
    playback_task = asyncio.create_task(player.play_queue(tts.audio_queue))
    
    print("🤖 AI: ", end="", flush=True)
    async for text_chunk in get_llm_response_streaming(user_text):
        if player.interrupted:
            break
        await tts.synthesize_streaming(text_chunk)
    
    await tts.audio_queue.put(None)
    
    try:
        await asyncio.wait_for(playback_task, timeout=30.0)
    except asyncio.TimeoutError:
        player.interrupt()
    await tts.close()
    
    if _listener:
        _listener.unmute()


async def main():
    """Main entry point for the streaming voice agent."""
    print("=" * 60)
    print("  🏠 KPN Promoters AI Voice Agent v2")
    print("  ⚡ Streaming Architecture — Low Latency Mode")
    print("=" * 60)
    print()
    print("📋 Pipeline: Deepgram STT → Groq LLM → Sarvam TTS")
    print("💡 Say 'bye' or 'exit' to end the call.")
    print()
    
    # Start persistent listener (microphone always on!)
    global _listener
    listener = PersistentListener()
    _listener = listener
    await listener.start()
    
    # Play greeting
    greeting = "Hello! I'm Priya from KPN Promoters. How are you doing today?"
    conversation_history.append({"role": "assistant", "content": greeting})
    print(f"🤖 AI: {greeting}")
    await respond_with_tts(greeting)
    
    # Main conversation loop
    while True:
        try:
            # Wait for user to speak (listener is ALWAYS on)
            user_text = await listener.wait_for_utterance()
            
            if not user_text:
                continue
            
            print(f"\n👤 User: {user_text}")
            
            # Check for exit
            exit_words = {"bye", "goodbye", "exit", "quit", "stop", "end call", 
                         "hang up", "bye bye", "bye-bye"}
            cleaned = user_text.lower().strip().rstrip('.!?,')
            if cleaned in exit_words or "bye" in cleaned.split():
                farewell = "Thank you for your time! Have a wonderful day. Goodbye!"
                conversation_history.append({"role": "assistant", "content": farewell})
                print(f"🤖 AI: {farewell}")
                await respond_with_tts(farewell)
                break
            
            # Generate and speak response
            await respond_streaming(user_text)
            
        except KeyboardInterrupt:
            print("\n\n👋 Call ended by user.")
            break
        except Exception as e:
            print(f"\n⚠️ Error: {e}")
            continue
    
    # Clean up
    await listener.stop()
    print("\n✅ Session complete. Thank you!")
    pygame.mixer.quit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

