import { useState, useRef, useCallback, useEffect } from 'react';

export function useVoiceStream(agentId, options = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcripts, setTranscripts] = useState([]);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const pcRef = useRef(null);
  const remoteAudioElRef = useRef(null);
  const useWebRTCRef = useRef(false);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const micStreamRef = useRef(null);
  const playbackCtxRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const mutedRef = useRef(false);
  const currentSourceRef = useRef(null);
  const disconnectedRef = useRef(false);
  const isGreetingRef = useRef(true);  // true until first message finishes playing

  // ── Stop agent audio immediately (barge-in) ──
  const stopAgentAudio = useCallback(() => {
    if (currentSourceRef.current) {
      try { currentSourceRef.current.stop(); } catch {}
      currentSourceRef.current = null;
    }
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    mutedRef.current = false;
    setIsSpeaking(false);
  }, []);

  // ── Play next audio chunk from queue ──
  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
        // All audio finished playing
        if (isGreetingRef.current) {
          // Greeting just finished → notify backend, enable mic
          isGreetingRef.current = false;
          // Tell backend greeting is done so it starts forwarding audio to STT
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'greeting_done' }));
            console.log('[Voice] Greeting done — sent signal to backend');
          }
        }
        
        // Add a small delay to prevent acoustic echo from triggering the mic immediately
        setTimeout(() => {
          if (!isGreetingRef.current) {
            mutedRef.current = false;
          }
        }, 500);

        setIsSpeaking(false);
        setIsListening(true);
      }
      return;
    }

    isPlayingRef.current = true;
    setIsSpeaking(true);

    // Only mute mic during greeting (uninterruptible)
    // For regular responses, keep mic active for barge-in
    if (isGreetingRef.current) {
      mutedRef.current = true;
    } else {
      mutedRef.current = false; // mic stays open for barge-in
    }

    const arrayBuffer = audioQueueRef.current.shift();

    try {
      if (!playbackCtxRef.current || playbackCtxRef.current.state === 'closed') {
        playbackCtxRef.current = new AudioContext();
      }
      if (playbackCtxRef.current.state === 'suspended') {
        await playbackCtxRef.current.resume();
      }

      const audioBuffer = await playbackCtxRef.current.decodeAudioData(arrayBuffer);
      const source = playbackCtxRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(playbackCtxRef.current.destination);
      currentSourceRef.current = source;

      source.onended = () => {
        currentSourceRef.current = null;
        isPlayingRef.current = false;
        playNextAudio(); // play next chunk or signal done
      };

      source.start(0);
    } catch (e) {
      console.error('Audio playback error:', e);
      currentSourceRef.current = null;
      isPlayingRef.current = false;
      mutedRef.current = false;
      setIsSpeaking(false);
      playNextAudio();
    }
  }, []);

  // ── Connect ──
  const connect = useCallback(async (callOptions = {}) => {
    if (wsRef.current || pcRef.current) return;
    setError(null);
    disconnectedRef.current = false;
    isGreetingRef.current = true; // reset for new call

    try {
      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      micStreamRef.current = micStream;

      const mergedOptions = { ...options, ...callOptions };
      useWebRTCRef.current = !!mergedOptions.useWebRTC;

      if (useWebRTCRef.current) {
        // WebRTC SDP Connection Flow
        const pc = new RTCPeerConnection({
          iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });
        pcRef.current = pc;

        // Feed browser mic audio track to peer connection
        micStream.getTracks().forEach(track => {
          pc.addTrack(track, micStream);
        });

        // Set up Data Channel for transcripts
        const dataChannel = pc.createDataChannel('transcripts');
        dataChannel.onopen = () => {
          console.log('[WebRTC] Data channel opened');
        };
        dataChannel.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'transcript') {
              if (msg.role === 'assistant') {
                setIsSpeaking(!msg.is_final);
                setIsListening(msg.is_final);
              } else if (msg.role === 'user') {
                setIsSpeaking(false);
                setIsListening(true);
              }

              setTranscripts(prev => {
                const newArr = [...prev];
                const last = newArr[newArr.length - 1];
                if (last && !last.is_final && last.role === msg.role) {
                  newArr[newArr.length - 1] = msg;
                } else {
                  newArr.push(msg);
                }
                return newArr;
              });
            }
          } catch (err) {
            console.error('[WebRTC DataChannel] Parse error:', err);
          }
        };

        // Attach remote incoming voice track
        pc.ontrack = (event) => {
          console.log('[WebRTC] Received remote track', event.streams);
          if (!remoteAudioElRef.current) {
            const audio = document.createElement('audio');
            audio.autoplay = true;
            remoteAudioElRef.current = audio;
            document.body.appendChild(audio);
          }
          if (event.streams && event.streams[0]) {
            remoteAudioElRef.current.srcObject = event.streams[0];
          } else {
            console.log('[WebRTC] No stream found in event, wrapping track in a new MediaStream');
            const stream = new MediaStream([event.track]);
            remoteAudioElRef.current.srcObject = stream;
          }
        };

        pc.onconnectionstatechange = () => {
          console.log('[WebRTC] Connection state:', pc.connectionState);
          if (pc.connectionState === 'connected') {
            setIsConnected(true);
            setIsListening(true);
          } else if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
            cleanupAll();
          }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const token = localStorage.getItem('supabase_token');
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch('http://localhost:8000/api/webrtc/offer', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type,
            agent_id: agentId,
            spreadsheet_id: mergedOptions.spreadsheetId || null,
            sheet_name: mergedOptions.sheetName || null,
            lead_row: mergedOptions.leadRow ? parseInt(mergedOptions.leadRow) : null
          })
        });

        if (!response.ok) {
          throw new Error('Failed to negotiate WebRTC with server.');
        }

        const answer = await response.json();
        await pc.setRemoteDescription(new RTCSessionDescription(answer));

      } else {
        // WebSocket Legacy Flow
        let audioCtx;
        try {
          audioCtx = new AudioContext({ sampleRate: 16000 });
        } catch {
          audioCtx = new AudioContext();
        }
        audioContextRef.current = audioCtx;

        let wsUrl = `ws://localhost:8000/api/agents/${agentId}/voice`;
        const queryParams = new URLSearchParams();
        if (mergedOptions.spreadsheetId) queryParams.append('spreadsheet_id', mergedOptions.spreadsheetId);
        if (mergedOptions.sheetName) queryParams.append('sheet_name', mergedOptions.sheetName);
        if (mergedOptions.leadRow) queryParams.append('lead_row', mergedOptions.leadRow);
        
        const token = localStorage.getItem('supabase_token');
        if (token) queryParams.append('token', token);
        
        const queryStr = queryParams.toString();
        if (queryStr) {
          wsUrl += `?${queryStr}`;
        }
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
          setIsConnected(true);
          setIsListening(true);

          const source = audioCtx.createMediaStreamSource(micStream);
          const processor = audioCtx.createScriptProcessor(4096, 1, 1);
          processorRef.current = processor;

          processor.onaudioprocess = (e) => {
            // Silence all output channels to prevent local microphone loopback/echo
            for (let i = 0; i < e.outputBuffer.numberOfChannels; i++) {
              e.outputBuffer.getChannelData(i).fill(0);
            }

            if (ws.readyState !== WebSocket.OPEN) return;
            if (mutedRef.current) return;

            const float32 = e.inputBuffer.getChannelData(0);
            const int16 = new Int16Array(float32.length);
            for (let i = 0; i < float32.length; i++) {
              const s = Math.max(-1, Math.min(1, float32[i]));
              int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            ws.send(int16.buffer);
          };

          source.connect(processor);
          processor.connect(audioCtx.destination);
        };

        ws.onmessage = (event) => {
          if (disconnectedRef.current) return;

          if (event.data instanceof ArrayBuffer) {
            audioQueueRef.current.push(event.data.slice(0));
            playNextAudio();
          } else {
            try {
              const msg = JSON.parse(event.data);

              if (msg.type === 'transcript') {
                if (msg.role === 'user' && isPlayingRef.current && !isGreetingRef.current) {
                  console.log('[Barge-in] User interrupted agent — stopping playback');
                  stopAgentAudio();

                  if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'barge_in' }));
                  }
                }

                setTranscripts(prev => {
                  const newArr = [...prev];
                  const last = newArr[newArr.length - 1];
                  if (last && !last.is_final && last.role === msg.role) {
                    newArr[newArr.length - 1] = msg;
                  } else {
                    newArr.push(msg);
                  }
                  return newArr;
                });
              } else if (msg.type === 'call_transfer') {
                console.log('[Voice] Call transfer requested to:', msg.to_phone);
                if (options.onCallTransfer) {
                  options.onCallTransfer(msg.to_phone);
                }
              }
            } catch (e) {
              console.error('[Voice] Parse error:', e);
            }
          }
        };

        ws.onerror = () => {
          setError('Failed to connect to voice server. Is the backend running?');
        };

        ws.onclose = () => {
          if (!disconnectedRef.current) cleanupAll();
        };
      }

    } catch (err) {
      console.error('[Voice] Connection failed:', err);
      setError(err.message || 'Failed to start voice call');
      cleanupAll();
    }
  }, [agentId, playNextAudio, stopAgentAudio]);

  // ── Cleanup ──
  const cleanupAll = useCallback(() => {
    disconnectedRef.current = true;
    if (currentSourceRef.current) {
      try { currentSourceRef.current.stop(); } catch {}
      currentSourceRef.current = null;
    }
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    if (micStreamRef.current) { micStreamRef.current.getTracks().forEach(t => t.stop()); micStreamRef.current = null; }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') { audioContextRef.current.close().catch(() => {}); audioContextRef.current = null; }
    if (playbackCtxRef.current && playbackCtxRef.current.state !== 'closed') { playbackCtxRef.current.close().catch(() => {}); playbackCtxRef.current = null; }
    if (pcRef.current) {
      try { pcRef.current.close(); } catch {}
      pcRef.current = null;
    }
    if (remoteAudioElRef.current) {
      try {
        remoteAudioElRef.current.srcObject = null;
        remoteAudioElRef.current.remove();
      } catch {}
      remoteAudioElRef.current = null;
    }
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    mutedRef.current = false;
    setIsConnected(false);
    setIsSpeaking(false);
    setIsListening(false);
  }, []);

  // ── Disconnect ──
  const disconnect = useCallback(() => {
    disconnectedRef.current = true;
    if (currentSourceRef.current) { try { currentSourceRef.current.stop(); } catch {} currentSourceRef.current = null; }
    audioQueueRef.current = [];
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'stop' }));
      wsRef.current.close();
      wsRef.current = null;
    }
    cleanupAll();
  }, [cleanupAll]);

  useEffect(() => {
    return () => { disconnectedRef.current = true; if (wsRef.current) { wsRef.current.close(); wsRef.current = null; } cleanupAll(); };
  }, [cleanupAll]);

  return { connect, disconnect, isConnected, isSpeaking, isListening, transcripts, error };
}
