"""
Google Service — Handles Google OAuth2, Google Sheets, and Google Calendar APIs.
"""

import os
import json
import datetime
import contextvars
from pathlib import Path
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

import db

TOKENS_PATH = Path(__file__).parent / "google_tokens.json"

# Context-local variable for tracking active user_id
current_user_id = contextvars.ContextVar("current_user_id", default="00000000-0000-0000-0000-000000000000")

# Module-level storage for the OAuth flow so the PKCE code_verifier
# persists between get_auth_url() and exchange_code_for_tokens().
_active_flow: Optional["Flow"] = None

# Derive javascript origins dynamically from redirect URI
google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5174/callback")
google_origin = "http://localhost:5174"
if "://" in google_redirect_uri:
    parts = google_redirect_uri.split("/")
    if len(parts) >= 3:
        google_origin = f"{parts[0]}//{parts[2]}"

CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "project_id": os.getenv("GOOGLE_PROJECT_ID", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uris": [google_redirect_uri],
        "javascript_origins": [google_origin]
    }
}

SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "openid"
]

def save_credentials(credentials: Credentials, user_id: Optional[str] = None):
    """Save user credentials to Supabase, or fall back to local disk."""
    if user_id is None:
        user_id = current_user_id.get()

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    if credentials.expiry:
        token_data["expiry"] = credentials.expiry.isoformat()

    if db.supabase and user_id != db.MOCK_USER_ID:
        try:
            db_creds = {
                "user_id": user_id,
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
            db.supabase.table("google_credentials").upsert(db_creds).execute()
            print(f"[Google Service] Credentials saved to Supabase for user {user_id}")
            return
        except Exception as e:
            print(f"[Google Service] Supabase save credentials failed: {e}. Falling back to disk.")

    with open(TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def get_credentials(user_id: Optional[str] = None) -> Optional[Credentials]:
    """Retrieve credentials from Supabase or disk, refreshing them if expired."""
    if user_id is None:
        user_id = current_user_id.get()

    credentials = None

    if db.supabase and user_id != db.MOCK_USER_ID:
        try:
            res = db.supabase.table("google_credentials").select("*").eq("user_id", user_id).execute()
            if res.data:
                db_creds = res.data[0]
                expiry_dt = None
                if db_creds.get("expiry"):
                    dt = datetime.datetime.fromisoformat(db_creds["expiry"].replace("Z", "+00:00"))
                    expiry_dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)

                
                credentials = Credentials(
                    token=db_creds["token"],
                    refresh_token=db_creds.get("refresh_token"),
                    token_uri=db_creds["token_uri"],
                    client_id=db_creds["client_id"],
                    client_secret=db_creds["client_secret"],
                    scopes=db_creds["scopes"],
                    expiry=expiry_dt
                )
        except Exception as e:
            print(f"[Google Service] Supabase load credentials failed: {e}. Falling back to disk.")

    if not credentials:
        if not TOKENS_PATH.exists():
            return None
        try:
            credentials = Credentials.from_authorized_user_file(str(TOKENS_PATH), SCOPES)
        except Exception as e:
            print(f"[Google Service] Error loading credentials from disk: {e}")
            return None

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            print("[Google Service] Refreshing expired credentials...")
            credentials.refresh(Request())
            save_credentials(credentials, user_id)
        except Exception as e:
            print(f"[Google Service] Error refreshing credentials: {e}")
            return None

    return credentials


def delete_credentials(user_id: Optional[str] = None):
    """Remove credentials (logout)."""
    if user_id is None:
        user_id = current_user_id.get()

    if db.supabase and user_id != db.MOCK_USER_ID:
        try:
            db.supabase.table("google_credentials").delete().eq("user_id", user_id).execute()
            print(f"[Google Service] Credentials deleted from Supabase for user {user_id}")
        except Exception as e:
            print(f"[Google Service] Supabase delete credentials failed: {e}")

    if TOKENS_PATH.exists():
        try:
            os.remove(TOKENS_PATH)
            print("[Google Service] Credentials deleted from disk.")
        except Exception:
            pass


def get_auth_url() -> str:
    """Generate authorization URL for Google OAuth2."""
    global _active_flow
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0]
    )
    # offline access is required to get a refresh token
    # prompt='consent' ensures the refresh token is sent every time
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes=True
    )
    # Store the flow so the PKCE code_verifier is available during exchange
    _active_flow = flow
    return auth_url


