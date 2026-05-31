"""
Agent Engine — Real-time voice pipeline over WebSocket.
Adapted from kpn_agent_v2.py for browser-based operation.

Pipeline: Browser Mic → WebSocket → Deepgram STT → Groq LLM → Sarvam TTS → WebSocket → Browser Speaker
"""

import os
import re
import json
import asyncio
import base64
import time
import datetime
from typing import AsyncGenerator, Optional, List, Dict, Any

import httpx
import websockets
from groq import AsyncGroq
from dotenv import load_dotenv

import google_service
import db

# Load env from parent directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

groq_client = AsyncGroq(api_key=GROQ_API_KEY)


def _ws_is_open(ws) -> bool:
    """Check if a websocket connection is open (compatible with websockets v14+)."""
    if ws is None:
        return False
    if hasattr(ws, 'open'):
        return ws.open
    try:
        from websockets.protocol import State
        return ws.state is State.OPEN
    except (ImportError, AttributeError):
        pass
    if hasattr(ws, 'closed'):
        return not ws.closed
    return True


class XmlStreamFilter:
    """
    Filters out XML-like tool call blocks (e.g. <function/...>...</function>)
    from a streaming token stream to prevent them from leaking into client text/audio.
    """
    def __init__(self):
        self.buffer = ""
        self.in_hidden_block = False
        self.hidden_tag_type = None
        self.trigger_prefixes = ["<function", "<tool_call", "<python", "<call", "<event", "<tool"]

    def feed(self, text: str) -> str:
        self.buffer += text
        output = ""

        while self.buffer:
            if not self.in_hidden_block:
                idx = self.buffer.find("<")
                if idx == -1:
                    output += self.buffer
                    self.buffer = ""
                    break
                else:
                    output += self.buffer[:idx]
                    self.buffer = self.buffer[idx:]

                    # Check if buffer starts with a trigger prefix (case-insensitive)
                    matched_any = False
                    for prefix in self.trigger_prefixes:
                        if self.buffer.lower().startswith(prefix.lower()):
                            self.in_hidden_block = True
                            self.hidden_tag_type = prefix[1:].lower()
                            matched_any = True
                            break

                    if self.in_hidden_block:
                        continue

                    # Check if buffer is a potential prefix of any trigger prefix
                    is_potential = False
                    for prefix in self.trigger_prefixes:
                        if prefix.lower().startswith(self.buffer.lower()):
                            is_potential = True
                            break

                    if is_potential:
                        break
                    else:
                        output += self.buffer[0]
                        self.buffer = self.buffer[1:]
            else:
                closing_tag = f"</{self.hidden_tag_type}>"
                idx = self.buffer.lower().find(closing_tag.lower())
                if idx != -1:
                    self.buffer = self.buffer[idx + len(closing_tag):]
                    self.in_hidden_block = False
                    self.hidden_tag_type = None
                else:
                    if len(self.buffer) > 2000:
                        output += self.buffer
                        self.buffer = ""
                        self.in_hidden_block = False
                        self.hidden_tag_type = None
                    break
        return output

    def flush(self) -> str:
        output = ""
        if not self.in_hidden_block:
            output = self.buffer
        self.buffer = ""
        return output


def _is_mp3_data(data: bytes) -> bool:
    """Detect if audio data is MP3 by checking for MP3 sync word or ID3 header."""
    if len(data) < 3:
        return False
    # MP3 frame sync: first 11 bits set (0xFF followed by 0xE0+ mask)
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    # ID3v2 tag header
    if data[:3] == b'ID3':
        return True
    return False


def decode_mp3_to_pcm(mp3_bytes: bytes, target_sample_rate: int = 16000) -> bytes:
    """
    Decode compressed audio (MP3) to raw PCM s16 mono at the target sample rate.
    If the data is already raw PCM (not MP3), return it as-is.
    """
    if not mp3_bytes:
        return b""
    if not _is_mp3_data(mp3_bytes):
        # Already raw PCM, return directly
        return mp3_bytes

    import io
    import av
    try:
        input_file = io.BytesIO(mp3_bytes)
        container = av.open(input_file)
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format='s16', layout='mono', rate=target_sample_rate)

        pcm_buffer = bytearray()
        for frame in container.decode(stream):
            resampled_frames = resampler.resample(frame)
            for r_frame in resampled_frames:
                pcm_buffer.extend(bytes(r_frame.planes[0]))
        
        # Flush resampler
        flushed_frames = resampler.resample(None)
        for r_frame in flushed_frames:
            pcm_buffer.extend(bytes(r_frame.planes[0]))

        return bytes(pcm_buffer)
    except Exception as e:
        print(f"[TTS] Error decoding MP3 to PCM: {e}")
        return b""


