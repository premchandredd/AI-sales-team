import asyncio
import websockets
import os
from dotenv import load_dotenv
import requests

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
        
def test_deepgram_rest(params_str):
    url = f"https://api.deepgram.com/v1/listen?{params_str}"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }
    response = requests.post(url, headers=headers, data=b"")
    print(f"REST Status for {params_str}: {response.status_code}")
    if response.status_code != 200:
        print(f"REST Error body: {response.text}")

async def main():
    test_deepgram_rest("language=te&model=nova-3")
    await test_deepgram_ws("language=te&encoding=linear16&sample_rate=16000&channels=1&model=nova-3")
    
    test_deepgram_rest("language=te&model=nova-3&tier=nova-3")
    await test_deepgram_ws("language=te&encoding=linear16&sample_rate=16000&channels=1&model=nova-3&tier=nova-3")

asyncio.run(main())