def exchange_code_for_tokens(code: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Exchange authorization code for credentials and save them."""
    global _active_flow
    # Reuse the flow from get_auth_url() to preserve the PKCE code_verifier.
    # If _active_flow is missing (e.g. server restarted), create a fresh one.
    if _active_flow is not None:
        flow = _active_flow
        _active_flow = None  # consume it
    else:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0]
        )
    flow.fetch_token(code=code)
    credentials = flow.credentials
    save_credentials(credentials, user_id)
    
    # Get user profile information
    user_info = get_user_info(credentials, user_id)
    return user_info

def get_user_info(credentials: Optional[Credentials] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetch logged in user profile info."""
    creds = credentials or get_credentials(user_id)
    if not creds:
        return {"authenticated": False}
    
    try:
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return {
            "authenticated": True,
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "scopes": creds.scopes,
        }
    except Exception as e:
        print(f"[Google Service] Failed to fetch user info: {e}")
        return {"authenticated": False, "error": str(e)}

# ─── Google Drive & Sheets API ───

def get_column_letter(col_idx: int) -> str:
    """Convert a 0-based column index to a Google Sheets column letter (e.g. 0 -> A, 25 -> Z, 26 -> AA)."""
    letter = ""
    col_idx += 1
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter

def list_spreadsheets() -> List[Dict[str, Any]]:
    """List Google Sheets files in the user's Google Drive."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
    
    try:
        service = build("drive", "v3", credentials=creds)
        # Query for files that are spreadsheets and not in trash
        query = "mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=50,
            fields="files(id, name, modifiedTime)"
        ).execute()
        return results.get("files", [])
    except Exception as e:
        print(f"[Google Service] Error listing spreadsheets: {e}")
        raise e

def list_sheets(spreadsheet_id: str) -> List[str]:
    """List sheet names (tabs) within a Google Spreadsheet."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
    
    try:
        service = build("sheets", "v4", credentials=creds)
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get("sheets", [])
        return [sheet.get("properties", {}).get("title") for sheet in sheets if sheet.get("properties", {}).get("title")]
    except Exception as e:
        print(f"[Google Service] Error listing sheet tabs: {e}")
        raise e

def get_sheet_data(spreadsheet_id: str, sheet_name: str) -> List[Dict[str, Any]]:
    """
    Get all rows from a spreadsheet as a list of dictionaries.
    Uses the first row as keys.
    """
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
    
    try:
        service = build("sheets", "v4", credentials=creds)
        # Read the entire sheet content
        range_name = f"'{sheet_name}'!A1:Z1000"
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        values = result.get("values", [])
        
        if not values:
            return []
            
        headers = [h.strip() for h in values[0]]
        rows = []
        
        for idx, row in enumerate(values[1:], start=2): # 1-indexed, starts at row 2
            row_dict = {"__row__": idx} # track actual spreadsheet row index
            for h_idx, header in enumerate(headers):
                if h_idx < len(row):
                    row_dict[header] = row[h_idx]
                else:
                    row_dict[header] = ""
            rows.append(row_dict)
            
        return rows
    except Exception as e:
        print(f"[Google Service] Error reading sheet data: {e}")
        raise e

def update_cell(spreadsheet_id: str, sheet_name: str, row: int, col_letter: str, value: str):
    """Update a specific cell value in the Google Sheet."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
        
    try:
        service = build("sheets", "v4", credentials=creds)
        range_name = f"'{sheet_name}'!{col_letter}{row}"
        body = {
            "values": [[value]]
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body=body
        ).execute()
        print(f"[Google Service] Updated cell {range_name} to '{value}'")
    except Exception as e:
        print(f"[Google Service] Error updating cell: {e}")
        raise e

def update_lead_status_in_sheet(spreadsheet_id: str, sheet_name: str, row_idx: int, status: str, notes: str = ""):
    """
    Update the lead status and notes in a specific row.
    If the 'Status' or 'Notes' column doesn't exist, they are appended as new columns.
    """
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
        
    try:
        service = build("sheets", "v4", credentials=creds)
        # Fetch first row (headers) to find/create columns
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1:Z1"
        ).execute()
        headers = result.get("values", [])[0] if result.get("values") else []
        
        # Ensure 'Status' and 'Notes' exist
        status_col_idx = -1
        notes_col_idx = -1
        
        for idx, h in enumerate(headers):
            h_clean = h.strip().lower()
            if h_clean == "status":
                status_col_idx = idx
            elif h_clean == "notes":
                notes_col_idx = idx
                
        # If columns don't exist, we add them to the header
        new_headers = list(headers)
        if status_col_idx == -1:
            status_col_idx = len(new_headers)
            new_headers.append("Status")
        if notes_col_idx == -1:
            notes_col_idx = len(new_headers)
            new_headers.append("Notes")
            
        if len(new_headers) > len(headers):
            # Update headers row
            end_col_letter = get_column_letter(len(new_headers) - 1)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1:{end_col_letter}1",
                valueInputOption="RAW",
                body={"values": [new_headers]}
            ).execute()
            
        # Write lead qualification data to the specified row
        # Map indices to column letters (0 -> A, 1 -> B, ...)
        status_col_letter = get_column_letter(status_col_idx)
        notes_col_letter = get_column_letter(notes_col_idx)
        
        update_cell(spreadsheet_id, sheet_name, row_idx, status_col_letter, status)
        if notes:
            update_cell(spreadsheet_id, sheet_name, row_idx, notes_col_letter, notes)
            
    except Exception as e:
        print(f"[Google Service] Error updating lead status in sheet: {e}")
        raise e

def create_template_leads_sheet() -> Dict[str, Any]:
    """Create a new Google Sheet named 'Voice Agent Lead Campaign' with template headers."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
        
    try:
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_body = {
            "properties": {
                "title": f"Voice Agent Leads - {datetime.date.today().strftime('%Y-%m-%d')}"
            },
            "sheets": [
                {
                    "properties": {
                        "title": "Leads"
                    }
                }
            ]
        }
        spreadsheet = service.spreadsheets().create(
            body=spreadsheet_body,
            fields="spreadsheetId,properties/title"
        ).execute()
        
        spreadsheet_id = spreadsheet.get("spreadsheetId")
        
        # Write headers and sample data
        headers = ["Name", "Phone", "Status", "Notes"]
        sample_rows = [
            headers,
            ["John Doe", "+1234567890", "New", ""],
            ["Jane Smith", "+1987654321", "New", ""],
            ["Bob Johnson", "+1122334455", "New", ""]
        ]
        
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="'Leads'!A1:D4",
            valueInputOption="RAW",
            body={"values": sample_rows}
        ).execute()
        
        return {
            "id": spreadsheet_id,
            "name": spreadsheet.get("properties", {}).get("title"),
        }
    except Exception as e:
        print(f"[Google Service] Error creating spreadsheet: {e}")
        raise e

