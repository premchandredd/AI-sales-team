import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

async def test_sarvam_messages():
    uri = "wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v3"
    headers = {"api-subscription-key": SARVAM_API_KEY}
    
    async with websockets.connect(uri, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "config",
            "data": {
                "target_language_code": "te-IN",
                "speaker": "ritu",
            }
        }))
        await ws.send(json.dumps({"type": "text", "data": {"text": "హలో, మీరు ఎలా ఉన్నారు?"}}))
        await ws.send(json.dumps({"type": "flush"}))
        
        while True:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(response)
                print(f"Message received: type={data.get('type')}")
                if data.get("type") != "audio":
                    print(f"Full message: {data}")
            except asyncio.TimeoutError:
                print("TIMEOUT REACHED")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

asyncio.run(test_sarvam_messages())
