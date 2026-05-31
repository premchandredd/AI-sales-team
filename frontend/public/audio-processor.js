// AudioWorklet Processor — captures raw PCM16 samples from the microphone.
// This runs in a separate audio thread for zero-latency capture.

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(0);
    // ~128ms chunks at 16kHz = 2048 samples
    this._targetSize = 2048;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0]; // mono channel

    // Append incoming samples to our buffer
    const newBuffer = new Float32Array(this._buffer.length + channelData.length);
    newBuffer.set(this._buffer);
    newBuffer.set(channelData, this._buffer.length);
    this._buffer = newBuffer;

    // When we have enough samples, convert float32 → int16 and send
    while (this._buffer.length >= this._targetSize) {
      const chunk = this._buffer.slice(0, this._targetSize);
      this._buffer = this._buffer.slice(this._targetSize);

      // Convert float32 [-1.0, 1.0] → int16 [-32768, 32767]
      const int16 = new Int16Array(chunk.length);
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      // Transfer the buffer to the main thread (zero-copy)
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