class VoiceSession:
    """
    Manages a single voice conversation session between the browser/telephony and AI agent.
    Each session maintains its own conversation history and audio pipeline.
    """

    def __init__(self, agent_config: dict, is_twilio: bool = False):
        self.agent_config = agent_config
        self.is_twilio = is_twilio
        self.user_id = agent_config.get("user_id", db.MOCK_USER_ID)
        self.system_prompt = agent_config.get("system_prompt", "You are a helpful assistant.")
        self.first_message = agent_config.get("first_message", "Hello! How can I help you?")
        
        # Smart Upgrade: Force Llama 3.3 70B and 500 tokens if agent is using the old broken defaults
        stored_model = agent_config.get("model", "llama-3.3-70b-versatile")
        self.model = "llama-3.3-70b-versatile" if stored_model == "llama-3.1-8b-instant" else stored_model
        
        self.voice = agent_config.get("voice", "aura-asteria-en")
        
        stored_max_tokens = agent_config.get("max_tokens", 500)
        self.max_tokens = 500 if stored_max_tokens <= 150 else stored_max_tokens
        
        self.temperature = agent_config.get("temperature", 0.7)

        # Extract Sarvam TTS language code from "Label|code" format
        raw_language = agent_config.get("language", "English (Indian)|en-IN")
        if "|" in raw_language:
            self.tts_language_code = raw_language.split("|", 1)[1]
        else:
            self.tts_language_code = "en-IN"

        self.conversation_history = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.is_active = False
        self.deepgram_ws = None
        self.transcript_buffer = []
        self.start_time = None
        
        self.spreadsheet_id = None
        self.sheet_name = None
        self.lead_row = None
        self.lead_details = {}
        
        # Persistent Sarvam WS
        self.sarvam_ws = None
        self.sarvam_speaker = None
        
        self.live_transfer_enabled = agent_config.get("live_transfer_enabled", False)
        self.live_transfer_number = agent_config.get("live_transfer_number", "")
        self.call_transferred = False
        self.has_knowledge_base = False
        self.transfer_destination = ""
        self.is_webrtc = False
    async def prepare_session(self, spreadsheet_id=None, sheet_name=None, lead_row=None, lead_id=None):
        """Prepare the session by injecting lead details and connection instructions into the system prompt."""
        # Scope the contextvar for the current thread/coroutine execution
        token_ctx = google_service.current_user_id.set(self.user_id)
        self.spreadsheet_id = spreadsheet_id or self.agent_config.get("google_sheets_id")
        self.sheet_name = sheet_name or self.agent_config.get("google_sheets_name")
        self.lead_row = lead_row

        # 1. Attempt to load client details (either from lead_id in campaigns, or directly from sheet)
        if lead_id and db.supabase:
            try:
                res = await asyncio.to_thread(
                    lambda: db.supabase.table("campaign_leads").select("custom_data", "lead_row").eq("id", lead_id).execute()
                )
                if res.data:
                    data_row = res.data[0]
                    self.lead_details = data_row.get("custom_data") or {}
                    if not self.lead_row:
                        self.lead_row = data_row.get("lead_row")
                    print(f"[VoiceSession] Loaded client details from Supabase campaign lead {lead_id}: {self.lead_details}")
            except Exception as e:
                print(f"[VoiceSession] Error reading lead custom_data from DB: {e}")

        # If not loaded yet, fetch from spreadsheet row
        if not self.lead_details and self.spreadsheet_id and self.sheet_name and self.lead_row:
            try:
                # Fetch row data asynchronously
                rows = await asyncio.to_thread(google_service.get_sheet_data, self.spreadsheet_id, self.sheet_name)
                for r in rows:
                    if r.get("__row__") == int(self.lead_row):
                        self.lead_details = r
                        break
            except Exception as e:
                print(f"[VoiceSession] Error preparing sheet data: {e}")

        # Inject customer info to system prompt if available
        if self.lead_details:
            lead_info = "\n".join([f"- {k}: {v}" for k, v in self.lead_details.items() if k != "__row__"])
            self.system_prompt += f"\n\n### CURRENT CALL CLIENT DETAILS:\n{lead_info}"

        # 2. Personalized dynamic greeting placeholder substitution
        if self.lead_details:
            # Match any placeholder like {{name}}, {{Name}}, {Name}, {company_name}
            def replace_placeholder(match):
                placeholder = match.group(1).strip()
                # Case-insensitive match in lead_details
                for key, val in self.lead_details.items():
                    if key.lower() == placeholder.lower() and key != "__row__":
                        return str(val) if val is not None else ""
                return ""  # fallback to empty if column is not found
            
            # Sub double curly braces
            self.first_message = re.sub(r'\{\{(.*?)\}\}', replace_placeholder, self.first_message)
            # Sub single curly braces
            self.first_message = re.sub(r'\{([^{}]+)\}', replace_placeholder, self.first_message)

        # Legacy backward-compatible fallback for {Name}
        name_val = self.lead_details.get("Name") or self.lead_details.get("name") or ""
        if "{Name}" in self.first_message:
            self.first_message = self.first_message.replace("{Name}", name_val)

        # Normalize multiple spaces and trailing spaces
        self.first_message = re.sub(r'\s+', ' ', self.first_message)
        # Normalize space around punctuation (e.g. "Hi , thanks" -> "Hi, thanks")
        self.first_message = re.sub(r'\s+([.,!?;:])', r'\1', self.first_message)
        self.first_message = self.first_message.strip()        # Dynamic connection instructions
        integration_prompt = []
        if self.agent_config.get("google_sheets_enabled") and self.spreadsheet_id and self.sheet_name:
            # Dynamically fetch the columns of the sheet to tell the agent exactly what details are required
            try:
                # Retrieve column headers with a 250ms timeout to avoid any setup latency
                headers = await asyncio.wait_for(
                    asyncio.to_thread(google_service.get_sheet_headers, self.spreadsheet_id, self.sheet_name),
                    timeout=0.25
                )
            except asyncio.TimeoutError:
                print("[VoiceSession] Sheets columns fetch timed out (250ms limit), using fallback/defaults")
                headers = ["Name", "Phone", "Status", "Notes"]
            except Exception as e:
                print(f"[VoiceSession] Error fetching sheet headers during prep: {e}")
                headers = ["Name", "Phone", "Status", "Notes"]

            if headers:
                # Find columns that are already filled vs missing
                filled_cols = {}
                missing_cols = []
                for h in headers:
                    val = self.lead_details.get(h, "")
                    if val and str(val).strip() and str(val).lower() != "null":
                        filled_cols[h] = val
                    else:
                        if h not in ["Status", "Notes"]:  # Status and Notes are handled post-call
                            missing_cols.append(h)

                columns_list = ", ".join([f"'{h}'" for h in headers])
                integration_prompt.append(
                    "### GOOGLE SHEETS CRM INTEGRATION\n"
                    "- The call details will be saved to a Google Sheets CRM spreadsheet automatically after the call ends.\n"
                    f"- CRITICAL MISSION: Your main task is to converse naturally and collect or confirm information for all the following CRM fields/columns: {columns_list}.\n"
                    "- Keep your questions conversational, brief, and friendly. Do not list all fields at once; ask for them one by one naturally."
                )

                if filled_cols:
                    known_info = "\n".join([f"- {k}: {v}" for k, v in filled_cols.items()])
                    integration_prompt.append(
                        f"### ALREADY KNOWN CLIENT DETAILS (DO NOT ask for these, they are already known):\n{known_info}"
                    )
                if missing_cols:
                    missing_list = ", ".join([f"'{m}'" for m in missing_cols])
                    integration_prompt.append(
                        f"### MISSING DETAILS TO GATHER (Steer the call to collect these):\n"
                        f"- You MUST collect the following missing details from the caller: {missing_list}.\n"
                        f"- Actively steer the conversation to gather these fields one by one. Do not skip any."
                    )
            else:
                integration_prompt.append(
                    "### GOOGLE SHEETS CRM INTEGRATION\n"
                    "- The call details will be saved to a Google Sheets CRM spreadsheet automatically after the call ends.\n"
                    "- Your task is to converse naturally and collect/confirm the customer's name, phone number, location, and key notes/status of interest."
                )

        calendar_enabled = self.agent_config.get("google_calendar_enabled") and self.agent_config.get("google_calendar_id")
        if not calendar_enabled:
            # Remove "Schedule appointments" block from system prompt if calendar integration is disabled
            self.system_prompt = re.sub(
                r'### Schedule appointments\s*\n(?:[^\n]*\n)*?(?=\n*###|\Z)',
                '',
                self.system_prompt
            )
            self.system_prompt = re.sub(r'\n{3,}', '\n\n', self.system_prompt)

        if calendar_enabled:
            integration_prompt.append(
                "### GOOGLE CALENDAR INTEGRATION\n"
                "- You can book appointments for the customer.\n"
                "- CRITICAL: Before offering or confirming an appointment time, you MUST check if that slot is free using the `check_calendar_availability` tool.\n"
                "- If the customer suggests a time, check availability first. If it's busy, politely inform them and suggest alternative open times.\n"
                "- Once a mutually agreed free slot is found, book it immediately using the `book_appointment` tool during the call."
            )
        else:
            integration_prompt.append(
                "### GOOGLE CALENDAR DISABLE NOTICE (CRITICAL)\n"
                "- Google Calendar appointment booking is DISABLED for this call. Do NOT offer to book an appointment or schedule a slot. "
                "Do NOT ask the customer for preferred times, dates, or details for booking. "
                "If the customer asks to schedule or book an appointment, politely explain that you can note down their preferred timing for a callback instead, but you cannot book it directly on the calendar."
            )
            
        # Check if email notifications or follow-ups are enabled
        calendar_email_enabled = self.agent_config.get("email_notifications_enabled", False)
        followup_email_enabled = self.agent_config.get("email_integration_enabled", False)
        
        if calendar_email_enabled or followup_email_enabled:
            # Check if we already have a valid email in the client details
            existing_email = (
                self.lead_details.get("Email") or 
                self.lead_details.get("email") or 
                self.lead_details.get("customer_email") or 
                self.lead_details.get("Customer Email") or 
                ""
            ).strip()
            
            if not existing_email:
                integration_prompt.append(
                    "### CRITICAL: COLLECT CUSTOMER EMAIL\n"
                    "- An automated email (e.g. appointment confirmation or follow-up details) needs to be sent to the customer after this call.\n"
                    "- Since we do NOT have the customer's email address in our database, you MUST ask the customer for their email address during the call.\n"
                    "- Ask for it politely (e.g., 'To send you the details, could I get your email address?').\n"
                    "- GUIDANCE FOR SPELLING AND DIGITS:\n"
                    "  1. Listen very carefully if the customer spells out their email letter-by-letter or says any numbers.\n"
                    "  2. If they say a number like 'one', check if they mean the digit '1'. (Almost all emails use the digit '1' instead of 'one'). Ask: 'Is that the digit 1?' to confirm.\n"
                    "  3. When confirming the email back to the customer, spell it out slowly and clearly (e.g., 'So that is m-a-n-a-m dot p-r-e-m-c-h-a-n-d dot digit 1 at gmail dot com, correct?').\n"
                    "  4. If you misunderstand the spelling, ask them to spell it using phonetic words (e.g., 'M for Mary, A for Apple') so that the transcription captures it correctly."
                )

        if followup_email_enabled:
            followup_instructions = self.agent_config.get("email_integration_instructions", "")
            if followup_instructions:
                integration_prompt.append(
                    "### EMAIL FOLLOW-UP CAPABILITY\n"
                    "- You have the ability to send follow-up emails to the customer after the call based on these guidelines:\n"
                    f"  \"{followup_instructions}\"\n"
                    "- Mention to the customer that you can email them these details after the call, and ensure we have their email address."
                )

        instructions = self.agent_config.get("google_integration_instructions", "")
        if instructions and (self.agent_config.get("google_sheets_enabled") or self.agent_config.get("google_calendar_enabled")):
            integration_prompt.append(
                f"### INSTRUCTIONS ON HOW THE AGENT SHOULD CONVERT/GATHER DETAILS:\n{instructions}"
            )
            
        if integration_prompt:
            self.system_prompt += "\n\n" + "\n\n".join(integration_prompt)

        # Check if RAG Knowledge Base is enabled/present
        if db.supabase:
            try:
                # Query if this agent has any files in the knowledge base
                kb_res = await asyncio.to_thread(
                    lambda: db.supabase.table("knowledge_bases").select("id").eq("agent_id", self.agent_config["id"]).execute()
                )
                if kb_res.data:
                    self.has_knowledge_base = True
                    self.system_prompt += (
                        "\n\n### KNOWLEDGE BASE RETRIEVAL\n"
                        "- You have access to a custom database containing business-specific facts, details, or FAQs.\n"
                        "- When asked a question about details, pricing, policies, or information that is not in your prompt, "
                        "you MUST query the knowledge base using the `query_knowledge_base(query: str)` tool to get the exact facts.\n"
                        "- Never make up or guess details. If the answer is not in the knowledge base, state that you don't know and note it down."
                    )
            except Exception as e:
                print(f"[VoiceSession] Error checking knowledge base: {e}")

        # Update system content in history
        self.conversation_history[0]["content"] = self.system_prompt


    async def generate_greeting_audio(self) -> bytes | None:
        """Generate TTS audio for the agent's first message."""
        self.conversation_history.append({"role": "assistant", "content": self.first_message})
        
        # Collect streamed bytes into a single buffer for the greeting (since it plays entirely at start)
        audio_buffer = bytearray()
        async for chunk in self.stream_synthesize_speech(self.first_message):
            audio_buffer.extend(chunk)
            
        return bytes(audio_buffer) if audio_buffer else None

    async def process_audio_chunk(self, audio_data: bytes):
        """Send an audio chunk to Deepgram for transcription."""
        if _ws_is_open(self.deepgram_ws):
            try:
                await self.deepgram_ws.send(audio_data)
            except Exception as e:
                print(f"[STT] Send error: {e}")

    async def connect_stt(self):
        """Connect to Deepgram's streaming STT WebSocket."""
        # Map Sarvam lang code (e.g., 'te-IN', 'ta-IN') to Deepgram lang code
        lang_prefix = self.tts_language_code.split("-")[0]
        # Deepgram uses 'or' for Odia, 'od-IN' might be from Sarvam
        if lang_prefix == "od":
            lang_prefix = "or"
            
        stt_language = "en-IN" if lang_prefix == "en" else lang_prefix

        stt_encoding = "mulaw" if self.is_twilio else "linear16"
        stt_sample_rate = 8000 if self.is_twilio else 16000

        url = (
            "wss://api.deepgram.com/v1/listen"
            f"?language={stt_language}"
            "&model=nova-2"
            f"&encoding={stt_encoding}"
            f"&sample_rate={stt_sample_rate}"
            "&channels=1"
            "&punctuate=true"
            "&interim_results=true"
            "&endpointing=800"
            "&utterance_end_ms=2000"
            "&vad_events=true"
            "&smart_format=true"
        )
        
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        try:
            self.deepgram_ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
            )
            self.is_active = True
            self.start_time = time.time()
            return self.deepgram_ws
        except Exception as e:
            print(f"[STT] Deepgram connection failed for {stt_language}: {e}")
            print("[STT] Retrying Deepgram with fallback (en-IN + nova-2)...")
            fallback_url = (
                "wss://api.deepgram.com/v1/listen"
                "?model=nova-2"
                "&language=en-IN"
                f"&encoding={stt_encoding}"
                f"&sample_rate={stt_sample_rate}"
                "&channels=1"
                "&punctuate=true"
                "&interim_results=true"
                "&endpointing=800"
                "&utterance_end_ms=2000"
                "&vad_events=true"
                "&smart_format=true"
            )
            try:
                self.deepgram_ws = await websockets.connect(
                    fallback_url,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=10,
                )
                self.is_active = True
                self.start_time = time.time()
                return self.deepgram_ws
            except Exception as e2:
                print(f"[STT] Deepgram fallback connection failed: {e2}")
                return None

    async def receive_transcripts(self) -> AsyncGenerator[dict, None]:
        """
        Receive transcription results from Deepgram with server-side silence debouncing.
        Uses a 2.5-second silence threshold to avoid cutting off the user mid-thought.
        Yields dicts: {"type": "interim"|"final"|"utterance_end", "text": "..."}
        """
        if not self.deepgram_ws:
            return

        event_queue = asyncio.Queue()
        self.transcript_buffer = []
        self.last_speech_time = time.time()
        
        # Debounce silence threshold: 2.5 seconds
        # This is the server-side fallback. Deepgram's own endpointing (800ms)
        # and utterance_end_ms (2000ms) handle most cases. This catches edge cases
        # where Deepgram doesn't fire UtteranceEnd but the user has clearly stopped.
        SILENCE_THRESHOLD = 2.5

        async def read_deepgram_loop():
            try:
                async for message in self.deepgram_ws:
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "Results":
                        alt = data.get("channel", {}).get("alternatives", [{}])[0]
                        transcript = alt.get("transcript", "")
                        is_final = data.get("is_final", False)
                        speech_final = data.get("speech_final", False)

                        if transcript:
                            self.last_speech_time = time.time()
                            if is_final:
                                self.transcript_buffer.append(transcript)
                                await event_queue.put({"type": "final", "text": transcript})
                                # Note: We intentionally do NOT fire utterance_end on speech_final.
                                # speech_final fires after only endpointing ms (800ms) of silence,
                                # which is too aggressive for natural conversation. Instead, we let
                                # Deepgram's UtteranceEnd event (2000ms) or our silence_checker_loop
                                # (2500ms) handle the turn boundary for a more natural cadence.
                            else:
                                await event_queue.put({"type": "interim", "text": transcript})

                    elif msg_type == "SpeechStarted":
                        # User started speaking! Reset last speech time to prevent silence checker from firing prematurely.
                        self.last_speech_time = time.time()

                    elif msg_type == "UtteranceEnd":
                        if self.transcript_buffer:
                            full_text = " ".join(self.transcript_buffer).strip()
                            self.transcript_buffer = []
                            if full_text:
                                await event_queue.put({"type": "utterance_end", "text": full_text})

            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                print(f"[STT] read_deepgram_loop error: {e}")
            finally:
                # Put None to signal EOF to the queue
                await event_queue.put(None)

        async def silence_checker_loop():
            try:
                while self.is_active:
                    await asyncio.sleep(0.1)
                    if self.transcript_buffer:
                        elapsed = time.time() - self.last_speech_time
                        if elapsed >= SILENCE_THRESHOLD:
                            full_text = " ".join(self.transcript_buffer).strip()
                            self.transcript_buffer = []
                            if full_text:
                                await event_queue.put({"type": "utterance_end", "text": full_text})
            except Exception as e:
                print(f"[STT] silence_checker_loop error: {e}")

        # Start the background tasks
        read_task = asyncio.create_task(read_deepgram_loop())
        checker_task = asyncio.create_task(silence_checker_loop())

        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield event
        finally:
            read_task.cancel()
            checker_task.cancel()
            # Flush any remaining text at the end of the session
            if self.transcript_buffer:
                full_text = " ".join(self.transcript_buffer).strip()
                self.transcript_buffer = []
                if full_text:
                    yield {"type": "utterance_end", "text": full_text}

    async def generate_response(self, user_text: str) -> AsyncGenerator[str, None]:
        """
        Stream LLM response token-by-token.
        Yields text chunks at sentence boundaries for natural TTS.
        Supports dynamic tool execution for Google Sheets and Calendar.
        """
        if user_text:
            self.conversation_history.append({"role": "user", "content": user_text})

        # Dynamically build tools list
        tools = []
        if self.agent_config.get("google_calendar_enabled") and self.agent_config.get("google_calendar_id"):
            tools.append({
                "type": "function",
                "function": {
                    "name": "check_calendar_availability",
                    "description": "Check if time slots are available on the user's Google Calendar for a specific date or time range. Returns list of busy slots (existing events).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_min_iso": {
                                "type": "string",
                                "description": "The start of the range to check in ISO 8601 format, e.g., '2026-05-28T09:00:00+05:30'."
                            },
                            "time_max_iso": {
                                "type": "string",
                                "description": "The end of the range to check in ISO 8601 format, e.g., '2026-05-28T17:00:00+05:30'."
                            }
                        },
                        "required": ["time_min_iso", "time_max_iso"]
                    }
                }
            })
            tools.append({
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "Book an appointment or event in the user's Google Calendar. Call this when the customer agrees to a specific date and time for an appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time_iso": {
                                "type": "string",
                                "description": "The start time of the appointment in ISO 8601 format, e.g., '2026-05-27T14:00:00+05:30'."
                            },
                            "end_time_iso": {
                                "type": "string",
                                "description": "The end time of the appointment in ISO 8601 format, e.g., '2026-05-27T15:00:00+05:30'. Usually 30-60 minutes after start_time."
                            },
                            "summary": {
                                "type": "string",
                                "description": "A short summary of the appointment, e.g., 'Appointment setting call with John'."
                            },
                            "description": {
                                "type": "string",
                                "description": "Optional description or details about the appointment."
                            }
                        },
                        "required": ["start_time_iso", "end_time_iso", "summary"]
                    }
                }
            })

        if self.agent_config.get("google_sheets_enabled") and (self.agent_config.get("google_sheets_id") or self.spreadsheet_id):
            if self.lead_row:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "update_lead_status",
                        "description": "Update the status of the current lead in the Google Sheet. Call this when the lead qualification is determined (e.g. 'Qualified' or 'Not Qualified' or 'Interested') or to add notes.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "description": "The status of the lead, e.g. 'Qualified' or 'Not Qualified' or 'Interested'."
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Additional notes about the call or the customer."
                                }
                            },
                            "required": ["status"]
                        }
                    }
                })
            
            tools.append({
                "type": "function",
                "function": {
                    "name": "add_row_to_sheet",
                    "description": "Append a new row of data to the Google Sheet. Use this to record new lead details or collected information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "row_values": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of values to append as a new row, e.g., ['John Doe', '+1234567890', 'Qualified', 'Wants a callback']"
                            }
                        },
                        "required": ["row_values"]
                    }
                }
            })

        if self.live_transfer_enabled and self.live_transfer_number:
            tools.append({
                "type": "function",
                "function": {
                    "name": "transfer_to_human_agent",
                    "description": "Transfer the call to a human agent, manager, or support representative immediately. Call this when the customer explicitly asks to talk to a human, or if the conversation is stuck.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "The reason why the call is being transferred to a human agent."
                            }
                        },
                        "required": ["reason"]
                    }
                }
            })

        if self.has_knowledge_base:
            tools.append({
                "type": "function",
                "function": {
                    "name": "query_knowledge_base",
                    "description": "Search the knowledge base for specific business facts, FAQs, manuals, policies, or pricing details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query to match against the document chunks, e.g. 'pricing plans' or 'refund policy'."
                            }
                        },
                        "required": ["query"]
                    }
                }
            })

        try:
            kwargs = {
                "messages": self.conversation_history,
                "model": self.model,
                "stream": True,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            # Asynchronously process integrations after the call rather than mid-call to minimize voice latency.
            # We do NOT pass tools to the real-time completion stream.

            stream = await groq_client.chat.completions.create(**kwargs)

            full_response = ""
            sentence_buffer = ""
            # Split on commas and punctuation for faster, shorter chunks to reduce TTS latency
            sentence_endings = re.compile(r'([.!?,;:\n।॥])')

            tool_calls = []
            xml_filter = XmlStreamFilter()

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                
                # Check for tool calls
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        while len(tool_calls) <= idx:
                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        
                        if tc_chunk.id:
                            tool_calls[idx]["id"] = tc_chunk.id
                        if tc_chunk.function:
                            if tc_chunk.function.name:
                                tool_calls[idx]["function"]["name"] += tc_chunk.function.name
                            if tc_chunk.function.arguments:
                                tool_calls[idx]["function"]["arguments"] += tc_chunk.function.arguments
                
                token = delta.content
                if token:
                    clean_token = xml_filter.feed(token)
                    if clean_token:
                        full_response += clean_token
                        sentence_buffer += clean_token

                        # Find the last sentence ending in the buffer
                        matches = list(sentence_endings.finditer(sentence_buffer))
                        if matches and len(sentence_buffer.strip()) > 25:
                            last_match = matches[-1]
                            split_idx = last_match.end()
                            
                            chunk_to_yield = sentence_buffer[:split_idx].strip()
                            if chunk_to_yield:
                                yield chunk_to_yield
                                
                            # Keep the remainder for the next chunk!
                            sentence_buffer = sentence_buffer[split_idx:]

            # Flush any remaining text in the XML stream filter
            final_clean = xml_filter.flush()
            if final_clean:
                full_response += final_clean
                sentence_buffer += final_clean

            if sentence_buffer.strip():
                yield sentence_buffer.strip()

            if full_response.strip():
                self.conversation_history.append({"role": "assistant", "content": full_response.strip()})

            # Execute tool calls if requested by LLM
            if tool_calls:
                print(f"[LLM] Model requested tool calls: {tool_calls}")
                
                # Clean up tool calls format for Groq structure
                formatted_tool_calls = []
                for tc in tool_calls:
                    formatted_tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    })
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": formatted_tool_calls
                })
                
                for tc in formatted_tool_calls:
                    name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    tool_id = tc["id"]
                    
                    try:
                        args = json.loads(raw_args)
                    except Exception as e:
                        args = {}
                        print(f"[TOOL] Failed to parse args: {raw_args}, error: {e}")
                        
                    tool_result = {"status": "error", "message": "Unknown tool or execution failed"}
                    
                    if name == "check_calendar_availability":
                        try:
                            calendar_id = self.agent_config.get("google_calendar_id", "primary")
                            time_min = args.get("time_min_iso")
                            time_max = args.get("time_max_iso")
                            
                            res = await asyncio.to_thread(
                                google_service.check_calendar_availability,
                                calendar_id=calendar_id,
                                time_min_iso=time_min,
                                time_max_iso=time_max
                            )
                            tool_result = {"status": "success", "busy_slots": res}
                            print(f"[TOOL] Checked availability: found {len(res)} busy slots")
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                            print(f"[TOOL] Calendar check error: {e}")

                    elif name == "book_appointment":
                        try:
                            calendar_id = self.agent_config.get("google_calendar_id", "primary")
                            start_time = args.get("start_time_iso")
                            end_time = args.get("end_time_iso")
                            summary = args.get("summary")
                            description = args.get("description", "")
                            
                            res = await asyncio.to_thread(
                                google_service.book_calendar_event,
                                calendar_id=calendar_id,
                                start_time_iso=start_time,
                                end_time_iso=end_time,
                                summary=summary,
                                description=description
                            )
                            tool_result = {"status": "success", "event": res}
                            print(f"[TOOL] Calendar event booked: {res}")
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                            print(f"[TOOL] Calendar booking error: {e}")
                            
                    elif name == "update_lead_status":
                        try:
                            spreadsheet_id = self.spreadsheet_id or self.agent_config.get("google_sheets_id")
                            sheet_name = self.sheet_name or self.agent_config.get("google_sheets_name")
                            row_idx = int(self.lead_row)
                            status = args.get("status")
                            notes = args.get("notes", "")
                            
                            await asyncio.to_thread(
                                google_service.update_lead_status_in_sheet,
                                spreadsheet_id=spreadsheet_id,
                                sheet_name=sheet_name,
                                row_idx=row_idx,
                                status=status,
                                notes=notes
                            )
                            tool_result = {"status": "success", "message": f"Lead status updated to '{status}'"}
                            print(f"[TOOL] Lead status updated to {status}")
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                            print(f"[TOOL] Lead update error: {e}")
                            
                    elif name == "add_row_to_sheet":
                        try:
                            spreadsheet_id = self.spreadsheet_id or self.agent_config.get("google_sheets_id")
                            sheet_name = self.sheet_name or self.agent_config.get("google_sheets_name")
                            row_values = args.get("row_values", [])
                            
                            await asyncio.to_thread(
                                google_service.append_row_to_sheet,
                                spreadsheet_id=spreadsheet_id,
                                sheet_name=sheet_name,
                                row_values=row_values
                            )
                            tool_result = {"status": "success", "message": "Row appended successfully"}
                            print(f"[TOOL] Row appended to sheet: {row_values}")
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                            print(f"[TOOL] Append row error: {e}")

                    elif name == "transfer_to_human_agent":
                        try:
                            reason = args.get("reason", "Customer requested transfer")
                            transfer_number = self.live_transfer_number
                            print(f"[TOOL] Transferring call to human. Reason: {reason}, Number: {transfer_number}")
                            
                            await self.execute_call_transfer(transfer_number, reason)
                            tool_result = {"status": "success", "message": "Call transfer initiated successfully"}
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                            print(f"[TOOL] Transfer error: {e}")

                    elif name == "query_knowledge_base":
                        try:
                            query = args.get("query", "")
                            print(f"[TOOL] Querying knowledge base: '{query}'")
                            from rag_service import query_knowledge_base
                            res = await query_knowledge_base(self.agent_config["id"], query)
                            tool_result = {"status": "success", "retrieved_context": res}
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                            print(f"[TOOL] Knowledge base query error: {e}")
                            
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": name,
                        "content": json.dumps(tool_result)
                    })
                
                # Resubmit history to LLM to get a verbal response
                async for chunk in self.generate_response(user_text=""):
                    yield chunk

        except Exception as e:
            print(f"[LLM] Groq generation error: {e}")
            # If it fails mid-way or times out, we just yield an error message or stop gracefully
            yield " Sorry, I lost my connection. Could you repeat that?"

    # ─── TTS: Sarvam AI (Streaming WS) + Deepgram Aura (REST fallback) ───

    async def stream_synthesize_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream text-to-speech audio chunks. Tries Sarvam AI (WS) first, falls back to Deepgram."""
        success = False
        async for chunk in self._stream_tts_sarvam(text):
            success = True
            yield chunk
            
        if not success:
            print("[TTS] Sarvam WS failed, falling back to Deepgram Aura REST")
            audio = await self._tts_deepgram(text)
            if audio:
                yield audio

    async def _get_sarvam_ws(self):
        """Get or create the persistent Sarvam TTS WebSocket connection."""
        if self.sarvam_ws and hasattr(self.sarvam_ws, 'state') and self.sarvam_ws.state.name == "OPEN":
            return self.sarvam_ws

        # Dynamically map speaker based on language and gender
        gender = self.agent_config.get("voice_gender", "female").lower()
        lang_code = self.tts_language_code

        if "hi-IN" in lang_code: speaker = "ashutosh" if gender == "male" else "priya"
        elif "ta-IN" in lang_code: speaker = "aayan" if gender == "male" else "ishta"
        elif "te-IN" in lang_code: speaker = "shubh" if gender == "male" else "ritu"
        elif "kn-IN" in lang_code: speaker = "rahul" if gender == "male" else "pooja"
        elif "en-IN" in lang_code: speaker = "sumit" if gender == "male" else "simran"
        else: speaker = "shubh" if gender == "male" else "shreya"

        # Explicitly pass send_completion_event=true to detect final packets reliably without relying on early timeouts
        uri = "wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v3&send_completion_event=true"
        headers = {"api-subscription-key": SARVAM_API_KEY}
        
        try:
            print(f"[TTS] Connecting persistent Sarvam WS using '{speaker}'...")
            ws = await websockets.connect(uri, additional_headers=headers)
            
            # NOTE: Sarvam ignores PCM codec requests and always returns MP3.
            # So we always request MP3 and decode it ourselves for WebRTC.
            if self.is_twilio:
                codec = "mulaw"
                sample_rate = 8000
            else:
                codec = "mp3"
                sample_rate = 22050

            # Send configuration
            config = {
                "type": "config",
                "data": {
                    "target_language_code": self.tts_language_code,
                    "speaker": speaker,
                    "output_audio_format": {"codec": codec, "sample_rate": sample_rate}
                }
            }
            await ws.send(json.dumps(config))
            self.sarvam_ws = ws
            self.sarvam_speaker = speaker
            return ws
        except Exception as e:
            print(f"[TTS] Failed to connect Sarvam WS: {e}")
            self.sarvam_ws = None
            return None

    async def _stream_tts_sarvam(self, text: str) -> AsyncGenerator[bytes, None]:
        """Sarvam AI TTS streaming via persistent WebSocket (Ultra-low latency, MP3 format)."""
        if not SARVAM_API_KEY:
            return

        ws = await self._get_sarvam_ws()
        if not ws:
            return

        try:
            t_start = time.perf_counter()
            # Send the text chunk
            await ws.send(json.dumps({"type": "text", "data": {"text": text}}))
            await ws.send(json.dumps({"type": "flush"}))
            
            audio_buffer = bytearray()
            
            # Since connection is already open, wait up to 3.0s for packets. We break instantly on the completion event.
            current_timeout = 3.0
            
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=current_timeout)
                    data = json.loads(response)
                    
                    if data.get("type") == "audio" and "data" in data:
                        audio_b64 = data["data"].get("audio", "")
                        if audio_b64:
                            audio_buffer.extend(base64.b64decode(audio_b64))
                    elif data.get("type") == "event" and data.get("data", {}).get("event_type") == "final":
                        # Received completion event from Sarvam — synthesis complete!
                        break
                            
                except asyncio.TimeoutError:
                    print("[TTS] Timeout waiting for Sarvam audio stream")
                    break
            
            if audio_buffer:
                t_ms = (time.perf_counter() - t_start) * 1000
                print(f"[TTS] Sarvam WS phrase completed in {t_ms:.0f}ms ({len(audio_buffer)/1024:.1f}KB) using '{self.sarvam_speaker}'")
                if getattr(self, "is_webrtc", False):
                    pcm_bytes = await asyncio.to_thread(decode_mp3_to_pcm, bytes(audio_buffer))
                    yield pcm_bytes
                else:
                    yield bytes(audio_buffer)

        except Exception as e:
            print(f"[TTS] Sarvam WS Error during streaming: {e}")
            # Reset ws so we reconnect next time
            self.sarvam_ws = None

    async def _tts_deepgram(self, text: str) -> bytes | None:
        """Deepgram Aura TTS — REST fallback."""
        if self.is_twilio:
            url = f"https://api.deepgram.com/v1/speak?model={self.voice}&encoding=mulaw&sample_rate=8000&container=none"
        elif getattr(self, "is_webrtc", False):
            url = f"https://api.deepgram.com/v1/speak?model={self.voice}&encoding=linear16&sample_rate=16000&container=none"
        else:
            url = f"https://api.deepgram.com/v1/speak?model={self.voice}"
            
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        try:
            t_start = time.perf_counter()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    t_ms = (time.perf_counter() - t_start) * 1000
                    print(f"[TTS] Deepgram fallback OK ({t_ms:.0f}ms)")
                    return response.content
                else:
                    print(f"[TTS] Deepgram error: {response.status_code}")
                    return None
        except Exception as e:
            print(f"[TTS] Deepgram error: {e}")
            return None

    def get_duration_minutes(self) -> float:
        """Get session duration in minutes."""
        if self.start_time:
            return (time.time() - self.start_time) / 60.0
        return 0.0

    async def execute_call_transfer(self, transfer_number: str, reason: str):
        """Initiates call transfer by updating Twilio call SID or setting local transfer flags."""
        if self.is_twilio and getattr(self, "call_sid", None):
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            # Fetch user settings if available
            if db.supabase and self.user_id != db.MOCK_USER_ID:
                try:
                    res = await asyncio.to_thread(
                        lambda: db.supabase.table("user_settings").select("*").eq("user_id", self.user_id).execute()
                    )
                    if res.data:
                        settings = res.data[0]
                        account_sid = settings.get("twilio_account_sid") or account_sid
                        auth_token = settings.get("twilio_auth_token") or auth_token
                except Exception as e:
                    print(f"[VoiceSession] Error fetching user Twilio settings for transfer: {e}")
            
            if account_sid and auth_token:
                base_url = os.getenv("BASE_URL") or "http://localhost:8000"
                from urllib.parse import urlencode
                params = {"to_phone": transfer_number}
                redirect_url = f"{base_url}/api/telephony/transfer-twiml?{urlencode(params)}"
                
                print(f"[VoiceSession] Redirecting Twilio call {self.call_sid} to: {redirect_url}")
                try:
                    from twilio.rest import Client
                    client = Client(account_sid, auth_token)
                    await asyncio.to_thread(
                        client.calls(self.call_sid).update,
                        url=redirect_url
                    )
                    self.call_transferred = True
                    self.transfer_destination = transfer_number
                except Exception as e:
                    print(f"[VoiceSession] Twilio redirect failed: {e}")
                    raise e
            else:
                raise Exception("Twilio credentials missing for live transfer.")
        else:
            # Set browser transfer flags
            self.call_transferred = True
            self.transfer_destination = transfer_number
            print(f"[VoiceSession] Browser session transfer requested to {transfer_number}")

    async def close(self):
        """Clean up the session."""
        self.is_active = False
        if _ws_is_open(self.deepgram_ws):
            try:
                await self.deepgram_ws.send(json.dumps({"type": "CloseStream"}))
                await self.deepgram_ws.close()
            except Exception:
                pass
        if self.sarvam_ws and hasattr(self.sarvam_ws, 'state') and self.sarvam_ws.state.name == "OPEN":
            try:
                await self.sarvam_ws.close()
            except Exception:
                pass

    async def process_post_call(self):
        """
        Runs asynchronously after the voice call ends.
        Dynamically reads the actual sheet headers and extracts values for each column
        from the conversation transcript using an LLM.
        """
        google_service.current_user_id.set(self.user_id)
        # 1. Check if integrations are enabled
        sheets_enabled = self.agent_config.get("google_sheets_enabled") and (self.agent_config.get("google_sheets_id") or self.spreadsheet_id)
        calendar_enabled = self.agent_config.get("google_calendar_enabled") and self.agent_config.get("google_calendar_id")
        email_integration_enabled = self.agent_config.get("email_integration_enabled", False)
        whatsapp_enabled = self.agent_config.get("whatsapp_enabled", False)

        print("[Post-Call] Starting post-call analysis and database logging...")

        # 2. Reconstruct plaintext transcript
        transcript_lines = []
        for msg in self.conversation_history:
            role = msg.get("role")
            content = msg.get("content")
            if role in ["user", "assistant"] and content:
                name = "Customer" if role == "user" else "Agent"
                transcript_lines.append(f"{name}: {content}")

        if not transcript_lines:
            print("[Post-Call] Transcript is empty, skipping.")
            return

        transcript_text = "\n".join(transcript_lines)

        # 3. Get spreadsheet info and actual headers
        spreadsheet_id = self.spreadsheet_id or self.agent_config.get("google_sheets_id")
        sheet_name = self.sheet_name or self.agent_config.get("google_sheets_name")

        headers = []
        if sheets_enabled and spreadsheet_id and sheet_name:
            try:
                creds = google_service.get_credentials()
                if creds:
                    from googleapiclient.discovery import build
                    service = build("sheets", "v4", credentials=creds)
                    result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=f"'{sheet_name}'!A1:Z1"
                    ).execute()
                    headers = result.get("values", [[]])[0] if result.get("values") else []
                    print(f"[Post-Call] Sheet headers: {headers}")
            except Exception as e:
                print(f"[Post-Call] Error fetching sheet headers: {e}")

        if not headers and sheets_enabled:
            # Fallback headers if we can't read them
            headers = ["Name", "Phone", "Status", "Notes"]

        # 4. Build existing row data string (for outbound calls to existing leads)
        existing_row_data_formatted = "No existing data (new call / inbound)"
        if self.lead_details:
            existing_lines = []
            for h in headers:
                val = self.lead_details.get(h, "")
                existing_lines.append(f"- {h}: {val if val else '(empty)'}")
            existing_row_data_formatted = "\n".join(existing_lines)

        # 5. Build dynamic extraction prompt
        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %A")
        integration_instructions = self.agent_config.get("google_integration_instructions", "")

        headers_str = ", ".join([f'"{h}"' for h in headers])

        # Add custom email followup instructions if enabled
        email_instr_block = ""
        if email_integration_enabled:
            email_rules = self.agent_config.get("email_integration_instructions", "")
            email_instr_block = f"""
