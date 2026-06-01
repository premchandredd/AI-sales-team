"""
FastAPI Server — Backend for Your Voice Agent platform.
Provides REST endpoints for agent management and WebSocket endpoint for voice streams.
"""

import os
import json
import asyncio
import sys
import io
import datetime
from typing import Optional

from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Form, Depends, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from prompt_builder import build_system_prompt, build_first_message, WIZARD_STEPS
import agents_store
from agent_engine import VoiceSession
import google_service
import db

# Fix Windows console encoding for emoji/unicode
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


app = FastAPI(title="Your Voice Agent API")

@app.on_event("startup")
async def startup_event():
    if sys.platform == "win32":
        try:
            import ctypes
            winmm = ctypes.WinDLL('winmm')
            winmm.timeBeginPeriod(1)
            print("[Startup] Windows system timer resolution set to 1ms.")
        except Exception as e:
            print(f"[Startup] Failed to set Windows timer resolution: {e}")
            
    try:
        from dialer_worker import CampaignDialer
        CampaignDialer.get_instance().start()
        print("[Startup] Campaign Auto-Dialer worker loop started.")
    except Exception as e:
        print(f"[Startup] Error starting dialer: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    if sys.platform == "win32":
        try:
            import ctypes
            winmm = ctypes.WinDLL('winmm')
            winmm.timeEndPeriod(1)
            print("[Shutdown] Windows system timer resolution restored.")
        except Exception:
            pass
            
    try:
        from dialer_worker import CampaignDialer
        CampaignDialer.get_instance().stop()
        print("[Shutdown] Campaign Auto-Dialer worker loop stopped.")
    except Exception as e:
        print(f"[Shutdown] Error stopping dialer: {e}")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth Dependency ───
async def get_auth_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> str:
    """Dependency that extracts user_id from Supabase JWT, falling back to mock user."""
    t = token
    if not t and authorization:
        if authorization.startswith("Bearer "):
            t = authorization.split(" ", 1)[1]
        else:
            t = authorization
            
    user_id = db.get_user_id_from_token(t)
    google_service.current_user_id.set(user_id)
    return user_id



# ─── REST Models ───

class AgentCreateRequest(BaseModel):
    name: str
    type: str
    language: str
    tasks: list[str]
    tone: str
    business_name: Optional[str] = ""
    business_description: Optional[str] = ""
    custom_instructions: Optional[str] = ""
    voice_gender: Optional[str] = "female"
    google_meet_enabled: Optional[bool] = False
    email_notifications_enabled: Optional[bool] = False
    email_integration_enabled: Optional[bool] = False
    email_integration_instructions: Optional[str] = ""
    live_transfer_enabled: Optional[bool] = False
    live_transfer_number: Optional[str] = ""

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    model: Optional[str] = None
    voice: Optional[str] = None
    voice_gender: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    google_calendar_enabled: Optional[bool] = None
    google_calendar_id: Optional[str] = None
    google_meet_enabled: Optional[bool] = None
    email_notifications_enabled: Optional[bool] = None
    email_integration_enabled: Optional[bool] = None
    email_integration_instructions: Optional[str] = None
    google_sheets_enabled: Optional[bool] = None
    google_sheets_id: Optional[str] = None
    google_sheets_name: Optional[str] = None
    google_integration_instructions: Optional[str] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_waba_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_template_name: Optional[str] = None
    whatsapp_template_language: Optional[str] = None
    whatsapp_integration_instructions: Optional[str] = None
    live_transfer_enabled: Optional[bool] = None
    live_transfer_number: Optional[str] = None

class ProposeColumnsRequest(BaseModel):
    system_prompt: str = ""
    integration_instructions: str = ""
    agent_type: str = "inbound"

class CreateCustomSheetRequest(BaseModel):
    columns: list[str]

class UpdateColumnsRequest(BaseModel):
    columns: list[str]



# ─── REST Endpoints ───

@app.get("/api/wizard/steps")
async def get_wizard_steps():
    """Returns the question flow for the Agent Builder UI."""
    return {"steps": WIZARD_STEPS}


@app.post("/api/agents")
async def create_agent(req: AgentCreateRequest, user_id: str = Depends(get_auth_user)):
    """Generate prompt from wizard answers and create new agent."""
    config_dict = req.model_dump()
    system_prompt = build_system_prompt(config_dict)
    first_message = build_first_message(config_dict)

    # Translate first_message if language is not English
    raw_language = config_dict.get("language", "English")
    language = raw_language.split("|")[0] if "|" in raw_language else raw_language
    
    if "English" not in language and groq_client:
        try:
            translation_prompt = (
                f"You are a professional translator. Translate this greeting into conversational {language}. "
                f"Use natural {language} as spoken locally, and it's OK to mix in common English words naturally. "
                f"CRITICAL: Output mostly in the native {language} script (e.g., Telugu script for Telugu). "
                f"HOWEVER, you MUST keep English acronyms, business names, and common abbreviations (e.g. KPN, VSL, BHK) in English/Latin letters! "
                f"Do not add any quotes, explanations, or transliterations. Just output the final translated greeting."
            )
            response = await groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": translation_prompt},
                    {"role": "user", "content": first_message}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=500,
            )
            translated = response.choices[0].message.content.strip()
            if translated:
                first_message = translated
        except Exception as e:
            print(f"Translation failed: {e}")

    agent_data = {
        **config_dict,
        "system_prompt": system_prompt,
        "first_message": first_message,
        "model": "llama-3.3-70b-versatile",
        "voice": "aura-asteria-en",
    }

    agent = agents_store.create_agent(agent_data, user_id=user_id)
    return {"agent": agent}


@app.get("/api/agents")
async def list_agents(user_id: str = Depends(get_auth_user)):
    """List all created agents."""
    agents = agents_store.list_agents(user_id=user_id)
    agents.sort(key=lambda x: x["created_at"], reverse=True)
    return {"agents": agents}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, user_id: str = Depends(get_auth_user)):
    agent = agents_store.get_agent(agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"agent": agent}


