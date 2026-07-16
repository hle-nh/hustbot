import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../types';
import SourceCard from './SourceCard';
import './MessageBubble.css';

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`msg-row ${isUser ? 'msg-row--user' : 'msg-row--bot'}`}>
      {/* Avatar */}
      {!isUser && (
        <div className="msg-avatar msg-avatar--bot" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="8" r="5" />
            <path d="M3 21v-2a7 7 0 0 1 14 0v2" />
          </svg>
        </div>
      )}

      <div className="msg-content">
        {/* Bubble */}
        <div className={`msg-bubble ${isUser ? 'msg-bubble--user' : 'msg-bubble--bot'}`}>
          {isUser ? (
            <p className="msg-text">{message.content}</p>
          ) : (
            <div className="msg-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="msg-sources">
            <p className="msg-sources-label">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              Nguồn tham khảo
            </p>
            <div className="msg-sources-grid">
              {message.sources.map((src, i) => (
                <SourceCard key={i} source={src} index={i + 1} />
              ))}
            </div>
          </div>
        )}

        {/* Web Search badge */}
        {!isUser && message.web_search_used && (
          <div className="msg-web-badge" role="note" aria-label="Kết quả từ tìm kiếm Web">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            Kết quả từ tìm kiếm Web
          </div>
        )}

        {/* Elapsed time */}
        {!isUser && message.elapsed_seconds !== undefined && (
          <p className="msg-meta">
            ⏱ {message.elapsed_seconds.toFixed(1)}s
          </p>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="msg-avatar msg-avatar--user" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
      )}
    </div>
  );
}
