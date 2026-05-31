import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def test_deepgram(lang):
    url = f"wss://api.deepgram.com/v1/listen?language={lang}&encoding=linear16&sample_rate=16000&channels=1"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    try:
        ws = await websockets.connect(url, additional_headers=headers)
        print(f"Success: lang={lang} is supported by Deepgram streaming!")
        await ws.close()
    except Exception as e:
        print(f"Failed: lang={lang} -> {e}")

async def main():
    await test_deepgram("te")
    await test_deepgram("te-IN")
    await test_deepgram("ta")
    await test_deepgram("ta-IN")

asyncio.run(main())
