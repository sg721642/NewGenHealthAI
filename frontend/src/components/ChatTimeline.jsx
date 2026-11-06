import MessageBubble from './MessageBubble';
import WelcomeScreen from './WelcomeScreen';

export default function ChatTimeline({
  messages,
  isTyping,
  showWelcome,
  onQuickQuestion,
  onFollowUpClick,
  onTriggerImageUpload,
  onTriggerVoiceInput,
  chatAreaRef,
}) {
  return (
    <div className="chat-timeline" ref={chatAreaRef}>
      {showWelcome && messages.length === 0 ? (
        <WelcomeScreen
          onQuickQuestion={onQuickQuestion}
          onTriggerImageUpload={onTriggerImageUpload}
          onTriggerVoiceInput={onTriggerVoiceInput}
        />
      ) : (
        <div className="messages-stream">
          {messages.map((msg, index) => (
            <MessageBubble
              key={`${index}-${msg.timestamp || ''}`}
              msg={msg}
              onFollowUpClick={onFollowUpClick}
            />
          ))}

          {/* Typing Indicator */}
          {isTyping && (
            <div className="message-wrapper message-assistant typing-active">
              <div className="message-avatar-wrap" aria-hidden="true">
                <div className="message-avatar assistant">
                  <i className="fas fa-heart-pulse" />
                </div>
              </div>
              <div className="message-content-group">
                <div className="bubble bubble-assistant typing-bubble">
                  <div className="typing-indicator-row">
                    <span className="typing-label">Analyzing health query</span>
                    <div className="typing-dots" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
