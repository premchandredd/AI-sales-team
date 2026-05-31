"""
WhatsApp Service — Handles sending messages via the official WhatsApp Cloud API (Meta).
"""
import httpx
from typing import List, Dict, Any, Optional

async def send_whatsapp_template(
    phone_number_id: str,
    access_token: str,
    recipient_phone: str,
    template_name: str,
    language_code: str = "en_US",
    parameters: List[str] = None
) -> Dict[str, Any]:
    """
    Send a template message to a recipient using Meta's WhatsApp Cloud API.
    
    Args:
        phone_number_id: Meta Phone Number ID.
        access_token: Meta Permanent Access Token.
        recipient_phone: Recipient phone number in E.164 format (e.g., +919876543210).
        template_name: Name of the pre-approved template in Meta App.
        language_code: Language code of the template (default: en_US).
        parameters: List of text parameter values to map to template variables {{1}}, {{2}}, etc.
    """
    if not phone_number_id or not access_token:
        raise ValueError("WhatsApp credentials (phone_number_id and access_token) must be provided.")
        
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Format recipient phone: remove spaces, dashes, parentheses, and keep digits only
    clean_phone = "".join(filter(str.isdigit, recipient_phone))
    
    # Ensure recipient phone starts with country code (Meta requires E.164 without '+')
    if recipient_phone.startswith("+"):
        clean_phone = recipient_phone.replace("+", "")
    
    components = []
    if parameters:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in parameters]
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        }
    }
    
    if components:
        payload["template"]["components"] = components
        
    print(f"[WhatsApp Service] Sending template '{template_name}' to {clean_phone} with params {parameters}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        res_json = response.json()
        
        if response.status_code != 200:
            print(f"[WhatsApp Service] Error sending message: {res_json}")
            raise Exception(res_json.get("error", {}).get("message", "Failed to send WhatsApp message"))
            
        print(f"[WhatsApp Service] Message sent successfully: {res_json}")
        return res_json
