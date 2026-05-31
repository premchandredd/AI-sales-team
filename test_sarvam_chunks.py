import asyncio
import websockets
import json
import time
import os
import base64
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

async def test_sarvam_ws():
    uri = "wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v3"
    headers = {"api-subscription-key": SARVAM_API_KEY}
    
    async with websockets.connect(uri, additional_headers=headers) as ws:
        config = {
            "type": "config",
            "data": {
                "target_language_code": "te-IN",
                "speaker": "ritu",
                # Omit output_audio_format to see the default, or keep it to see what we get
            }
        }
        await ws.send(json.dumps(config))
        await ws.send(json.dumps({"type": "text", "data": {"text": "నేను మీకు ఎలా సహాయం చేయగలను?"}}))
        await ws.send(json.dumps({"type": "flush"}))
        
        chunks = []
        while True:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                if data.get("type") == "audio" and "data" in data:
                    audio_b64 = data["data"].get("audio", "")
                    if audio_b64:
                        chunk = base64.b64decode(audio_b64)
                        chunks.append(chunk)
                        print(f"Chunk received: {len(chunk)} bytes. Starts with: {chunk[:4]}")
                elif data.get("type") == "flush_complete":
                    print("Stream done")
                    break
            except Exception as e:
                print(f"Error: {e}")
                break

asyncio.run(test_sarvam_ws())