Also evaluate if a custom email follow-up should be sent based on these custom rules:
"{email_rules}"

Instructions for email:
- If the criteria in the rules are met: set email_followup.send to true. Fill in recipient_email (extracted from conversation or fallback to customer email), and generate an appropriate email subject and body in plain text format based on the rules.
- If the criteria are not met, or if no email address was mentioned/found: set email_followup.send to false with null values.
"""

        # Add WhatsApp instructions if enabled
        whatsapp_instr_block = ""
        if whatsapp_enabled:
            whatsapp_rules = self.agent_config.get("whatsapp_integration_instructions", "")
            whatsapp_instr_block = f"""
Also evaluate if a WhatsApp notification should be sent based on the call.
WhatsApp Template Name: {self.agent_config.get("whatsapp_template_name", "hello_world")}
Instructions for WhatsApp parameters:
"{whatsapp_rules}"

Instructions for WhatsApp:
- If the criteria in the rules are met: set whatsapp.send to true. Fill in recipient_phone (extracted from conversation or fallback to customer phone), and set parameters to a list of strings representing the ordered parameter values ({{{{1}}}}, {{{{2}}}}, etc.) as described in the instructions.
- If the criteria are not met, or if no phone number was found: set whatsapp.send to false with null/empty values.
"""

        system_instruction = f"""You are a precise data extraction assistant.
