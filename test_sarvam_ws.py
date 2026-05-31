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
    
    print("Connecting to Sarvam WS...")
    t_start = time.perf_counter()
    
    async with websockets.connect(uri, additional_headers=headers) as ws:
        # Send config
        config = {
            "type": "config",
            "data": {
                "target_language_code": "te-IN",
                "speaker": "ritu",
                "output_audio_format": {"codec": "pcm", "sample_rate": 22050}
            }
        }
        await ws.send(json.dumps(config))
        
        t_text_send = time.perf_counter()
        
        # Send text
        text_message = {
            "type": "text",
            "data": {"text": "నేను మీకు ఎలా సహాయం చేయగలను?"}
        }
        await ws.send(json.dumps(text_message))
        
        # Send flush
        await ws.send(json.dumps({"type": "flush"}))
        
        first_audio_time = None
        total_audio = bytearray()
        
        while True:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("type") == "audio" and "data" in data:
                    audio_b64 = data["data"].get("audio", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        total_audio.extend(audio_bytes)
                        if first_audio_time is None:
                            first_audio_time = time.perf_counter() - t_text_send
                            print(f"Time to First Audio Chunk: {first_audio_time * 1000:.0f}ms")
                elif data.get("type") == "flush_complete":
                    print("Received flush_complete!")
                    break
                elif data.get("type") == "error":
                    print(f"Error from server: {data}")
                    break
            except asyncio.TimeoutError:
                print("Timeout waiting for audio")
                break
                
        print(f"Total audio received: {len(total_audio)/1024:.1f} KB")

asyncio.run(test_sarvam_ws())
