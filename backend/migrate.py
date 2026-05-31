import os
import pg8000.dbapi
from dotenv import load_dotenv

# Load env variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
DB_HOST = os.getenv("SUPABASE_DB_HOST", "db.oylogkjuzvchooftacja.supabase.co")
DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))

SQL_SCRIPT = """
-- Enable UUID generation if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Create User Settings Table (for Twilio Credentials)
CREATE TABLE IF NOT EXISTS public.user_settings (
    user_id UUID PRIMARY KEY,
    twilio_account_sid TEXT,
    twilio_auth_token TEXT,
    twilio_phone_number TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for User Settings
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can manage their own settings" ON public.user_settings;
CREATE POLICY "Users can manage their own settings" ON public.user_settings
    FOR ALL TO authenticated USING (auth.uid() = user_id);

-- 2. Create Google Credentials Table (Multi-tenant OAuth)
CREATE TABLE IF NOT EXISTS public.google_credentials (
    user_id UUID PRIMARY KEY,
    token TEXT NOT NULL,
    refresh_token TEXT,
    token_uri TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    scopes JSONB NOT NULL,
    expiry TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for Google Credentials
ALTER TABLE public.google_credentials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can manage their own Google credentials" ON public.google_credentials;
CREATE POLICY "Users can manage their own Google credentials" ON public.google_credentials
    FOR ALL TO authenticated USING (auth.uid() = user_id);

-- 3. Create Agents Table
CREATE TABLE IF NOT EXISTS public.agents (
    id TEXT PRIMARY KEY,
    user_id UUID,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'inbound',
    language TEXT NOT NULL,
    tts_language_code TEXT NOT NULL,
    tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
    tone TEXT NOT NULL DEFAULT 'Professional',
    system_prompt TEXT NOT NULL,
    first_message TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT 'llama-3.3-70b-versatile',
    voice TEXT NOT NULL DEFAULT 'aura-asteria-en',
    voice_gender TEXT NOT NULL DEFAULT 'female',
    max_tokens INTEGER NOT NULL DEFAULT 500,
    temperature NUMERIC NOT NULL DEFAULT 0.7,
    google_calendar_enabled BOOLEAN NOT NULL DEFAULT false,
    google_calendar_id TEXT NOT NULL DEFAULT 'primary',
    google_meet_enabled BOOLEAN NOT NULL DEFAULT false,
    email_notifications_enabled BOOLEAN NOT NULL DEFAULT false,
    email_integration_enabled BOOLEAN NOT NULL DEFAULT false,
    email_integration_instructions TEXT DEFAULT '',
    google_sheets_enabled BOOLEAN NOT NULL DEFAULT false,
    google_sheets_id TEXT DEFAULT '',
    google_sheets_name TEXT DEFAULT '',
    google_integration_instructions TEXT DEFAULT '',
    whatsapp_enabled BOOLEAN NOT NULL DEFAULT false,
    whatsapp_phone_number_id TEXT DEFAULT '',
    whatsapp_waba_id TEXT DEFAULT '',
    whatsapp_access_token TEXT DEFAULT '',
    whatsapp_template_name TEXT DEFAULT 'hello_world',
    whatsapp_template_language TEXT DEFAULT 'en_US',
    whatsapp_integration_instructions TEXT DEFAULT '',
    live_transfer_enabled BOOLEAN NOT NULL DEFAULT false,
    live_transfer_number TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    calls_count INTEGER NOT NULL DEFAULT 0,
    total_minutes NUMERIC NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'active'
);

-- Enable RLS for Agents
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can manage their own agents" ON public.agents;
CREATE POLICY "Users can manage their own agents" ON public.agents
    FOR ALL TO authenticated USING (auth.uid() = user_id);

-- Ensure columns exist in case agents table was already created
ALTER TABLE public.agents ADD COLUMN IF NOT EXISTS live_transfer_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.agents ADD COLUMN IF NOT EXISTS live_transfer_number TEXT NOT NULL DEFAULT '';

-- 4. Create Calls Table for conversational analytics and history
CREATE TABLE IF NOT EXISTS public.calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT REFERENCES public.agents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    call_sid TEXT,
    duration NUMERIC NOT NULL DEFAULT 0.0,
    transcript TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    sentiment TEXT DEFAULT 'Neutral',
    outcome TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS for Calls
ALTER TABLE public.calls ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can manage their own calls" ON public.calls;
CREATE POLICY "Users can manage their own calls" ON public.calls
    FOR ALL TO authenticated USING (auth.uid() = user_id);

-- 5. Create Campaigns & Lead Queue Tables
CREATE TABLE IF NOT EXISTS public.campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    agent_id TEXT REFERENCES public.agents(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'paused', -- 'paused', 'active', 'completed'
    spreadsheet_id TEXT,
    sheet_name TEXT,
    start_time TEXT DEFAULT '09:00',
    end_time TEXT DEFAULT '18:00',
    max_concurrent_calls INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.campaign_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES public.campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'calling', 'completed', 'failed'
    call_sid TEXT,
    notes TEXT DEFAULT '',
    lead_row INTEGER,
    custom_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Ensure columns exist for campaigns and leads in case they were already created
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS spreadsheet_id TEXT;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS sheet_name TEXT;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS start_time TEXT DEFAULT '09:00';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS end_time TEXT DEFAULT '18:00';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS max_concurrent_calls INTEGER DEFAULT 1;

ALTER TABLE public.campaign_leads ADD COLUMN IF NOT EXISTS lead_row INTEGER;
ALTER TABLE public.campaign_leads ADD COLUMN IF NOT EXISTS custom_data JSONB DEFAULT '{}'::jsonb;

-- Campaign redesign: inbound/outbound differentiation and advanced features
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS campaign_type TEXT DEFAULT 'outbound';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS retry_delay_minutes INTEGER DEFAULT 15;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS call_order TEXT DEFAULT 'sequential';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS after_hours_action TEXT DEFAULT 'none';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS after_hours_message TEXT DEFAULT '';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS after_hours_transfer_number TEXT DEFAULT '';

-- Campaign leads: retry tracking
ALTER TABLE public.campaign_leads ADD COLUMN IF NOT EXISTS attempt_count INTEGER DEFAULT 0;
ALTER TABLE public.campaign_leads ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITH TIME ZONE;


-- Enable RLS for Campaigns & Leads
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_leads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own campaigns" ON public.campaigns;
CREATE POLICY "Users can manage their own campaigns" ON public.campaigns
    FOR ALL TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can manage their own campaign leads" ON public.campaign_leads;
CREATE POLICY "Users can manage their own campaign leads" ON public.campaign_leads
    FOR ALL TO authenticated USING (
        EXISTS (SELECT 1 FROM public.campaigns WHERE campaigns.id = campaign_leads.campaign_id AND campaigns.user_id = auth.uid())
    );

-- 6. Create Knowledge Base & Document Chunk Tables
CREATE TABLE IF NOT EXISTS public.knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    agent_id TEXT REFERENCES public.agents(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id UUID REFERENCES public.knowledge_bases(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding JSONB -- Stores embedding vector array
);

-- Enable RLS for Knowledge Base
ALTER TABLE public.knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kb_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own knowledge bases" ON public.knowledge_bases;
CREATE POLICY "Users can manage their own knowledge bases" ON public.knowledge_bases
    FOR ALL TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can manage their own kb chunks" ON public.kb_chunks;
CREATE POLICY "Users can manage their own kb chunks" ON public.kb_chunks
    FOR ALL TO authenticated USING (
        EXISTS (SELECT 1 FROM public.knowledge_bases WHERE knowledge_bases.id = kb_chunks.kb_id AND knowledge_bases.user_id = auth.uid())
    );
"""

def run_migration():
    if not DB_PASSWORD:
        print("[Migration] ERROR: SUPABASE_DB_PASSWORD not found in environment variables.")
        print("Please provide the database password so I can run migrations directly.")
        return False

    print(f"[Migration] Connecting to database {DB_HOST}:{DB_PORT}...")
    try:
        conn = pg8000.dbapi.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            ssl_context=True
        )
        cursor = conn.cursor()
        print("[Migration] Running DDL commands...")
        cursor.execute(SQL_SCRIPT)
        conn.commit()
        cursor.close()
        conn.close()
        print("[Migration] Success! All tables and security policies created successfully.")
        return True
    except Exception as e:
        print(f"[Migration] Database connection or query failed: {e}")
        return False

if __name__ == "__main__":
    run_migration()
