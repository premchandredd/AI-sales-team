import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Usually service_role key
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[Supabase] Connected to {SUPABASE_URL}")
    except Exception as e:
        print(f"[Supabase] Error initializing client: {e}")
else:
    print("[Supabase] WARNING: SUPABASE_URL or SUPABASE_KEY missing from environment.")

# Fallback Mock User ID for local sandbox testing
MOCK_USER_ID = "00000000-0000-0000-0000-000000000000"

def get_user_id_from_token(auth_header: Optional[str]) -> str:
    """
    Decodes the Supabase JWT token or verifies it via Supabase API, returning the user's UUID.
    If auth is missing or invalid and Supabase is not configured, falls back to MOCK_USER_ID.
    """
    if not auth_header:
        return MOCK_USER_ID

    if not auth_header.startswith("Bearer "):
        # Check if the token is passed directly without Bearer prefix
        token = auth_header.strip()
    else:
        token = auth_header.split(" ", 1)[1].strip()

    if not token or token == "null" or token == "undefined":
        return MOCK_USER_ID

    if not supabase:
        return MOCK_USER_ID

    try:
        # Verify and fetch user using Supabase auth client
        res = supabase.auth.get_user(token)
        if res and res.user:
            return str(res.user.id)
    except Exception as e:
        print(f"[Auth] Supabase token verification failed: {e}")
        # Try local JWT decode as fallback if pyjwt is available and secret is present
        try:
            import jwt
            if SUPABASE_JWT_SECRET:
                # The secret might be HS256 key
                payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
                if "sub" in payload:
                    return str(payload["sub"])
        except Exception as local_e:
            print(f"[Auth] Local JWT decode failed: {local_e}")

    return MOCK_USER_ID
