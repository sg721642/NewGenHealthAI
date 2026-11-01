import { useState, useRef, useCallback, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { formatMessageTimestamp } from '../utils/formatters';

export default function MessageBubble({ msg, onFollowUpClick }) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [copied, setCopied] = useState(false);
  const audioRef = useRef(null);
  const blobUrlRef = useRef(null);
  const ttsAbortRef = useRef(null);

  const copyText = useCallback(() => {
    if (!msg.content) return;
    navigator.clipboard.writeText(msg.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }, [msg.content]);

  // TTS Voice Synthesis
  const speakMessage = useCallback(async () => {
    // If speaking, stop and abort
    if (isSpeaking) {
      if (ttsAbortRef.current) {
        ttsAbortRef.current.abort();
        ttsAbortRef.current = null;
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      setIsSpeaking(false);
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
      return;
    }

    try {
      setIsSpeaking(true);
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }

      const token = localStorage.getItem('auth_token');
      const abortCtrl = new AbortController();
      ttsAbortRef.current = abortCtrl;

      const res = await fetch('/api/v1/voice/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text: (msg.content || '').substring(0, 2000) }),
        signal: abortCtrl.signal,
      });

      if (!res.ok) throw new Error(`TTS failed with status: ${res.status}`);

      const audioBlob = await res.blob();
      const blobUrl = URL.createObjectURL(audioBlob);
      blobUrlRef.current = blobUrl;

      const audio = new Audio(blobUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setIsSpeaking(false);
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current);
          blobUrlRef.current = null;
        }
      };

      audio.onerror = () => {
        setIsSpeaking(false);
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current);
          blobUrlRef.current = null;
        }
      };

      await audio.play();
    } catch {
      // Clean up on TTS error or cancellation without leaking error objects to console
      setIsSpeaking(false);
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    } finally {
      ttsAbortRef.current = null;
    }
  }, [msg.content, isSpeaking]);

  // Clean up audio on unmount
  useEffect(() => {
    return () => {
      if (ttsAbortRef.current) {
        ttsAbortRef.current.abort();
        ttsAbortRef.current = null;
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, []);

  if (msg.type === 'user') {
    return (
      <div className="message-wrapper message-user">
        <div className="message-avatar-wrap" aria-hidden="true">
          <div className="message-avatar user">
            <i className="fas fa-user" />
          </div>
        </div>

        <div className="message-content-group">
          <div className="bubble bubble-user">
            {msg.image && (
              <div className="user-attached-image-wrap">
                <img
                  src={msg.image}
                  alt="Uploaded medical sample"
                  className="user-attached-image"
                />
              </div>
            )}
            <div className="user-message-text">{msg.content}</div>
          </div>

          <div className="message-metadata">
            <span className="message-timestamp">{msg.timestamp}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-wrapper message-assistant">
      <div className="message-avatar-wrap" aria-hidden="true">
        <div className="message-avatar assistant">
          <i className="fas fa-heart-pulse" />
        </div>
      </div>

      <div className="message-content-group">
        <div className="bubble bubble-assistant">
          <div className="markdown-prose">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>

          {/* Follow-up question chips */}
          {msg.followUp && msg.followUp.questions && msg.followUp.questions.length > 0 && (
            <div className="followup-intake-card">
              <div className="followup-intake-header">
                <i className="fas fa-clipboard-question" aria-hidden="true" />
                <span>Health intake follow-up questions</span>
              </div>

              {msg.followUp.questions.map((q, qIdx) => (
                <div key={qIdx} className="followup-question-item">
                  <p className="followup-question-text">{q.text}</p>
                  <div className="followup-options-grid" role="group" aria-label="Suggested follow-up responses">
                    {(q.options || []).map((opt, oIdx) => (
                      <button
                        key={oIdx}
                        type="button"
                        className="followup-choice-chip"
                        onClick={() => onFollowUpClick && onFollowUpClick(opt)}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              <div className="followup-round-indicator">
                <i className="fas fa-shield-halved" />
                <span>Round {msg.followUp.triage_round} of {msg.followUp.max_rounds} · Educational Triage</span>
              </div>
            </div>
          )}
        </div>

        {/* Message Footer Actions */}
        <div className="message-metadata">
          <div className="metadata-left">
            <span className="message-timestamp">{formatMessageTimestamp(msg.timestamp)}</span>
            {msg.source && (
              <span className="metadata-source-pill" title={`Clinical source: ${msg.source}`}>
                <i className="fas fa-database" />
                <span>{msg.source}</span>
              </span>
            )}
          </div>

          <div className="metadata-actions">
            <button
              type="button"
              className={`action-pill-btn ${isSpeaking ? 'active' : ''}`}
              onClick={speakMessage}
              title={isSpeaking ? 'Stop speaking' : 'Listen to response'}
              aria-label={isSpeaking ? 'Stop speaking' : 'Listen to response'}
            >
              <i className={`fas ${isSpeaking ? 'fa-volume-xmark' : 'fa-volume-high'}`} />
              <span>{isSpeaking ? 'Stop' : 'Listen'}</span>
            </button>

            <button
              type="button"
              className="action-pill-btn"
              onClick={copyText}
              title="Copy response text"
              aria-label="Copy response text"
            >
              <i className={`fas ${copied ? 'fa-check' : 'fa-copy'}`} />
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
