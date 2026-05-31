import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def test_deepgram(lang, model):
    url = f"wss://api.deepgram.com/v1/listen?language={lang}&encoding=linear16&sample_rate=16000&channels=1&model={model}"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    try:
        ws = await websockets.connect(url, additional_headers=headers)
        print(f"Success: lang={lang}, model={model} works!")
        await ws.close()
    except Exception as e:
        print(f"Failed: lang={lang}, model={model} -> {e}")

async def main():
    await test_deepgram("te", "general")
    await test_deepgram("te", "whisper-medium")
    await test_deepgram("te", "whisper-large")

asyncio.run(main())
