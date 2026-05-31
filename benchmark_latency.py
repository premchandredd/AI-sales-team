import os
import sys
import time
import json
import asyncio
import struct
import math
import statistics
import httpx
import websockets
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

groq_client = AsyncGroq(api_key=GROQ_API_KEY)

def generate_pcm16_audio(duration_s=2.0, sample_rate=16000, freq=440):
    num_samples = int(sample_rate * duration_s)
    audio = bytearray()
    for i in range(num_samples):
        sample = int(32767 * 0.5 * math.sin(2 * math.pi * freq * i / sample_rate))
        audio.extend(struct.pack('<h', sample))
    return bytes(audio)

def fmt_ms(seconds):
    return f"{seconds * 1000:.0f}ms"

async def benchmark_stt(num_runs=3):
    print("\nSTAGE 1: Deepgram STT (Nova-3, Telugu) Latency")
    url = (
        "wss://api.deepgram.com/v1/listen"
        "?language=te"
        "&model=nova-3"
        "&encoding=linear16"
        "&sample_rate=16000"
        "&channels=1"
        "&punctuate=true"
        "&interim_results=true"
    )
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    audio_data = generate_pcm16_audio(2.0)
    chunk_size = 4096
    
    first_result_times = []
    
    for run in range(num_runs):
        t_connect_start = time.perf_counter()
        try:
            ws = await websockets.connect(url, additional_headers=headers)
        except Exception as e:
            print(f"  Run {run+1}: STT Connection FAILED - {e}")
            continue
            
        t_send_start = time.perf_counter()
        for i in range(0, len(audio_data), chunk_size):
            await ws.send(audio_data[i:i + chunk_size])
            await asyncio.sleep(0.01)
            
        first_result_time = None
        try:
            async for message in ws:
                data = json.loads(message)
                if data.get("type") == "Results":
                    transcript = data.get("channel", {}).get("alternatives", [{}])[0].get("transcript", "")
                    if transcript:
                        first_result_time = time.perf_counter() - t_send_start
                        first_result_times.append(first_result_time)
                        print(f"  Run {run+1}: First Result={fmt_ms(first_result_time)}")
                        break
        except Exception:
            pass
        await ws.close()
        
    return {"stt_avg_ms": statistics.mean(first_result_times) * 1000 if first_result_times else 0}

async def benchmark_llm(num_runs=3):
    print("\nSTAGE 2: Groq LLM (llama-3.3-70b-versatile) Latency")
    messages = [
        {"role": "system", "content": "You are a Telugu real estate agent."},
        {"role": "user", "content": "నేను ఒక ఇల్లు కొనాలి అని అనుకుంటున్నాను."},
    ]
    ttft_times = []
    total_times = []
    
    for run in range(num_runs):
        t_start = time.perf_counter()
        first_token_time = None
        try:
            stream = await groq_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                stream=True,
                temperature=0.7,
                max_tokens=150,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content
                if token and first_token_time is None:
                    first_token_time = time.perf_counter() - t_start
                    ttft_times.append(first_token_time)
            total_times.append(time.perf_counter() - t_start)
            print(f"  Run {run+1}: TTFT={fmt_ms(first_token_time)}")
        except Exception as e:
            print(f"  Run {run+1}: LLM FAILED - {e}")
            
    return {
        "llm_ttft_avg_ms": statistics.mean(ttft_times) * 1000 if ttft_times else 0,
        "llm_total_avg_ms": statistics.mean(total_times) * 1000 if total_times else 0
    }

async def benchmark_tts(num_runs=3):
    print("\nSTAGE 3: Sarvam TTS (Telugu) Latency")
    test_text = "నేను మీకు ఎలా సహాయం చేయగలను?"
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": [test_text],
        "target_language_code": "te-IN",
        "speaker": "ritu",
        "model": "bulbul:v3",
        "pace": 1.1,
        "speech_sample_rate": 22050,
        "enable_preprocessing": True,
    }
    latencies = []
    for run in range(num_runs):
        t_start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                latencies.append(time.perf_counter() - t_start)
                print(f"  Run {run+1}: TTS Latency={fmt_ms(latencies[-1])}")
            else:
                print(f"  Run {run+1}: TTS FAILED - {response.status_code}")
        except Exception as e:
            print(f"  Run {run+1}: TTS FAILED - {e}")
            
    return {"tts_avg_ms": statistics.mean(latencies) * 1000 if latencies else 0}

async def main():
    print("=== PIPELINE LATENCY BENCHMARK (TELUGU) ===")
    stt = await benchmark_stt(3)
    llm = await benchmark_llm(3)
    tts = await benchmark_tts(3)
    
    print("\n=== FINAL REPORT ===")
    print(json.dumps({**stt, **llm, **tts}, indent=2))

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