def create_custom_leads_sheet(columns: List[str], title: str = None) -> Dict[str, Any]:
    """Create a new Google Sheet with custom column headers (no sample data)."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")

    if not title:
        title = f"Voice Agent Leads - {datetime.date.today().strftime('%Y-%m-%d')}"

    try:
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_body = {
            "properties": {"title": title},
            "sheets": [{"properties": {"title": "Leads"}}]
        }
        spreadsheet = service.spreadsheets().create(
            body=spreadsheet_body,
            fields="spreadsheetId,properties/title"
        ).execute()

        spreadsheet_id = spreadsheet.get("spreadsheetId")

        # Write only headers — no sample data
        col_count = len(columns)
        end_col = get_column_letter(col_count - 1) if col_count > 0 else "A"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'Leads'!A1:{end_col}1",
            valueInputOption="RAW",
            body={"values": [columns]}
        ).execute()

        return {
            "id": spreadsheet_id,
            "name": spreadsheet.get("properties", {}).get("title"),
        }
    except Exception as e:
        print(f"[Google Service] Error creating custom spreadsheet: {e}")
        raise e

def append_row_to_sheet(spreadsheet_id: str, sheet_name: str, row_values: List[Any]):
    """Append a list of values as a new row in a spreadsheet."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
    try:
        service = build("sheets", "v4", credentials=creds)
        body = {"values": [row_values]}
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        print(f"[Google Service] Appended row to {sheet_name}: {row_values}")
    except Exception as e:
        print(f"[Google Service] Error appending row to sheet: {e}")
        raise e

# ─── Google Calendar API ───

