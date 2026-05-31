import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def test_deepgram(lang, smart_format, model="nova-2"):
    url = f"wss://api.deepgram.com/v1/listen?language={lang}&encoding=linear16&sample_rate=16000&channels=1&punctuate=true&interim_results=true"
    if smart_format:
        url += "&smart_format=true"
    if model:
        url += f"&model={model}"
        
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    try:
        ws = await websockets.connect(url, additional_headers=headers)
        print(f"Success: lang={lang}, smart_format={smart_format}, model={model}")
        await ws.close()
    except Exception as e:
        print(f"Failed: lang={lang}, smart_format={smart_format}, model={model} -> {e}")

async def main():
    await test_deepgram("te", True, "nova-2")
    await test_deepgram("te", False, "nova-2")
    await test_deepgram("te", True, None)
    await test_deepgram("te", False, None)
    await test_deepgram("hi", True, "nova-2")

asyncio.run(main())