Analyze the conversation transcript below between an AI voice agent and a customer.

Current Date/Time: {current_time_str}

The Google Sheet has these columns: [{headers_str}]

Existing row data (if outbound call to existing lead):
{existing_row_data_formatted}

{"Agent Instructions for data collection: " + integration_instructions if integration_instructions else ""}

Instructions:
1. For EACH column listed above, extract the most relevant value from the conversation.
2. For "Status" column: classify as "New", "Interested", "Qualified", "Not Qualified", "Callback", "No Answer", or another short descriptive status.
3. For "Notes" column: write a brief professional summary of the call.
4. If a value was already present in the existing row data and was NOT corrected/updated during the call, keep the existing value.
5. If a column's value cannot be determined from the conversation AND no existing value exists, set it to null.
6. Email spelling normalization: If the customer spelled out their email address letter-by-letter or with pauses (e.g., "m a n a m dot p r e m c h a n d dot one at gmail dot com"), you MUST normalize it by removing all spaces and converting spelled-out punctuation words to symbols (e.g. "dot" to ".", "at" to "@").
7. Convert spelled-out number words in email addresses to their numeric digits if they were spoken as part of the email address (e.g., convert "one" to "1" in "premchand.1@gmail.com", or "two" to "2"). Review context carefully to ensure digits are formatted correctly.
8. Be extremely thorough. Search for indirect answers, synonyms, or contextual clues in the transcript. Do not skip any column updates if the information is present.
{email_instr_block}
{whatsapp_instr_block}
Also detect if the customer agreed to book an appointment:
- If yes: set appointment.booked to true with start_time_iso, end_time_iso (30 min later unless specified), summary, description in ISO 8601 format with timezone. Also extract the customer's email and phone number if they mentioned it, and set appointment.customer_email and appointment.customer_phone.
- If no: set appointment.booked to false with null values.