def list_calendars() -> List[Dict[str, Any]]:
    """List Google Calendars of the authenticated user."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
        
    try:
        service = build("calendar", "v3", credentials=creds)
        calendar_list = service.calendarList().list().execute()
        items = calendar_list.get("items", [])
        return [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False)
            } for item in items
        ]
    except Exception as e:
        print(f"[Google Service] Error listing calendars: {e}")
        raise e

def book_calendar_event(
    calendar_id: str,
    start_time_iso: str,
    end_time_iso: str,
    summary: str,
    description: str = "",
    create_meet: bool = False,
    attendee_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new calendar event, optionally with a Google Meet link and attendee.
    start_time_iso and end_time_iso must be ISO 8601 strings.
    """
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
        
    try:
        import uuid
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time_iso,
            },
            "end": {
                "dateTime": end_time_iso,
            },
            "reminders": {
                "useDefault": True,
            },
        }
        
        if create_meet:
            event["conferenceData"] = {
                "createRequest": {
                    "requestId": f"meet-{uuid.uuid4().hex[:8]}",
                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet"
                    }
                }
            }
            
        if attendee_email:
            event["attendees"] = [{"email": attendee_email}]
            
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event,
            conferenceDataVersion=1 if create_meet else 0,
            sendUpdates="all" if attendee_email else "none"
        ).execute()
        
        meet_link = created_event.get("hangoutLink")
        if not meet_link:
            entry_points = created_event.get("conferenceData", {}).get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri")
                    break
        
        print(f"[Google Service] Event booked successfully. Meet: {meet_link}, Link: {created_event.get('htmlLink')}")
        return {
            "id": created_event.get("id"),
            "htmlLink": created_event.get("htmlLink"),
            "summary": created_event.get("summary"),
            "start": created_event.get("start", {}).get("dateTime"),
            "meetLink": meet_link,
        }
    except Exception as e:
        print(f"[Google Service] Error booking calendar event: {e}")
        raise e

def send_email_via_gmail(to_email: str, subject: str, body_text: str) -> bool:
    """Send an email using the user's authenticated Gmail account."""
    creds = get_credentials()
    if not creds:
        print("[Google Service] No credentials available, cannot send email")
        return False
        
    try:
        import base64
        from email.mime.text import MIMEText
        service = build("gmail", "v1", credentials=creds)
        message = MIMEText(body_text)
        message["to"] = to_email
        message["subject"] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body = {"raw": raw_message}
        
        service.users().messages().send(userId="me", body=body).execute()
        print(f"[Google Service] Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[Google Service] Error sending email via Gmail: {e}")
        raise e

def get_sheet_headers(spreadsheet_id: str, sheet_name: str) -> List[str]:
    """Retrieve the column headers (first row) of a sheet."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
    try:
        service = build("sheets", "v4", credentials=creds)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1:Z1"
        ).execute()
        values = result.get("values", [])
        if not values or not values[0]:
            return []
        return [h.strip() for h in values[0] if h.strip()]
    except Exception as e:
        print(f"[Google Service] Error getting sheet headers: {e}")
        raise e

def update_sheet_headers(spreadsheet_id: str, sheet_name: str, columns: List[str]):
    """Overwrite the headers row (first row) of a sheet."""
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
    try:
        service = build("sheets", "v4", credentials=creds)
        col_count = len(columns)
        end_col = get_column_letter(col_count - 1) if col_count > 0 else "A"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1:{end_col}1",
            valueInputOption="RAW",
            body={"values": [columns]}
        ).execute()
        print(f"[Google Service] Updated sheet headers to: {columns}")
    except Exception as e:
        print(f"[Google Service] Error updating sheet headers: {e}")
        raise e

def check_calendar_availability(
    calendar_id: str,
    time_min_iso: str,
    time_max_iso: str
) -> List[Dict[str, Any]]:
    """
    Check availability by listing events on a calendar within a specific time range.
    Returns a list of dictionaries with start, end, and summary of existing events (busy slots).
    """
    creds = get_credentials()
    if not creds:
        raise Exception("Google account not connected")
        
    try:
        service = build("calendar", "v3", credentials=creds)
        
        # Call the Calendar API to list events
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            singleEvents=True,
            orderBy="startTime",
            fields="items(summary,start,end)"
        ).execute()
        
        events = events_result.get("items", [])
        
        busy_slots = []
        for event in events:
            start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
            end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
            summary = event.get("summary", "Busy")
            busy_slots.append({
                "summary": summary,
                "start": start,
                "end": end
            })
            
        return busy_slots
    except Exception as e:
        print(f"[Google Service] Error checking calendar availability: {e}")
        raise e

