import os
import sys
import time
import json
import base64
import threading
import requests
import io
import re
import queue
from dotenv import load_dotenv
import sounddevice as sd
import soundfile as sf
import numpy as np
from groq import Groq
import pygame

# Global state for interruption
playback_interrupted = False

# 1. Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

if not GROQ_API_KEY or not SARVAM_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
    print("Error: API keys not found or default. Please set GROQ_API_KEY and SARVAM_API_KEY in the .env file.")
    sys.exit(1)

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# 2. Pygame mixer initialization for audio playback
pygame.mixer.init()

# 3. Conversation history
system_prompt = (
    "You are an AI sales consultant for KPN Promoters in Chennai. "
    "Keep your answers to one or two short sentences. "
    "Be polite, natural, and conversational. "
    "Your main goal is to get the user to agree to a site visit for Omega Town."
)

conversation_history = [
    {"role": "system", "content": system_prompt}
]

def record_audio_vad(filename="input.wav", samplerate=16000, silence_duration=1.5, threshold=300):
    """Records audio automatically using Voice Activity Detection (VAD)."""
    global playback_interrupted
    print("\nListening... (Speak now)")
    
    audio_data = []
    recording = False
    silent_chunks = 0
    chunk_size = 1024
    chunks_per_second = samplerate / chunk_size
    max_silent_chunks = int(silence_duration * chunks_per_second)
    
    with sd.InputStream(samplerate=samplerate, channels=1, dtype='int16') as stream:
        while True:
            data, _ = stream.read(chunk_size)
            # Calculate volume/energy of the chunk
            rms = np.sqrt(np.mean(np.square(data.astype(np.float32))))
            
            if not recording:
                if rms > threshold:
                    # User started speaking! Interrupt if AI is currently playing audio.
                    if pygame.mixer.music.get_busy():
                        print("\n[AI Interrupted!]")
                        playback_interrupted = True
                        pygame.mixer.music.stop()
                        
                    recording = True
                    print("Voice detected! Recording...")
                    audio_data.append(data)
            else:
                audio_data.append(data)
                if rms < threshold:
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                    
                if silent_chunks > max_silent_chunks:
                    print("Silence detected. Processing...")
                    break
                    
    if not audio_data:
        return False
        
    audio_np = np.concatenate(audio_data, axis=0)
    sf.write(filename, audio_np, samplerate)
    return True

def transcribe_audio(filename="input.wav"):
    """Transcribes audio using Groq Whisper model."""
    print("Transcribing...")
    with open(filename, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(filename, file.read()),
            model="whisper-large-v3",
        )
    return transcription.text

def get_llm_response(user_text):
    """Gets response from Groq Llama 3 model."""
    print("Generating response...")
    conversation_history.append({"role": "user", "content": user_text})
    
    chat_completion = client.chat.completions.create(
        messages=conversation_history,
        model="llama-3.1-8b-instant",
    )
    
    ai_response = chat_completion.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": ai_response})
    
    return ai_response

def generate_and_play_tts(text, filename="output.wav"):
    """Generates TTS using Sarvam API in parallel chunks to reduce latency."""
    global playback_interrupted
    playback_interrupted = False
    
    print(f"Streaming audio...")
    
    # Split text into sentences to stream them one by one
    sentences = re.split(r'(?<=[.!?]) +', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return
        
    audio_queue = queue.Queue()
    
    def fetch_all():
        try:
            for sentence in sentences:
                if playback_interrupted:
                    break
                url = "https://api.sarvam.ai/text-to-speech"
                payload = {
                    "inputs": [sentence],
                    "target_language_code": "en-IN", 
                    "speaker": "priya",
                    "pace": 1.0,
                    "speech_sample_rate": 8000,
                    "enable_preprocessing": True,
                    "model": "bulbul:v3"
                }
                headers = {
                    "api-subscription-key": SARVAM_API_KEY,
                    "Content-Type": "application/json"
                }
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    resp_json = response.json()
                    if "audios" in resp_json and len(resp_json["audios"]) > 0:
                        audio_bytes = base64.b64decode(resp_json["audios"][0])
                        audio_queue.put(audio_bytes)
                else:
                    print(f"Error from Sarvam API: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            # Signal that all sentences are fetched
            audio_queue.put("DONE")

    # Start fetching in background thread
    fetch_thread = threading.Thread(target=fetch_all)
    fetch_thread.start()
    
    def play_all():
        global playback_interrupted
        while True:
            if playback_interrupted:
                break
                
            item = audio_queue.get()
            if item == "DONE":
                break
                
            # Play directly from memory instead of saving to disk
            audio_io = io.BytesIO(item)
            pygame.mixer.music.load(audio_io)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if playback_interrupted:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.05)
            pygame.mixer.music.unload()

    # Start playing in background thread so the main loop can return to listening instantly
    play_thread = threading.Thread(target=play_all)
    play_thread.start()

def main():
    print("=== KPN Promoters AI Voice Agent ===")
    print("Ready. Ensure your microphone and speakers are working.")
    
    while True:
        try:
            success = record_audio_vad("input.wav")
            if not success:
                continue
                
            # 1. Transcribe audio to text
            user_text = transcribe_audio("input.wav")
            print(f"User: {user_text}")
            
            if not user_text.strip():
                print("No speech detected. Please try again.")
                continue
                
            # 2. Get AI text response
            ai_text = get_llm_response(user_text)
            print(f"AI: {ai_text}")
            
            # 3. Convert text to speech & play
            generate_and_play_tts(ai_text, "output.wav")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
