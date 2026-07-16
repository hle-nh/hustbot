import './TypingIndicator.css';

export default function TypingIndicator() {
  return (
    <div className="typing-row" aria-label="HUSTBot đang soạn câu trả lời" role="status">
      <div className="typing-avatar" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="8" r="5" />
          <path d="M3 21v-2a7 7 0 0 1 14 0v2" />
        </svg>
      </div>
      <div className="typing-bubble">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}
