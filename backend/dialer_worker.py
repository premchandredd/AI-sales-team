import os
import asyncio
import datetime
from db import supabase
from twilio.rest import Client

class CampaignDialer:
    _instance = None
    _task = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker_loop())
            print("[Dialer] Background worker loop started.")
            
    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            print("[Dialer] Background worker loop stopped.")
            
    async def _worker_loop(self):
        while True:
            try:
                await self._process_active_campaigns()
            except Exception as e:
                print(f"[Dialer] Worker error occurred: {e}")
            await asyncio.sleep(10)  # Check every 10 seconds

    async def _process_active_campaigns(self):
        if not supabase:
            return
            
        # 1. Fetch active campaigns
        res = await asyncio.to_thread(
            lambda: supabase.table("campaigns").select("*").eq("status", "active").execute()
        )
        campaigns = res.data or []
        
        for camp in campaigns:
            camp_id = camp["id"]
            user_id = camp["user_id"]
            agent_id = camp["agent_id"]
            spreadsheet_id = camp.get("spreadsheet_id")
            sheet_name = camp.get("sheet_name")
            campaign_type = camp.get("campaign_type", "outbound")
            
            # Skip inbound campaigns — they don't auto-dial
            if campaign_type == "inbound":
                continue
            
            # 1.1 Check allowed time hours
            start_time = camp.get("start_time") or "09:00"
            end_time = camp.get("end_time") or "18:00"
            
            now = datetime.datetime.now()
            now_str = now.strftime("%H:%M")
            if not (start_time <= now_str <= end_time):
                print(f"[Dialer] Campaign '{camp['name']}' ({camp_id}) is outside of operating hours ({start_time} - {end_time}). Current time: {now_str}")
                continue

            # 2. Check concurrency limit
            max_concurrent = camp.get("max_concurrent_calls") or 1
            if max_concurrent < 1:
                max_concurrent = 1

            active_res = await asyncio.to_thread(
                lambda: supabase.table("campaign_leads")
                .select("id")
                .eq("campaign_id", camp_id)
                .eq("status", "calling")
                .execute()
            )
            active_calls_count = len(active_res.data or [])
            if active_calls_count >= max_concurrent:
                print(f"[Dialer] Campaign '{camp['name']}' reached concurrency limit ({active_calls_count}/{max_concurrent}). Waiting.")
                continue
                
            limit_needed = max_concurrent - active_calls_count

            # 3. Get next pending leads
            lead_res = await asyncio.to_thread(
                lambda: supabase.table("campaign_leads")
                .select("*")
                .eq("campaign_id", camp_id)
                .eq("status", "pending")
                .order("created_at", desc=False)
                .limit(limit_needed)
                .execute()
            )
            leads = lead_res.data or []
            
            # 3.1 Check for retryable failed leads
            retry_count = camp.get("retry_count") or 0
            if retry_count > 0 and len(leads) < limit_needed:
                retry_limit = limit_needed - len(leads)
                now_iso = now.isoformat()
                try:
                    retry_res = await asyncio.to_thread(
                        lambda: supabase.table("campaign_leads")
                        .select("*")
                        .eq("campaign_id", camp_id)
                        .eq("status", "retry_pending")
                        .lt("next_retry_at", now_iso)
                        .order("next_retry_at", desc=False)
                        .limit(retry_limit)
                        .execute()
                    )
                    retry_leads = retry_res.data or []
                    leads.extend(retry_leads)
                except Exception as e:
                    print(f"[Dialer] Retry query failed: {e}")
            
            if not leads:
                if active_calls_count == 0:
                    # Check if there are any retry_pending leads still waiting
                    retry_pending_res = await asyncio.to_thread(
                        lambda: supabase.table("campaign_leads")
                        .select("id")
                        .eq("campaign_id", camp_id)
                        .eq("status", "retry_pending")
                        .limit(1)
                        .execute()
                    )
                    if not (retry_pending_res.data or []):
                        # No pending, no retries, no active calls → completed
                        await asyncio.to_thread(
                            lambda: supabase.table("campaigns")
                            .update({"status": "completed"})
                            .eq("id", camp_id)
                            .execute()
                        )
                        print(f"[Dialer] Campaign '{camp['name']}' ({camp_id}) completed!")
                continue
                
            # 4. Initiate calls
            for lead in leads:
                lead_id = lead["id"]
                to_phone = lead["phone"]
                lead_row = lead.get("lead_row")
                
                print(f"[Dialer] Dialing lead '{lead['name']}' ({to_phone}) for campaign '{camp['name']}'")
                asyncio.create_task(self._dial_lead(
                    campaign_id=camp_id,
                    lead_id=lead_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    to_phone=to_phone,
                    spreadsheet_id=spreadsheet_id,
                    sheet_name=sheet_name,
                    lead_row=lead_row,
                    retry_count=retry_count,
                    retry_delay_minutes=camp.get("retry_delay_minutes") or 15,
                    attempt_count=lead.get("attempt_count") or 0
                ))

    async def _dial_lead(self, campaign_id: str, lead_id: str, agent_id: str, user_id: str, to_phone: str, spreadsheet_id: str = None, sheet_name: str = None, lead_row: int = None, retry_count: int = 0, retry_delay_minutes: int = 15, attempt_count: int = 0):
        # Fetch user Twilio settings
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_phone = os.getenv("TWILIO_PHONE_NUMBER")
        
        try:
            res = await asyncio.to_thread(
                lambda: supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
            )
            if res.data:
                settings = res.data[0]
                account_sid = settings.get("twilio_account_sid") or account_sid
                auth_token = settings.get("twilio_auth_token") or auth_token
                from_phone = settings.get("twilio_phone_number") or from_phone
        except Exception as e:
            print(f"[Dialer] Error loading Twilio settings: {e}")
            
        if not account_sid or not auth_token or not from_phone:
            print(f"[Dialer] Error: Twilio credentials missing for user {user_id}. Marking lead as failed.")
            await asyncio.to_thread(
                lambda: supabase.table("campaign_leads")
                .update({"status": "failed", "notes": "Twilio settings missing"})
                .eq("id", lead_id)
                .execute()
            )
            return

        base_url = os.getenv("BASE_URL") or "http://localhost:8000"
        from urllib.parse import urlencode
        
        new_attempt = attempt_count + 1
        
        params = {
            "agent_id": agent_id,
            "campaign_id": campaign_id,
            "lead_id": lead_id,
            "spreadsheet_id": spreadsheet_id or "",
            "sheet_name": sheet_name or "",
            "lead_row": str(lead_row) if lead_row is not None else ""
        }
        twiml_url = f"{base_url}/api/telephony/campaign-twiml?{urlencode(params)}"
        
        # Mark lead as calling
        await asyncio.to_thread(
            lambda: supabase.table("campaign_leads")
            .update({"status": "calling", "attempt_count": new_attempt})
            .eq("id", lead_id)
            .execute()
        )

        try:
            def place_call():
                client = Client(account_sid, auth_token)
                return client.calls.create(
                    to=to_phone,
                    from_=from_phone,
                    url=twiml_url,
                    status_callback=f"{base_url}/api/telephony/campaign-callback?{urlencode(params)}",
                    status_callback_event=["completed", "failed", "busy", "no-answer"]
                )
                
            call = await asyncio.to_thread(place_call)
            
            # Save call SID to lead
            await asyncio.to_thread(
                lambda: supabase.table("campaign_leads")
                .update({"call_sid": call.sid})
                .eq("id", lead_id)
                .execute()
            )
            print(f"[Dialer] Call created successfully. CallSid={call.sid} (attempt {new_attempt})")
            
        except Exception as e:
            print(f"[Dialer] Twilio outbound failed: {e}")
            # Check if we should retry
            if new_attempt < retry_count:
                next_retry = datetime.datetime.now() + datetime.timedelta(minutes=retry_delay_minutes)
                await asyncio.to_thread(
                    lambda: supabase.table("campaign_leads")
                    .update({
                        "status": "retry_pending",
                        "notes": f"Attempt {new_attempt} failed: {str(e)}",
                        "next_retry_at": next_retry.isoformat()
                    })
                    .eq("id", lead_id)
                    .execute()
                )
                print(f"[Dialer] Lead '{lead_id}' scheduled for retry at {next_retry.isoformat()} (attempt {new_attempt}/{retry_count})")
            else:
                await asyncio.to_thread(
                    lambda: supabase.table("campaign_leads")
                    .update({"status": "failed", "notes": f"Twilio Error (attempt {new_attempt}): {str(e)}"})
                    .eq("id", lead_id)
                    .execute()
                )