Respond with a JSON object:
{{
  "column_updates": {{
    {", ".join([f'"{h}": "value or null"' for h in headers])}
  }},
  "appointment": {{
    "booked": false,
    "start_time_iso": "string or null",
    "end_time_iso": "string or null",
    "summary": "string or null",
    "description": "string or null",
    "customer_email": "string or null",
    "customer_phone": "string or null"
  }},
  "email_followup": {{
    "send": false,
    "recipient_email": "string or null",
    "subject": "string or null",
    "body": "string or null"
  }},
  "whatsapp": {{
    "send": false,
    "recipient_phone": "string or null",
    "parameters": []
  }},
  "sentiment": "Positive, Neutral, or Negative (strictly one of these three)",
  "outcome": "Brief outcome of the call, e.g. 'Appointment booked', 'Callback requested', 'Transferred to Agent', 'Not interested', or 'Incomplete call'",
  "summary": "A brief, professional summary of the call."
}}

Respond ONLY with the JSON object. Do not add markdown code blocks, quotes, or pre/post text."""

        try:
            response = await groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Transcript:\n{transcript_text}"}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            raw_json = response.choices[0].message.content.strip()
            print(f"[Post-Call] Extracted data JSON: {raw_json}")
            extracted = json.loads(raw_json)
        except Exception as e:
            print(f"[Post-Call] Failed to extract data using LLM: {e}")
            return

        column_updates = extracted.get("column_updates", {})

        # 6. Save to Google Sheets if enabled
        if sheets_enabled and headers:
            if self.lead_row:
                # OUTBOUND: Update existing row — fill in/update each column
                row_idx = int(self.lead_row)
                try:
                    print(f"[Post-Call] Updating Google Sheet row {row_idx} with dynamic columns...")
                    for col_idx, header in enumerate(headers):
                        value = column_updates.get(header)
                        if value is not None and str(value).lower() != "null":
                            col_letter = chr(65 + col_idx) if col_idx < 26 else "Z"
                            await asyncio.to_thread(google_service.update_cell, spreadsheet_id, sheet_name, row_idx, col_letter, str(value))
                    print(f"[Post-Call] Row {row_idx} updated successfully with {len(column_updates)} columns.")
                except Exception as e:
                    print(f"[Post-Call] Sheet update error: {e}")
            else:
                # INBOUND: Append a new row matching the header order
                try:
                    row_values = []
                    for header in headers:
                        value = column_updates.get(header, "")
                        if value is None or str(value).lower() == "null":
                            value = ""
                        row_values.append(str(value))
                    print(f"[Post-Call] Appending new row to sheet: {row_values}")
                    await asyncio.to_thread(google_service.append_row_to_sheet, spreadsheet_id, sheet_name, row_values)
                except Exception as e:
                    print(f"[Post-Call] Sheet append error: {e}")

        # 7. Book calendar event if enabled and client agreed
        appt = extracted.get("appointment", {})
        if calendar_enabled and appt.get("booked"):
            calendar_id = self.agent_config.get("google_calendar_id", "primary")
            start_time = appt.get("start_time_iso")
            end_time = appt.get("end_time_iso")
            customer_name = column_updates.get("Name") or column_updates.get("name") or "Customer"
            summary = appt.get("summary") or f"Appointment with {customer_name}"
            description = appt.get("description") or ""
            
            # Fetch meet and email configuration settings
            google_meet_enabled = self.agent_config.get("google_meet_enabled", False)
            email_notifications_enabled = self.agent_config.get("email_notifications_enabled", False)
            
            # Resolve customer email
            customer_email = appt.get("customer_email") or column_updates.get("Email") or column_updates.get("email")
            if customer_email and str(customer_email).lower() in ["null", "none", ""]:
                customer_email = None

            try:
                print(f"[Post-Call] Booking calendar event on {calendar_id} (Meet: {google_meet_enabled}, Email: {customer_email})...")
                res = await asyncio.to_thread(
                    google_service.book_calendar_event,
                    calendar_id=calendar_id,
                    start_time_iso=start_time,
                    end_time_iso=end_time,
                    summary=summary,
                    description=description,
                    create_meet=google_meet_enabled,
                    attendee_email=customer_email
                )
                print(f"[Post-Call] Calendar event booked: {res}")
                
                # Send Gmail notification if enabled and customer email is available
                if email_notifications_enabled and customer_email:
                    print(f"[Post-Call] Sending confirmation email to {customer_email}...")
                    meet_link = res.get("meetLink")
                    meet_text = f"\nGoogle Meet Link: {meet_link}\n" if meet_link else ""
                    
                    email_subject = f"Appointment Confirmed: {summary}"
                    email_body = (
                        f"Hi {customer_name or 'there'},\n\n"
                        f"Your appointment has been successfully scheduled!\n\n"
                        f"Details:\n"
                        f"- Event: {summary}\n"
                        f"- Date/Time: {res.get('start') or start_time}\n"
                        f"{meet_text}\n"
                        f"Thank you,\n"
                        f"AI Voice Assistant"
                    )
                    await asyncio.to_thread(
                        google_service.send_email_via_gmail,
                        to_email=customer_email,
                        subject=email_subject,
                        body_text=email_body
                    )
            except Exception as e:
                print(f"[Post-Call] Calendar booking / email notification error: {e}")

        # 8. Send custom email follow-up if enabled
        if email_integration_enabled:
            email_f = extracted.get("email_followup", {})
            if email_f.get("send"):
                recipient = email_f.get("recipient_email") or column_updates.get("Email") or column_updates.get("email") or appt.get("customer_email")
                subject = email_f.get("subject") or "Follow-up details"
                body = email_f.get("body")
                
                if recipient and str(recipient).lower() not in ["null", "none", ""] and body:
                    try:
                        print(f"[Post-Call] Sending custom follow-up email to {recipient}...")
                        await asyncio.to_thread(
                            google_service.send_email_via_gmail,
                            to_email=str(recipient).strip(),
                            subject=subject,
                            body_text=body
                        )
                    except Exception as e:
                        print(f"[Post-Call] Custom follow-up email error: {e}")
                else:
                    print(f"[Post-Call] Custom follow-up skipped (recipient: {recipient}, body length: {len(body) if body else 0})")

        # 9. Send WhatsApp notification if enabled
        if whatsapp_enabled:
            wa_f = extracted.get("whatsapp", {})
            if wa_f.get("send"):
                phone_number_id = self.agent_config.get("whatsapp_phone_number_id")
                access_token = self.agent_config.get("whatsapp_access_token")
                recipient = wa_f.get("recipient_phone") or column_updates.get("Phone") or column_updates.get("phone") or (self.lead_details.get("Phone") if self.lead_details else "")
                template_name = self.agent_config.get("whatsapp_template_name", "hello_world")
                lang_code = self.agent_config.get("whatsapp_template_language", "en_US")
                params = wa_f.get("parameters", [])
                
                if recipient and phone_number_id and access_token:
                    try:
                        import whatsapp_service
                        print(f"[Post-Call] Sending WhatsApp to {recipient}...")
                        await whatsapp_service.send_whatsapp_template(
                            phone_number_id=phone_number_id,
                            access_token=access_token,
                            recipient_phone=str(recipient).strip(),
                            template_name=template_name,
                            language_code=lang_code,
                            parameters=params
                        )
                    except Exception as e:
                        print(f"[Post-Call] WhatsApp error: {e}")
                else:
                    print(f"[Post-Call] WhatsApp skipped (recipient: {recipient}, credentials missing: {not (phone_number_id and access_token)})")

        # 10. Save call analytics to calls table
        try:
            print("[Post-Call] Saving call log to database...")
            call_sid = getattr(self, "call_sid", None)
            duration = self.get_duration_minutes()
            
            summary = extracted.get("summary") or "No summary generated."
            sentiment = extracted.get("sentiment") or "Neutral"
            outcome = extracted.get("outcome") or "No outcome determined."
            
            # If the user transfer flag is set, force the outcome to represent it
            if getattr(self, "call_transferred", False):
                outcome = f"Transferred to Agent ({self.transfer_destination})"
            
            call_payload = {
                "agent_id": self.agent_config.get("id"),
                "user_id": self.user_id,
                "call_sid": call_sid,
                "duration": round(duration, 2),
                "transcript": transcript_text,
                "summary": summary,
                "sentiment": sentiment,
                "outcome": outcome,
                "created_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
            
            if db.supabase:
                await asyncio.to_thread(
                    db.supabase.table("calls").insert(call_payload).execute
                )
                print(f"[Post-Call] Call log saved successfully to Supabase calls table.")
            else:
                print(f"[Post-Call] Supabase not available, mock saving call: {call_payload}")
        except Exception as e:
            print(f"[Post-Call] Error saving call log: {e}")
