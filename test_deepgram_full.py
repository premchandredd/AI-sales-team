import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def test_deepgram_ws(params_str):
    url = f"wss://api.deepgram.com/v1/listen?{params_str}"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    try:
        ws = await websockets.connect(url, additional_headers=headers)
        print(f"WS Success with params: {params_str}")
        await ws.close()
    except Exception as e:
        print(f"WS Failed with params: {params_str} -> {e}")

async def main():
    await test_deepgram_ws("language=te&encoding=linear16&sample_rate=16000&channels=1&model=nova-3&punctuate=true&interim_results=true&endpointing=600&utterance_end_ms=1200&vad_events=true&smart_format=true")
    
asyncio.run(main())
