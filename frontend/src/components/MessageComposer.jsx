import { useState, useRef, useEffect, useCallback } from 'react';

export default function MessageComposer({
  inputValue,
  setInputValue,
  onSend,
  isTyping,
  inputRef,
  onImageUpload,
  fileInputRef,
  currentSessionId,
}) {
  const [voiceState, setVoiceState] = useState('idle'); // 'idle' | 'recording' | 'transcribing'
  const [recordingTime, setRecordingTime] = useState(0);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const elapsedRef = useRef(0);
  const sttAbortRef = useRef(null);
  const voiceSessionTokenRef = useRef(0);

  // Auto-resize textarea
  const handleInput = (e) => {
    setInputValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  // Cleanup voice resources
  const cleanupVoiceResources = useCallback(() => {
    voiceSessionTokenRef.current += 1;
    audioChunksRef.current = [];

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (sttAbortRef.current) {
      sttAbortRef.current.abort();
      sttAbortRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
    mediaRecorderRef.current = null;
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((track) => track.stop());
      } catch {
        /* ignore */
      }
      streamRef.current = null;
    }
    setVoiceState('idle');
    setRecordingTime(0);
  }, []);

  // Clean up on unmount or session switch
  useEffect(() => {
    return cleanupVoiceResources;
  }, [cleanupVoiceResources]);

  useEffect(() => {
    cleanupVoiceResources();
  }, [currentSessionId, cleanupVoiceResources]);

  // Transcribe audio using backend Groq Whisper endpoint
  const transcribeAudio = useCallback(async (audioBlob, ext, sessionToken) => {
    if (voiceSessionTokenRef.current !== sessionToken) return;

    setVoiceState('transcribing');
    const abortCtrl = new AbortController();
    sttAbortRef.current = abortCtrl;

    try {
      const formData = new FormData();
      formData.append('file', audioBlob, `recording${ext}`);

      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/v1/voice/stt', {
        method: 'POST',
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: abortCtrl.signal,
      });

      // Verify token hasn't changed while awaiting fetch
      if (voiceSessionTokenRef.current !== sessionToken) return;

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const errorMsg = data?.detail || data?.error || `Voice transcription failed (${res.status})`;
        if (res.status === 429) {
          alert('Another voice request is already in progress. Please wait a moment.');
        } else if (res.status === 503) {
          alert('Voice transcription is temporarily unavailable or at maximum capacity. Please retry shortly.');
        } else if (res.status === 400) {
          alert('Voice recording could not be processed: ' + errorMsg);
        } else {
          alert('Transcription error: ' + errorMsg);
        }
        return;
      }

      if (!data) {
        alert('Voice server error. Make sure the backend is running.');
        return;
      }

      if (data.text && data.text.trim()) {
        const transcribed = data.text.trim();
        setInputValue((prev) => {
          const sep = prev && prev.trim() ? ' ' : '';
          return prev + sep + transcribed;
        });
      } else {
        alert('No speech detected. Speak clearly for at least 2 seconds.');
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      alert('Voice failed: ' + (err.message || 'Network error'));
    } finally {
      if (voiceSessionTokenRef.current === sessionToken) {
        sttAbortRef.current = null;
        setVoiceState('idle');
      }
    }
  }, [setInputValue]);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (voiceState !== 'idle') return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Microphone access is not supported by your browser.');
      return;
    }

    voiceSessionTokenRef.current += 1;
    const sessionToken = voiceSessionTokenRef.current;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // If user cancelled, switched session, or logged out while getUserMedia was resolving
      if (voiceSessionTokenRef.current !== sessionToken) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current = stream;
      audioChunksRef.current = [];

      let mimeType = '';
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported) {
        for (const mt of ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', '']) {
          if (!mt || MediaRecorder.isTypeSupported(mt)) {
            mimeType = mt;
            break;
          }
        }
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

      recorder.ondataavailable = (e) => {
        if (voiceSessionTokenRef.current !== sessionToken) return;
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        const duration = elapsedRef.current;
        setRecordingTime(0);

        // Check if recording was cancelled or cleaned up
        if (voiceSessionTokenRef.current !== sessionToken) {
          audioChunksRef.current = [];
          setVoiceState('idle');
          return;
        }

        if (duration < 1) {
          audioChunksRef.current = [];
          setVoiceState('idle');
          return;
        }

        const mime = recorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mime });
        audioChunksRef.current = [];

        if (blob.size < 500) {
          setVoiceState('idle');
          return;
        }

        let ext = '.webm';
        if (mime.includes('ogg')) ext = '.ogg';
        else if (mime.includes('mp4') || mime.includes('m4a')) ext = '.m4a';
        else if (mime.includes('mpeg') || mime.includes('mp3')) ext = '.mp3';
        else if (mime.includes('wav')) ext = '.wav';

        await transcribeAudio(blob, ext, sessionToken);
      };

      recorder.onerror = () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setVoiceState('idle');
        setRecordingTime(0);
      };

      mediaRecorderRef.current = recorder;
      recorder.start(1000);
      setVoiceState('recording');
      setRecordingTime(0);
      elapsedRef.current = 0;

      timerRef.current = setInterval(() => {
        elapsedRef.current += 1;
        setRecordingTime(elapsedRef.current);
      }, 1000);
    } catch (err) {
      setVoiceState('idle');
      if (err.name === 'NotAllowedError') {
        alert('Microphone access denied. Please allow microphone permission and try again.');
      } else if (err.name === 'NotFoundError') {
        alert('No microphone found. Please connect a microphone.');
      } else {
        alert('Microphone error: ' + err.message);
      }
    }
  }, [voiceState, transcribeAudio]);

  const handleMicClick = useCallback(() => {
    if (voiceState === 'recording') {
      stopRecording();
    } else if (voiceState === 'idle') {
      startRecording();
    } else if (voiceState === 'transcribing') {
      cleanupVoiceResources();
    }
  }, [voiceState, startRecording, stopRecording, cleanupVoiceResources]);

  const formatTimer = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  const placeholderText =
    voiceState === 'transcribing'
      ? 'Transcribing your audio input...'
      : voiceState === 'recording'
      ? `Recording in progress (${formatTimer(recordingTime)}) — click microphone to complete`
      : 'Describe your symptoms or ask a medical question…';

  return (
    <footer className="composer-container">
      <div className="composer-frame">
        <div className={`composer-card ${voiceState === 'recording' ? 'is-recording' : ''}`}>
          {/* Medical Image Attachment */}
          <label
            className="composer-action-btn attach-btn"
            title="Upload medical image for analysis (Skin, X-ray, or Retina)"
            aria-label="Upload medical image"
          >
            <i className="fas fa-paperclip" />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={onImageUpload}
            />
          </label>

          {/* Textarea */}
          <textarea
            ref={inputRef}
            className="composer-textarea"
            placeholder={placeholderText}
            rows={1}
            value={inputValue}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            aria-label="Message input"
          />

          {/* Voice Recording Timer */}
          {voiceState === 'recording' && (
            <div className="recording-timer-pill" role="status" aria-label="Recording time">
              <span className="rec-pulse-dot" />
              <span>{formatTimer(recordingTime)}</span>
            </div>
          )}

          {/* Voice Input Button */}
          <button
            type="button"
            className={`composer-action-btn voice-btn ${voiceState !== 'idle' ? 'active' : ''}`}
            title={
              voiceState === 'recording'
                ? 'Stop recording'
                : voiceState === 'transcribing'
                ? 'Transcribing... click to cancel'
                : 'Voice input — click to speak'
            }
            aria-label={
              voiceState === 'recording'
                ? 'Stop voice recording'
                : voiceState === 'transcribing'
                ? 'Cancel transcription'
                : 'Start voice recording'
            }
            onClick={handleMicClick}
          >
            <i
              className={`fas ${
                voiceState === 'recording'
                  ? 'fa-stop'
                  : voiceState === 'transcribing'
                  ? 'fa-spinner fa-spin'
                  : 'fa-microphone'
              }`}
            />
          </button>

          {/* Send Message Button */}
          <button
            type="button"
            className="composer-send-btn"
            title="Send message"
            aria-label="Send message"
            onClick={onSend}
            disabled={!inputValue.trim() || isTyping}
          >
            <i className="fas fa-paper-plane" />
          </button>
        </div>

        {/* Clinical Transparency Footer */}
        <div className="composer-clinical-hint">
          <i className="fas fa-shield-halved" />
          <span>
            AI responses are informational only — always consult a qualified healthcare professional. Call 112 / 911 in emergencies.
          </span>
        </div>
      </div>
    </footer>
  );
}
