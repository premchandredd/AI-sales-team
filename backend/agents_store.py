"""
Agent persistence layer — Refactored to support Supabase with local JSON fallback.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import db

STORE_PATH = Path(__file__).parent / "agents.json"


def _load() -> dict:
    if STORE_PATH.exists():
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"agents": {}}


def _save(data: dict):
    try:
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"[agents_store] Failed to save JSON store: {e}")


def _backfill_defaults(agent: dict) -> dict:
    agent.setdefault("google_calendar_enabled", False)
    agent.setdefault("google_calendar_id", "primary")
    agent.setdefault("google_meet_enabled", False)
    agent.setdefault("email_notifications_enabled", False)
    agent.setdefault("email_integration_enabled", False)
    agent.setdefault("email_integration_instructions", "")
    agent.setdefault("google_sheets_enabled", False)
    agent.setdefault("google_sheets_id", "")
    agent.setdefault("google_sheets_name", "")
    agent.setdefault("google_integration_instructions", "")
    agent.setdefault("whatsapp_enabled", False)
    agent.setdefault("whatsapp_phone_number_id", "")
    agent.setdefault("whatsapp_waba_id", "")
    agent.setdefault("whatsapp_access_token", "")
    agent.setdefault("whatsapp_template_name", "hello_world")
    agent.setdefault("whatsapp_template_language", "en_US")
    agent.setdefault("whatsapp_integration_instructions", "")
    agent.setdefault("live_transfer_enabled", False)
    agent.setdefault("live_transfer_number", "")
    agent.setdefault("calls_count", 0)
    agent.setdefault("total_minutes", 0.0)
    return agent


def create_agent(agent_data: dict, user_id: str) -> dict:
    """Create a new agent and persist it."""
    agent_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"

    # Extract TTS language code from "Label|code" format
    raw_language = agent_data.get("language", "English (Indian)|en-IN")
    if "|" in raw_language:
        tts_lang_code = raw_language.split("|", 1)[1]
    else:
        tts_lang_code = "en-IN"

    agent = {
        "id": agent_id,
        "name": agent_data.get("name", "Untitled Agent"),
        "type": agent_data.get("type", "inbound"),
        "language": agent_data.get("language", "English (Indian)|en-IN"),
        "tts_language_code": tts_lang_code,
        "tasks": agent_data.get("tasks", []),
        "tone": agent_data.get("tone", "Professional"),
        "system_prompt": agent_data.get("system_prompt", ""),
        "first_message": agent_data.get("first_message", "Hello! How can I help you today?"),
        "model": agent_data.get("model", "llama-3.3-70b-versatile"),
        "voice": agent_data.get("voice", "aura-asteria-en"),
        "voice_gender": agent_data.get("voice_gender", "female"),
        "max_tokens": agent_data.get("max_tokens", 500),
        "temperature": agent_data.get("temperature", 0.7),
        "google_calendar_enabled": agent_data.get("google_calendar_enabled", False),
        "google_calendar_id": agent_data.get("google_calendar_id", "primary"),
        "google_meet_enabled": agent_data.get("google_meet_enabled", False),
        "email_notifications_enabled": agent_data.get("email_notifications_enabled", False),
        "email_integration_enabled": agent_data.get("email_integration_enabled", False),
        "email_integration_instructions": agent_data.get("email_integration_instructions", ""),
        "google_sheets_enabled": agent_data.get("google_sheets_enabled", False),
        "google_sheets_id": agent_data.get("google_sheets_id", ""),
        "google_sheets_name": agent_data.get("google_sheets_name", ""),
        "google_integration_instructions": agent_data.get("google_integration_instructions", ""),
        "whatsapp_enabled": agent_data.get("whatsapp_enabled", False),
        "whatsapp_phone_number_id": agent_data.get("whatsapp_phone_number_id", ""),
        "whatsapp_waba_id": agent_data.get("whatsapp_waba_id", ""),
        "whatsapp_access_token": agent_data.get("whatsapp_access_token", ""),
        "whatsapp_template_name": agent_data.get("whatsapp_template_name", "hello_world"),
        "whatsapp_template_language": agent_data.get("whatsapp_template_language", "en_US"),
        "whatsapp_integration_instructions": agent_data.get("whatsapp_integration_instructions", ""),
        "live_transfer_enabled": agent_data.get("live_transfer_enabled", False),
        "live_transfer_number": agent_data.get("live_transfer_number", ""),
        "created_at": now,
        "updated_at": now,
        "calls_count": 0,
        "total_minutes": 0.0,
        "status": "active",
    }

    if db.supabase:
        try:
            db_agent = {**agent, "user_id": user_id}
            res = db.supabase.table("agents").insert(db_agent).execute()
            if res.data:
                return _backfill_defaults(res.data[0])
        except Exception as e:
            print(f"[agents_store] Supabase insert failed: {e}. Falling back to local store.")

    store = _load()
    agent["user_id"] = user_id
    store["agents"][agent_id] = agent
    _save(store)
    return agent


def get_agent(agent_id: str, user_id: Optional[str] = None) -> dict | None:
    """Get an agent by ID. Telephony features can retrieve without user_id restriction."""
    if db.supabase:
        try:
            query = db.supabase.table("agents").select("*").eq("id", agent_id)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            if res.data:
                return _backfill_defaults(res.data[0])
        except Exception as e:
            print(f"[agents_store] Supabase get failed: {e}. Falling back to local store.")

    store = _load()
    agent = store["agents"].get(agent_id)
    if agent:
        if user_id and agent.get("user_id") != user_id:
            return None
        return _backfill_defaults(agent)
    return None


def list_agents(user_id: str) -> list[dict]:
    """List all agents for the current user."""
    if db.supabase:
        try:
            res = db.supabase.table("agents").select("*").eq("user_id", user_id).execute()
            if res.data is not None:
                return [_backfill_defaults(a) for a in res.data]
        except Exception as e:
            print(f"[agents_store] Supabase list failed: {e}. Falling back to local store.")

    store = _load()
    agents = []
    for a in store["agents"].values():
        if a.get("user_id") == user_id:
            agents.append(_backfill_defaults(a))
    return agents


def update_agent(agent_id: str, updates: dict, user_id: str) -> dict | None:
    """Update agent configuration."""
    ALLOWED_NEW_FIELDS = {
        "google_calendar_enabled", "google_calendar_id",
        "google_meet_enabled", "email_notifications_enabled",
        "email_integration_enabled", "email_integration_instructions",
        "google_sheets_enabled", "google_sheets_id", "google_sheets_name",
        "google_integration_instructions",
        "whatsapp_enabled", "whatsapp_phone_number_id", "whatsapp_waba_id",
        "whatsapp_access_token", "whatsapp_template_name", "whatsapp_template_language",
        "whatsapp_integration_instructions",
    }

    clean_updates = {}
    for key, value in updates.items():
        if key in ("id", "created_at", "user_id"):
            continue
        clean_updates[key] = value
        if key == "language" and value:
            if "|" in value:
                clean_updates["tts_language_code"] = value.split("|", 1)[1]
            else:
                clean_updates["tts_language_code"] = "en-IN"

    clean_updates["updated_at"] = datetime.utcnow().isoformat() + "Z"

    if db.supabase:
        try:
            res = db.supabase.table("agents").update(clean_updates).eq("id", agent_id).eq("user_id", user_id).execute()
            if res.data:
                return _backfill_defaults(res.data[0])
        except Exception as e:
            print(f"[agents_store] Supabase update failed: {e}. Falling back to local store.")

    store = _load()
    if agent_id not in store["agents"]:
        return None
    agent = store["agents"][agent_id]
    if agent.get("user_id") != user_id:
        return None

    for key, value in clean_updates.items():
        if key in agent or key in ALLOWED_NEW_FIELDS:
            agent[key] = value

    store["agents"][agent_id] = agent
    _save(store)
    return agent


def delete_agent(agent_id: str, user_id: str) -> bool:
    """Delete an agent."""
    if db.supabase:
        try:
            res = db.supabase.table("agents").delete().eq("id", agent_id).eq("user_id", user_id).execute()
            if res.data:
                return True
        except Exception as e:
            print(f"[agents_store] Supabase delete failed: {e}. Falling back to local store.")

    store = _load()
    if agent_id in store["agents"]:
        if store["agents"][agent_id].get("user_id") == user_id:
            del store["agents"][agent_id]
            _save(store)
            return True
    return False


def increment_call(agent_id: str, duration_minutes: float = 0.0):
    """Increment calls count and total talk time."""
    if db.supabase:
        try:
            agent = get_agent(agent_id)
            if agent:
                new_calls = agent.get("calls_count", 0) + 1
                new_minutes = float(agent.get("total_minutes", 0.0)) + duration_minutes
                db.supabase.table("agents").update({
                    "calls_count": new_calls,
                    "total_minutes": new_minutes
                }).eq("id", agent_id).execute()
                return
        except Exception as e:
            print(f"[agents_store] Supabase increment failed: {e}. Falling back to local store.")

    store = _load()
    if agent_id in store["agents"]:
        store["agents"][agent_id]["calls_count"] += 1
        store["agents"][agent_id]["total_minutes"] += duration_minutes
        _save(store)
