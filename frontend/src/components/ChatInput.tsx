import { useState, useRef, type KeyboardEvent } from 'react';
import { useChatStore } from '../store/chatStore';
import './ChatInput.css';

export default function ChatInput() {
  const [text, setText] = useState('');
  const { sendMessage, isLoading, activeConversationId, newConversation, webSearchEnabled, toggleWebSearch } = useChatStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = text.trim().length > 0 && !isLoading;

  const handleSend = async () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    if (!activeConversationId) newConversation();

    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    await sendMessage(trimmed);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  };

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-box">
        <textarea
          id="chat-textarea"
          ref={textareaRef}
          className="chat-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Hỏi về quy chế, học phí, tuyển sinh... (Enter để gửi)"
          rows={1}
          maxLength={2000}
          disabled={isLoading}
          aria-label="Nhập câu hỏi"
          aria-multiline="true"
        />

        <button
          id="web-search-btn"
          className={`web-search-btn ${webSearchEnabled ? 'web-search-btn--active' : ''}`}
          onClick={toggleWebSearch}
          disabled={isLoading}
          aria-label={webSearchEnabled ? 'Tắt tìm kiếm Web' : 'Bật tìm kiếm Web'}
          title={webSearchEnabled ? 'Tắt tìm kiếm Web' : 'Bật tìm kiếm Web (dùng khi câu hỏi ngoài quy chế HUST)'}
          type="button"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
          <span>Web</span>
        </button>

        <button
          id="send-btn"
          className={`send-btn ${canSend ? 'send-btn--active' : ''}`}
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Gửi tin nhắn"
          title="Gửi (Enter)"
        >
          {isLoading ? (
            <span className="send-spinner" aria-hidden="true" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
      <p className="chat-input-hint">
        Shift + Enter để xuống dòng &nbsp;·&nbsp; {text.length}/2000
      </p>
    </div>
  );
}
