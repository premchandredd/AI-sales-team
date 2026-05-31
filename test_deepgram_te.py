import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def test_deepgram(params_str):
    url = f"wss://api.deepgram.com/v1/listen?{params_str}"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    try:
        ws = await websockets.connect(url, additional_headers=headers)
        print(f"Success with params: {params_str}")
        await ws.close()
    except Exception as e:
        print(f"Failed with params: {params_str} -> {e}")

async def main():
    # Bare minimum for Telugu
    await test_deepgram("language=te&encoding=linear16&sample_rate=16000&channels=1")
    # Add punctuate
    await test_deepgram("language=te&encoding=linear16&sample_rate=16000&channels=1&punctuate=true")
    # Add interim_results
    await test_deepgram("language=te&encoding=linear16&sample_rate=16000&channels=1&interim_results=true")
    # Add smart_format
    await test_deepgram("language=te&encoding=linear16&sample_rate=16000&channels=1&smart_format=true")
    # With nova-2 model
    await test_deepgram("language=te&encoding=linear16&sample_rate=16000&channels=1&model=nova-2")

asyncio.run(main())