@app.patch("/api/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest, user_id: str = Depends(get_auth_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    agent = agents_store.update_agent(agent_id, updates, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"agent": agent}


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str, user_id: str = Depends(get_auth_user)):
    success = agents_store.delete_agent(agent_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True}


# ─── Google OAuth & Data Endpoints ───

class GoogleSyncRequest(BaseModel):
    provider_token: str
    provider_refresh_token: Optional[str] = None
    expires_in: Optional[int] = None

@app.post("/api/google/sync-provider-tokens")
async def sync_google_provider_tokens(req: GoogleSyncRequest, user_id: str = Depends(get_auth_user)):
    try:
        from google.oauth2.credentials import Credentials
        import datetime
        
        # Calculate expiry datetime
        expiry = None
        if req.expires_in:
            expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=req.expires_in)
            
        # Try to preserve existing refresh token if missing in the sync request
        r_token = req.provider_refresh_token
        if not r_token:
            existing = google_service.get_credentials(user_id)
            if existing and existing.refresh_token:
                r_token = existing.refresh_token
                
        creds = Credentials(
            token=req.provider_token,
            refresh_token=r_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=google_service.CLIENT_CONFIG["web"]["client_id"],
            client_secret=google_service.CLIENT_CONFIG["web"]["client_secret"],
            scopes=google_service.SCOPES,
            expiry=expiry
        )
        
        google_service.save_credentials(creds, user_id)
        return {"success": True, "message": "Google provider tokens synced successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GoogleAuthRequest(BaseModel):
    code: str

@app.get("/api/google/auth-url")
async def get_google_auth_url(user_id: str = Depends(get_auth_user)):
    try:
        auth_url = google_service.get_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/google/authenticate")
async def authenticate_google(req: GoogleAuthRequest, user_id: str = Depends(get_auth_user)):
    try:
        user_info = google_service.exchange_code_for_tokens(req.code, user_id)
        return user_info
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        try:
            with open("error_debug.txt", "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/google/status")
async def get_google_status(user_id: str = Depends(get_auth_user)):
    try:
        user_info = google_service.get_user_info(user_id=user_id)
        return user_info
    except Exception as e:
        return {"authenticated": False, "error": str(e)}

@app.post("/api/google/logout")
async def logout_google(user_id: str = Depends(get_auth_user)):
    try:
        google_service.delete_credentials(user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google/sheets")
async def list_google_sheets(user_id: str = Depends(get_auth_user)):
    try:
        spreadsheets = google_service.list_spreadsheets()
        return {"spreadsheets": spreadsheets}
    except Exception as e:
        import traceback
        print(f"[Google Sheets ERROR] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google/sheets/{spreadsheet_id}/sheets")
async def list_google_sheet_tabs(spreadsheet_id: str, user_id: str = Depends(get_auth_user)):
    try:
        tabs = google_service.list_sheets(spreadsheet_id)
        return {"sheets": tabs}
    except Exception as e:
        import traceback
        print(f"[Google Sheet Tabs ERROR] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google/sheets/{spreadsheet_id}/{sheet_name}/data")
async def get_google_sheet_data(spreadsheet_id: str, sheet_name: str, user_id: str = Depends(get_auth_user)):
    try:
        data = google_service.get_sheet_data(spreadsheet_id, sheet_name)
        return {"data": data}
    except Exception as e:
        import traceback
        print(f"[Google Sheet Data ERROR] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/google/sheets/create-template")
async def create_google_sheets_template(user_id: str = Depends(get_auth_user)):
    try:
        sheet_info = google_service.create_template_leads_sheet()
        return sheet_info
    except Exception as e:
        import traceback
        print(f"[Google Create Template ERROR] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/google/sheets/propose-columns")
async def propose_columns(req: ProposeColumnsRequest, user_id: str = Depends(get_auth_user)):
    """Use LLM to propose ideal CRM spreadsheet columns based on agent configuration."""
    fallback = ["Name", "Phone", "Status", "Notes"]
    if not groq_client:
        return {"columns": fallback}
    try:
        prompt = (
            "You are a CRM spreadsheet designer. Based on the following voice agent configuration, "
            "propose the ideal column headers for a Google Sheets CRM spreadsheet that this agent would use to log call data.\n\n"
            f"Agent Type: {req.agent_type}\n"
            f"System Prompt: {req.system_prompt[:2000]}\n"
            f"Integration Instructions: {req.integration_instructions[:1000]}\n\n"
            "Rules:\n"
            "- Always include a \"Name\" column and a \"Phone\" column as the first two.\n"
            "- Always include \"Status\" and \"Notes\" columns (typically near the end).\n"
            "- Add additional relevant columns based on the agent's tasks and instructions (e.g., Budget, Location, Property Type, etc.).\n"
            "- Return ONLY a JSON array of column name strings. Example: [\"Name\", \"Phone\", \"Budget\", \"Location\", \"Status\", \"Notes\"]\n"
            "- Maximum 10 columns.\n"
            "- Do not include explanations — ONLY the JSON array."
        )
        response = await groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        # Parse JSON array from response
        import re as _re
        match = _re.search(r'\[.*\]', raw, _re.DOTALL)
        if match:
            columns = json.loads(match.group())
            if isinstance(columns, list) and all(isinstance(c, str) for c in columns):
                return {"columns": columns[:10]}
        return {"columns": fallback}
    except Exception as e:
        print(f"[Propose Columns ERROR] {e}")
        return {"columns": fallback}

@app.post("/api/google/sheets/create-custom")
async def create_custom_google_sheet(req: CreateCustomSheetRequest, user_id: str = Depends(get_auth_user)):
    """Create a new Google Sheet with user-specified column headers."""
    try:
        sheet_info = google_service.create_custom_leads_sheet(req.columns)
        return sheet_info
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Google Create Custom Sheet ERROR] {tb}")
        try:
            with open("error_debug.txt", "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google/sheets/{spreadsheet_id}/{sheet_name}/columns")
async def get_sheet_columns(spreadsheet_id: str, sheet_name: str, user_id: str = Depends(get_auth_user)):
    """Get the current column headers of a sheet."""
    try:
        columns = google_service.get_sheet_headers(spreadsheet_id, sheet_name)
        return {"columns": columns}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Google Get Sheet Columns ERROR] {tb}")
        try:
            with open("error_debug.txt", "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/google/sheets/{spreadsheet_id}/{sheet_name}/columns")
