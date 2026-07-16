import { useEffect, useRef } from 'react';
import type { Message } from '../types';
import { useChatStore } from '../store/chatStore';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import WelcomeScreen from './WelcomeScreen';
import hustLogo from '../assets/hust_logo.png';
import './ChatWindow.css';

interface Props {
  messages: Message[];
}

export default function ChatWindow({ messages }: Props) {
  const { isLoading, error } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <section
      className="chat-window"
      aria-label="Cuộc trò chuyện"
      aria-live="polite"
      aria-atomic="false"
    >
      {messages.length === 0 && !isLoading ? (
        <WelcomeScreen />
      ) : (
        <div className="message-list">
          {/* HUST watermark */}
          <div className="chat-watermark" aria-hidden="true">
            <img src={hustLogo} alt="" className="chat-watermark-img" />
          </div>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isLoading && <TypingIndicator />}
          {error && (
            <div className="chat-error" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}
          <div ref={bottomRef} aria-hidden="true" />
        </div>
      )}

    </section>
  );
}
