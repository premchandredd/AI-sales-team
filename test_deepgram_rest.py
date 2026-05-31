import os
import requests
from dotenv import load_dotenv

load_dotenv("c:/Users/manam/OneDrive/Desktop/voicekpm/.env")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

url = "https://api.deepgram.com/v1/listen?language=te&model=nova-2"
headers = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}",
    "Content-Type": "audio/wav"
}

# Sending empty audio just to see if the configuration is accepted or rejected
response = requests.post(url, headers=headers, data=b"")
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