async def update_sheet_columns(spreadsheet_id: str, sheet_name: str, req: UpdateColumnsRequest, user_id: str = Depends(get_auth_user)):
    """Overwrite the headers row (first row) of a sheet."""
    try:
        google_service.update_sheet_headers(spreadsheet_id, sheet_name, req.columns)
        return {"success": True}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Google Update Sheet Columns ERROR] {tb}")
        try:
            with open("error_debug.txt", "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google/calendars")
async def list_google_calendars(user_id: str = Depends(get_auth_user)):
    try:
        calendars = google_service.list_calendars()
        return {"calendars": calendars}
    except Exception as e:
        import traceback
        print(f"[Google Calendars ERROR] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── WebSocket Endpoint (Real-time Voice) ───

@app.websocket("/api/agents/{agent_id}/voice")
async def voice_stream(
    websocket: WebSocket,
    agent_id: str,
    token: Optional[str] = None,
    spreadsheet_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    lead_row: Optional[int] = None,
    lead_id: Optional[str] = None
):
    """
    Real-time voice streaming endpoint.

    Browser sends: raw PCM16 audio bytes (16kHz, mono, int16)
    Server sends:  TTS audio bytes (MP3) + JSON transcript messages
    """
    await websocket.accept()
    # Resolve token to user_id and set context scoping
    user_id = db.get_user_id_from_token(token)
    google_service.current_user_id.set(user_id)

    print(f"[VOICE] WebSocket connected for agent {agent_id} (user_id={user_id}, leadsheet={spreadsheet_id}, row={lead_row}, lead_id={lead_id})")

    agent_config = agents_store.get_agent(agent_id, user_id=user_id)

    if not agent_config:
        print(f"[VOICE] Agent {agent_id} not found, closing")
        await websocket.close(code=1008, reason="Agent not found")
        return

    session = VoiceSession(agent_config)
    await session.prepare_session(spreadsheet_id, sheet_name, lead_row, lead_id=lead_id)

    stop_event = asyncio.Event()
    barge_in_event = asyncio.Event()  # set when user interrupts agent
    greeting_done_event = asyncio.Event()  # set when frontend finishes playing greeting

    try:
        # 1. Generate and send greeting audio FIRST (Do not connect STT yet to avoid timeout)
        greeting_audio = await session.generate_greeting_audio()
        if greeting_audio:
            # Send text FIRST so UI shows it before voice plays
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": session.first_message,
                "is_final": True,
            })
            await websocket.send_bytes(greeting_audio)
            await websocket.send_json({"type": "audio_flush"})
            print(f"[VOICE] Greeting sent: {session.first_message}")
        else:
            # No greeting audio — connect STT and mark as done immediately
            print("[VOICE] WARNING: Failed to generate greeting audio, connecting STT immediately")
            stt_ws = await session.connect_stt()
            if not stt_ws:
                await websocket.close(code=1011, reason="Failed to connect to STT")
                return
            greeting_done_event.set()

        # 3. Start concurrent tasks

        async def receive_browser_audio():
            """Receive raw PCM16 audio from browser and forward to Deepgram."""
            try:
                while not stop_event.is_set():
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive(), timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue

                    if "bytes" in data:
                        # Only forward mic audio to STT after greeting is done
                        if greeting_done_event.is_set():
                            await session.process_audio_chunk(data["bytes"])

                    elif "text" in data:
                        msg = json.loads(data["text"])
                        if msg.get("type") == "stop":
                            print("[VOICE] Stop signal from client")
                            stop_event.set()
                            return
                        elif msg.get("type") == "barge_in":
                            print("[VOICE] Barge-in: user interrupted agent")
                            barge_in_event.set()
                        elif msg.get("type") == "greeting_done":
                            print("[VOICE] Greeting finished playing — connecting STT now")
                            # Connect to Deepgram STT only now, so it doesn't time out during greeting
                            stt_ws = await session.connect_stt()
                            if not stt_ws:
                                print("[VOICE] Failed to connect to Deepgram STT")
                                stop_event.set()
                                return
                            print("[VOICE] Deepgram STT connected OK, mic now active")
                            greeting_done_event.set()

            except WebSocketDisconnect:
                print("[VOICE] Browser disconnected")
                stop_event.set()
            except Exception as e:
                print(f"[VOICE] Browser receive error: {e}")
                stop_event.set()

        async def process_transcripts():
            """Receive transcripts from Deepgram, generate LLM + TTS responses."""
            try:
                # Wait until greeting finishes and STT is successfully connected
                await greeting_done_event.wait()
                if stop_event.is_set():
                    return

                async for stt_msg in session.receive_transcripts():
                    if stop_event.is_set():
                        return

                    if stt_msg["type"] == "interim":
                        await websocket.send_json({
                            "type": "transcript",
                            "role": "user",
                            "text": stt_msg["text"],
                            "is_final": False,
                        })

                    elif stt_msg["type"] == "utterance_end":
                        user_text = stt_msg["text"].strip()
                        if not user_text:
                            continue

                        print(f"[VOICE] User said: {user_text}")

                        await websocket.send_json({
                            "type": "transcript",
                            "role": "user",
                            "text": user_text,
                            "is_final": True,
                        })

                        # Clear any previous barge-in before generating new response
                        barge_in_event.clear()

                        # --- TRUE PIPELINING (Concurrent TTS) ---
                        # We use an asyncio.Queue to overlap LLM generation and TTS synthesis.
                        audio_queue = asyncio.Queue()

                        async def tts_producer():
                            full_ai_text = ""
                            try:
                                async for text_chunk in session.generate_response(user_text):
                                    if stop_event.is_set() or barge_in_event.is_set():
                                        print("[VOICE] Barge-in: stopping LLM generation")
                                        break

                                    full_ai_text += text_chunk + " "
                                    
                                    # Stream the text to UI immediately!
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "role": "assistant",
                                        "text": full_ai_text.strip(),
                                        "is_final": False,
                                    })

                                    # Push the streaming TTS generator directly to the queue
                                    gen = session.stream_synthesize_speech(text_chunk)
                                    await audio_queue.put(gen)

                                # Mark text as final
                                if full_ai_text.strip():
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "role": "assistant",
                                        "text": full_ai_text.strip(),
                                        "is_final": True,
                                    })
                                    print(f"[VOICE] AI text sent: {full_ai_text.strip()}")
                            finally:
                                await audio_queue.put(None)  # EOF marker

                        async def audio_consumer():
                            while True:
                                gen = await audio_queue.get()
                                if gen is None:
                                    break
                                if stop_event.is_set() or barge_in_event.is_set():
                                    print("[VOICE] Barge-in: stopping TTS playback")
                                    break
                                
                                try:
                                    async for audio_bytes in gen:
                                        if stop_event.is_set() or barge_in_event.is_set():
                                            break
                                        if audio_bytes:
                                            await websocket.send_bytes(audio_bytes)
                                except Exception as e:
                                    print(f"[VOICE] TTS streaming error: {e}")

                        # Run producer and consumer concurrently
                        await asyncio.gather(
                            tts_producer(),
                            audio_consumer()
                        )

                        await websocket.send_json({"type": "audio_flush"})

                        if getattr(session, "call_transferred", False):
                            await websocket.send_json({
                                "type": "call_transfer",
                                "to_phone": session.transfer_destination,
                            })
                            print(f"[VOICE] Sent transfer signal to browser. Closing session.")
                            stop_event.set()
                            return

            except WebSocketDisconnect:
                stop_event.set()
            except Exception as e:
                print(f"[VOICE] Transcript processing error: {e}")
                import traceback
                traceback.print_exc()
                stop_event.set()

        browser_task = asyncio.create_task(receive_browser_audio())
        transcript_task = asyncio.create_task(process_transcripts())

        done, pending = await asyncio.wait(
            [browser_task, transcript_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except Exception as e:
        print(f"[VOICE] Session error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        duration = session.get_duration_minutes()
        agents_store.increment_call(agent_id, duration)
        await session.close()
        print(f"[VOICE] Session ended ({duration:.1f} min)")

        # Run post-call processing in the background to save details to Google Sheets/Calendar asynchronously
        asyncio.create_task(session.process_post_call())

        try:
            await websocket.close()
        except Exception:
            pass


# ─── Twilio Telephony REST Models ───

class TwilioSettingsUpdateRequest(BaseModel):
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

class OutboundCallRequest(BaseModel):
    agent_id: str
    to_phone: str
    from_phone: Optional[str] = ""
    spreadsheet_id: Optional[str] = ""
    sheet_name: Optional[str] = ""
    lead_row: Optional[int] = None


# ─── Twilio Telephony REST Endpoints ───

@app.get("/api/settings/twilio")
async def get_twilio_settings(user_id: str = Depends(get_auth_user)):
    """Retrieve Twilio settings for the authenticated user."""
    if db.supabase:
        try:
            res = db.supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
            if res.data:
                settings = res.data[0]
                # Obfuscate token for security
                token = settings.get("twilio_auth_token", "")
                obfuscated_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "..."
                return {
                    "twilio_account_sid": settings.get("twilio_account_sid", ""),
                    "twilio_auth_token": obfuscated_token,
                    "twilio_phone_number": settings.get("twilio_phone_number", ""),
                    "configured": True
                }
        except Exception as e:
            print(f"[Twilio Settings] Error loading settings: {e}")
    
    # Fallback/default from env
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    obfuscated_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "..."
    return {
        "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
        "twilio_auth_token": obfuscated_token,
        "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
        "configured": bool(os.getenv("TWILIO_ACCOUNT_SID"))
    }

@app.post("/api/settings/twilio")
async def update_twilio_settings(req: TwilioSettingsUpdateRequest, user_id: str = Depends(get_auth_user)):
    """Save or update Twilio settings for the authenticated user."""
    # Resolve the actual auth token (handle obfuscation)
    auth_token = req.twilio_auth_token
    if "..." in auth_token:
        existing_token = None
        if db.supabase and user_id != db.MOCK_USER_ID:
            try:
                res = db.supabase.table("user_settings").select("twilio_auth_token").eq("user_id", user_id).execute()
                if res.data:
                    existing_token = res.data[0].get("twilio_auth_token")
            except Exception as e:
                print(f"[Twilio Settings] Error reading existing token: {e}")
        if not existing_token:
            existing_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        auth_token = existing_token

    if db.supabase and user_id != db.MOCK_USER_ID:
        try:
            payload = {
                "user_id": user_id,
                "twilio_account_sid": req.twilio_account_sid,
                "twilio_auth_token": auth_token,
                "twilio_phone_number": req.twilio_phone_number,
                "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
            db.supabase.table("user_settings").upsert(payload).execute()
            return {"success": True, "message": "Twilio settings saved successfully."}
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")
            
    # Local fallback writes to environment variable (memory only)
    os.environ["TWILIO_ACCOUNT_SID"] = req.twilio_account_sid
    os.environ["TWILIO_AUTH_TOKEN"] = auth_token
    os.environ["TWILIO_PHONE_NUMBER"] = req.twilio_phone_number
    return {"success": True, "message": "Twilio settings saved locally."}


@app.post("/api/telephony/call")
async def place_telephony_call(req: OutboundCallRequest, user_id: str = Depends(get_auth_user)):
    """Trigger an outbound call using Twilio REST API."""
    # 1. Retrieve Twilio credentials
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = req.from_phone or os.getenv("TWILIO_PHONE_NUMBER")

    if db.supabase and user_id != db.MOCK_USER_ID:
        try:
            res = db.supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
            if res.data:
                settings = res.data[0]
                account_sid = settings.get("twilio_account_sid") or account_sid
                auth_token = settings.get("twilio_auth_token") or auth_token
                from_phone = settings.get("twilio_phone_number") or from_phone
        except Exception as e:
            print(f"[Telephony] Error fetching User Twilio settings: {e}")

    if not account_sid or not auth_token or not from_phone:
        raise HTTPException(
            status_code=400,
            detail="Twilio Account SID, Auth Token, and Outbound Phone Number must be configured first."
        )

    # 2. Build TwiML redirect URL pointing back to our server
    # We read BASE_URL from env; if not configured, we attempt to resolve from the request headers
    base_url = os.getenv("BASE_URL")
    if not base_url:
        # Fallback to local
        base_url = "http://localhost:8000"

    from urllib.parse import urlencode
    params = {
        "agent_id": req.agent_id,
    }
    if req.spreadsheet_id:
        params["spreadsheet_id"] = req.spreadsheet_id
    if req.sheet_name:
        params["sheet_name"] = req.sheet_name
    if req.lead_row is not None:
        params["lead_row"] = str(req.lead_row)

    twiml_url = f"{base_url}/api/telephony/outbound-twiml?{urlencode(params)}"
    print(f"[Telephony] Placing Twilio outbound call. To: {req.to_phone}, From: {from_phone}, URL: {twiml_url}")

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            to=req.to_phone,
            from_=from_phone,
            url=twiml_url
        )
        return {"success": True, "call_sid": call.sid, "status": call.status}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to place call via Twilio: {str(e)}")


@app.post("/api/telephony/outbound-twiml")
async def outbound_twiml(
    agent_id: str,
    spreadsheet_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    lead_row: Optional[int] = None
):
    """Returns TwiML telling Twilio to connect the call's audio stream to our WebSocket endpoint."""
    base_url = os.getenv("BASE_URL") or "localhost:8000"
    
    # Strip protocols to get raw host
    ws_host = base_url.replace("http://", "").replace("https://", "")
    ws_scheme = "wss" if "https" in base_url else "ws"
    ws_stream_url = f"{ws_scheme}://{ws_host}/api/telephony/stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_stream_url}">
            <Parameter name="agent_id" value="{agent_id}" />
            <Parameter name="spreadsheet_id" value="{spreadsheet_id or ''}" />
            <Parameter name="sheet_name" value="{sheet_name or ''}" />
            <Parameter name="lead_row" value="{str(lead_row) if lead_row is not None else ''}" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/api/telephony/inbound")
async def inbound_call(
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...)
):
    """Webhook for handling incoming Twilio calls. Routes to the first active inbound agent."""
    agent_id = None
    
    # 1. Look up an inbound agent
    if db.supabase:
        try:
            res = db.supabase.table("agents").select("id").eq("type", "inbound").limit(1).execute()
            if res.data:
                agent_id = res.data[0]["id"]
        except Exception as e:
            print(f"[Telephony] Inbound lookup in Supabase failed: {e}")
            
    if not agent_id:
        # Check local store fallback
        try:
            agents = agents_store.list_agents(db.MOCK_USER_ID)
            inbound_agents = [a for a in agents if a.get("type") == "inbound"]
            if inbound_agents:
                agent_id = inbound_agents[0]["id"]
        except Exception:
            pass

    if not agent_id:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, no active voice agent is configured for this number.</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Connect the call to our WebSocket stream
    base_url = os.getenv("BASE_URL") or "localhost:8000"
    ws_host = base_url.replace("http://", "").replace("https://", "")
    ws_scheme = "wss" if "https" in base_url else "ws"
    ws_stream_url = f"{ws_scheme}://{ws_host}/api/telephony/stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_stream_url}">
            <Parameter name="agent_id" value="{agent_id}" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# ─── WebSocket Endpoint for Twilio Media Streaming ───

async def twilio_transcript_loop(
    websocket: WebSocket,
    session: VoiceSession,
    stream_sid: str,
    stop_event: asyncio.Event,
    barge_in_event: asyncio.Event
):
    """Concurrently processes Deepgram transcripts and forwards TTS audio to Twilio."""
    try:
        async for stt_msg in session.receive_transcripts():
            if stop_event.is_set():
                break

            if stt_msg["type"] == "interim":
                # Deepgram Interim results: check for barge-in if we are speaking
                # (Note: session doesn't keep track of playback, but if the transcript loop
                # gets user speech, it will trigger the barge_in event)
                pass
            elif stt_msg["type"] == "utterance_end":
                user_text = stt_msg["text"].strip()
                if not user_text:
                    continue

                print(f"[TELEPHONY] User said: {user_text}")
                
                # Clear any existing barge-in
                barge_in_event.clear()
                
                audio_queue = asyncio.Queue()

                async def tts_producer():
                    try:
                        async for text_chunk in session.generate_response(user_text):
                            if stop_event.is_set() or barge_in_event.is_set():
                                break

                            # Stream TTS speech in mulaw 8000Hz directly from Sarvam or Deepgram fallback
                            gen = session.stream_synthesize_speech(text_chunk)
                            await audio_queue.put(gen)
                    finally:
                        await audio_queue.put(None)

                async def audio_consumer():
                    while True:
                        gen = await audio_queue.get()
                        if gen is None:
                            break
                        if stop_event.is_set() or barge_in_event.is_set():
                            break

                        try:
                            async for audio_bytes in gen:
                                if stop_event.is_set() or barge_in_event.is_set():
                                    break
                                if audio_bytes:
                                    # Encode to base64 payload
                                    payload = base64.b64encode(audio_bytes).decode("utf-8")
                                    await websocket.send_json({
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {
                                            "payload": payload
                                        }
                                    })
                        except Exception as e:
                            print(f"[TELEPHONY] Error in TTS playback consumer: {e}")

                await asyncio.gather(
                    tts_producer(),
                    audio_consumer()
                )

    except Exception as e:
        print(f"[TELEPHONY] Error in transcript loop: {e}")


@app.websocket("/api/telephony/stream")
async def telephony_stream(websocket: WebSocket):
    """
    Handles real-time Twilio Media Stream over WebSocket.
    Streams 8kHz mu-law audio to/from Twilio directly.
    """
    await websocket.accept()
    print("[TELEPHONY] WebSocket connection opened from Twilio")

    stream_sid = None
    call_sid = None
    agent_id = None
    spreadsheet_id = None
    sheet_name = None
    lead_row = None
    campaign_id = None
    lead_id = None

    session = None
    stop_event = asyncio.Event()
    barge_in_event = asyncio.Event()

    try:
        async for message in websocket.iter_json():
            event = message.get("event")
            if event == "connected":
                print("[TELEPHONY] Handshake established with Twilio")
            elif event == "start":
                start_data = message.get("start", {})
                stream_sid = start_data.get("streamSid")
                call_sid = start_data.get("callSid")
                custom_params = start_data.get("customParameters", {})

                agent_id = custom_params.get("agent_id")
                spreadsheet_id = custom_params.get("spreadsheet_id")
                sheet_name = custom_params.get("sheet_name")
                campaign_id = custom_params.get("campaign_id")
                lead_id = custom_params.get("lead_id")
                
                lead_row_raw = custom_params.get("lead_row")
                lead_row = int(lead_row_raw) if lead_row_raw and lead_row_raw.isdigit() else None

                print(f"[TELEPHONY] Stream details: CallSid={call_sid}, AgentId={agent_id}, Spreadsheet={spreadsheet_id}, Row={lead_row}, CampaignId={campaign_id}, LeadId={lead_id}")

                if not agent_id:
                    print("[TELEPHONY] No agent ID provided in stream parameters, closing connection.")
                    break

                # Get agent configuration (telephony works globally by ID)
                agent_config = agents_store.get_agent(agent_id)
                if not agent_config:
                    print(f"[TELEPHONY] Agent {agent_id} not found in database, closing.")
                    break

                # Create and prepare session in Twilio mode!
                session = VoiceSession(agent_config, is_twilio=True)
                session.call_sid = call_sid
                await session.prepare_session(spreadsheet_id, sheet_name, lead_row, lead_id=lead_id)

                # Connect to Deepgram STT (with PCMU 8000Hz codec configuration)
                stt_ws = await session.connect_stt()
                if not stt_ws:
                    print("[TELEPHONY] Failed to connect to Deepgram STT, closing.")
                    break

                # Generate greeting and send directly as 8kHz mulaw
                greeting_audio = await session.generate_greeting_audio()
                if greeting_audio:
                    payload = base64.b64encode(greeting_audio).decode("utf-8")
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": payload
                        }
                    })
                    print("[TELEPHONY] Greeting audio streamed successfully")

                # Concurrently listen to transcripts and feed audio
                asyncio.create_task(twilio_transcript_loop(websocket, session, stream_sid, stop_event, barge_in_event))

            elif event == "media":
                media_data = message.get("media", {})
                payload_b64 = media_data.get("payload")
                if payload_b64 and session:
                    # Forward base64-encoded raw mulaw bytes to Deepgram STT
                    audio_bytes = base64.b64decode(payload_b64)
                    await session.process_audio_chunk(audio_bytes)

            elif event == "stop":
                print(f"[TELEPHONY] Received stop signal for StreamSid: {stream_sid}")
                break

    except WebSocketDisconnect:
        print("[TELEPHONY] Twilio closed WebSocket connection")
    except Exception as e:
        print(f"[TELEPHONY] Stream handler error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        stop_event.set()
        if session:
            duration = session.get_duration_minutes()
            agents_store.increment_call(agent_id, duration)
            await session.close()
            
            # Post-call updates (Sheets, Calendar, Whatsapp templates) asynchronously
            asyncio.create_task(session.process_post_call())
            
            # Dialer campaign lead status update
            if lead_id and db.supabase:
                try:
                    # Update status to completed
                    status_note = f"Call completed. Duration: {duration:.1f} mins."
                    await asyncio.to_thread(
                        lambda: db.supabase.table("campaign_leads")
                        .update({"status": "completed", "notes": status_note})
                        .eq("id", lead_id)
                        .execute()
                    )
                    print(f"[TELEPHONY] Updated campaign lead {lead_id} status to completed.")
                except Exception as ex:
                    print(f"[TELEPHONY] Error updating campaign lead status: {ex}")
                    
            print(f"[TELEPHONY] Telephony session ended ({duration:.1f} min)")

        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/api/telephony/transfer-twiml")
async def transfer_twiml(to_phone: str = Query(...)):
    """TwiML response to transfer a call to a human agent."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please hold while I transfer your call to a representative.</Say>
    <Dial>{to_phone}</Dial>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.get("/api/calls")
async def get_calls(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(20),
    offset: int = Query(0),
    user_id: str = Depends(get_auth_user)
):
    """Retrieve call logs for the authenticated user, optionally filtered by agent_id."""
    if not db.supabase:
        return {"calls": [], "count": 0}
        
    try:
        query = db.supabase.table("calls").select("*", count="exact").eq("user_id", user_id)
        if agent_id:
            query = query.eq("agent_id", agent_id)
            
        res = await asyncio.to_thread(
            lambda: query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        )
        return {
            "calls": res.data or [],
            "count": res.count or 0
        }
    except Exception as e:
        print(f"[API Calls] Error fetching calls: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch calls: {str(e)}")


@app.get("/api/analytics")
async def get_analytics(
    agent_id: Optional[str] = Query(None),
    user_id: str = Depends(get_auth_user)
):
    """Aggregate call analytics for the authenticated user's dashboard."""
    if not db.supabase:
        return {
            "total_calls": 0,
            "total_duration": 0,
            "sentiment_counts": {"Positive": 0, "Neutral": 0, "Negative": 0},
            "outcome_counts": {},
            "daily_volume": []
        }
        
    try:
        query = db.supabase.table("calls").select("duration, sentiment, outcome, created_at").eq("user_id", user_id)
        if agent_id:
            query = query.eq("agent_id", agent_id)
            
        res = await asyncio.to_thread(query.execute)
        calls = res.data or []
        
        total_calls = len(calls)
        total_duration = sum(float(c.get("duration", 0.0) or 0.0) for c in calls)
        
        sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
        outcome_counts = {}
        daily_volume_map = {}
        
        for c in calls:
            sent = c.get("sentiment", "Neutral")
            if sent not in sentiment_counts:
                sentiment_counts[sent] = 0
            sentiment_counts[sent] += 1
            
            out = c.get("outcome") or "Unknown"
            outcome_counts[out] = outcome_counts.get(out, 0) + 1
            
            created_at = c.get("created_at")
            if created_at:
                try:
                    date_str = created_at.split("T")[0]
                    daily_volume_map[date_str] = daily_volume_map.get(date_str, 0) + 1
                except Exception:
                    pass
                    
        daily_volume = [
            {"date": date, "calls": count}
            for date, count in sorted(daily_volume_map.items())
        ]
        
        return {
            "total_calls": total_calls,
            "total_duration": round(total_duration, 2),
            "sentiment_counts": sentiment_counts,
            "outcome_counts": outcome_counts,
            "daily_volume": daily_volume
        }
    except Exception as e:
        print(f"[API Analytics] Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


# ─── WebRTC Signaling Route ───
class WebRTCOfferRequest(BaseModel):
    sdp: str
    type: str
    agent_id: str
    spreadsheet_id: Optional[str] = None
    sheet_name: Optional[str] = None
    lead_row: Optional[int] = None
    lead_id: Optional[str] = None

@app.post("/api/webrtc/offer")
async def webrtc_offer(req: WebRTCOfferRequest, user_id: str = Depends(get_auth_user)):
    """WebRTC SDP offer handler."""
    try:
        from webrtc_handler import WebRTCSessionManager
        answer = await WebRTCSessionManager.get_instance().handle_offer(
            sdp=req.sdp,
            sdp_type=req.type,
            agent_id=req.agent_id,
            user_id=user_id,
            spreadsheet_id=req.spreadsheet_id,
            sheet_name=req.sheet_name,
            lead_row=req.lead_row,
            lead_id=req.lead_id
        )
        return answer
    except Exception as e:
        print(f"[API WebRTC] Offer failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
# ─── Campaigns & Auto-Dialer Routes ───

class CampaignCreateRequest(BaseModel):
    name: str
    agent_id: str
    campaign_type: Optional[str] = "outbound"  # 'outbound' or 'inbound'
    spreadsheet_id: Optional[str] = None
    sheet_name: Optional[str] = None
    start_time: Optional[str] = "09:00"
    end_time: Optional[str] = "18:00"
    max_concurrent_calls: Optional[int] = 1
    retry_count: Optional[int] = 0
    retry_delay_minutes: Optional[int] = 15
    call_order: Optional[str] = "sequential"  # 'sequential' or 'random'
    after_hours_action: Optional[str] = "none"  # 'none', 'voicemail', 'message', 'transfer'
    after_hours_message: Optional[str] = ""
    after_hours_transfer_number: Optional[str] = ""

@app.post("/api/campaigns")
async def create_campaign(req: CampaignCreateRequest, user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        # Auto-resolve spreadsheet from agent config if not provided (outbound campaigns)
        sheet_id = req.spreadsheet_id
        sheet_name = req.sheet_name
        if req.campaign_type == "outbound" and (not sheet_id or not sheet_name):
            try:
                agent_res = await asyncio.to_thread(
                    lambda: db.supabase.table("agents").select("google_sheets_id, google_sheets_name").eq("id", req.agent_id).single().execute()
                )
                if agent_res.data:
                    sheet_id = sheet_id or agent_res.data.get("google_sheets_id") or None
                    sheet_name = sheet_name or agent_res.data.get("google_sheets_name") or None
            except Exception as e:
                print(f"[API Campaigns] Agent sheet lookup failed: {e}")

        c_res = await asyncio.to_thread(
            lambda: db.supabase.table("campaigns").insert({
                "user_id": user_id,
                "agent_id": req.agent_id,
                "name": req.name,
                "status": "paused",
                "campaign_type": req.campaign_type,
                "spreadsheet_id": sheet_id,
                "sheet_name": sheet_name,
                "start_time": req.start_time,
                "end_time": req.end_time,
                "max_concurrent_calls": req.max_concurrent_calls,
                "retry_count": req.retry_count,
                "retry_delay_minutes": req.retry_delay_minutes,
                "call_order": req.call_order,
                "after_hours_action": req.after_hours_action,
                "after_hours_message": req.after_hours_message,
                "after_hours_transfer_number": req.after_hours_transfer_number
            }).execute()
        )
        if not c_res.data:
            raise Exception("Failed to create campaign")
        camp = c_res.data[0]
        camp_id = camp["id"]

        lead_count = 0
        if req.campaign_type == "outbound" and sheet_id and sheet_name:
            rows = await asyncio.to_thread(
                google_service.get_sheet_data, sheet_id, sheet_name
            )
            lead_inserts = []
            for r in rows:
                phone = r.get("Phone") or r.get("phone")
                name = r.get("Name") or r.get("name") or "Lead"
                if phone:
                    lead_inserts.append({
                        "campaign_id": camp_id,
                        "name": name,
                        "phone": phone,
                        "status": "pending",
                        "lead_row": r.get("__row__"),
                        "custom_data": r,
                        "attempt_count": 0
                    })
            
            # Randomize if call_order is 'random'
            if req.call_order == "random" and lead_inserts:
                import random
                random.shuffle(lead_inserts)

            if lead_inserts:
                batch_size = 50
                for j in range(0, len(lead_inserts), batch_size):
                    batch = lead_inserts[j:j+batch_size]
                    await asyncio.to_thread(
                        lambda b=batch: db.supabase.table("campaign_leads").insert(b).execute()
                    )
                lead_count = len(lead_inserts)

        return {"success": True, "campaign": camp, "leads_imported": lead_count}
    except Exception as e:
        print(f"[API Campaigns] Create failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns")
async def list_campaigns(agent_id: Optional[str] = Query(None), user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        return {"campaigns": []}
    try:
        q = db.supabase.table("campaigns").select("*").eq("user_id", user_id)
        if agent_id:
            q = q.eq("agent_id", agent_id)
        res = await asyncio.to_thread(lambda: q.order("created_at", desc=True).execute())
        
        campaigns = res.data or []
        for c in campaigns:
            leads_res = await asyncio.to_thread(
                lambda: db.supabase.table("campaign_leads").select("id, status").eq("campaign_id", c["id"]).execute()
            )
            leads = leads_res.data or []
            c["total_leads"] = len(leads)
            c["pending_leads"] = len([l for l in leads if l["status"] == "pending"])
            c["completed_leads"] = len([l for l in leads if l["status"] == "completed"])
            c["failed_leads"] = len([l for l in leads if l["status"] == "failed"])
            
        return {"campaigns": campaigns}
    except Exception as e:
        print(f"[API Campaigns] List failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/campaigns/{id}/start")
async def start_campaign(id: str, user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        res = await asyncio.to_thread(
            lambda: db.supabase.table("campaigns").update({"status": "active"}).eq("id", id).eq("user_id", user_id).execute()
        )
        return {"success": len(res.data) > 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/campaigns/{id}/pause")
async def pause_campaign(id: str, user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        res = await asyncio.to_thread(
            lambda: db.supabase.table("campaigns").update({"status": "paused"}).eq("id", id).eq("user_id", user_id).execute()
        )
        return {"success": len(res.data) > 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns/{id}/leads")
async def list_campaign_leads(id: str, user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        return {"leads": []}
    try:
        res = await asyncio.to_thread(
            lambda: db.supabase.table("campaign_leads").select("*").eq("campaign_id", id).execute()
        )
        return {"leads": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── RAG Knowledge Base Routes ───

from fastapi import UploadFile, File

@app.post("/api/knowledge-base/upload")
async def upload_document(
    agent_id: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(get_auth_user)
):
    temp_dir = os.path.join(os.path.dirname(__file__), "..", "scratch")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
            
        from rag_service import ingest_document
        success, message = await ingest_document(
            agent_id=agent_id,
            user_id=user_id,
            file_path=temp_path,
            filename=file.filename
        )
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API RAG] Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/api/knowledge-base")
async def list_knowledge_bases(agent_id: str = Query(...), user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        return {"documents": []}
    try:
        res = await asyncio.to_thread(
            lambda: db.supabase.table("knowledge_bases")
            .select("*")
            .eq("agent_id", agent_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {"documents": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/knowledge-base/{id}")
async def delete_knowledge_base(id: str, user_id: str = Depends(get_auth_user)):
    if not db.supabase:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        res = await asyncio.to_thread(
            lambda: db.supabase.table("knowledge_bases").delete().eq("id", id).eq("user_id", user_id).execute()
        )
        return {"success": len(res.data) > 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Twilio Outbound Dialer Webhooks ───

@app.get("/api/telephony/campaign-twiml")
async def campaign_twiml(
    agent_id: str,
    campaign_id: str,
    lead_id: str,
    spreadsheet_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    lead_row: Optional[int] = None
):
    """TwiML generator for campaign calls. Connects answered calls to stream."""
    base_url = os.getenv("BASE_URL") or "http://localhost:8000"
    ws_host = base_url.replace("http://", "").replace("https://", "")
    ws_scheme = "wss" if base_url.startswith("https") else "ws"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_scheme}://{ws_host}/api/telephony/stream">
            <Parameter name="agent_id" value="{agent_id}" />
            <Parameter name="campaign_id" value="{campaign_id}" />
            <Parameter name="lead_id" value="{lead_id}" />
            <Parameter name="spreadsheet_id" value="{spreadsheet_id or ''}" />
            <Parameter name="sheet_name" value="{sheet_name or ''}" />
            <Parameter name="lead_row" value="{str(lead_row) if lead_row is not None else ''}" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")

@app.post("/api/telephony/campaign-callback")
async def campaign_callback(
    campaign_id: str,
    lead_id: str,
    CallStatus: str = Form(None)
):
    """Twilio callback hook to update lead status when campaign calls end or fail."""
    if db.supabase:
        if CallStatus in ["failed", "busy", "no-answer", "canceled"]:
            try:
                await asyncio.to_thread(
                    lambda: db.supabase.table("campaign_leads")
                    .update({"status": "failed", "notes": f"Twilio Dial Status: {CallStatus}"})
                    .eq("id", lead_id)
                    .execute()
                )
                print(f"[Callback] Lead {lead_id} marked as failed ({CallStatus}).")
            except Exception as e:
                print(f"[Callback] Error updating lead: {e}")
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
