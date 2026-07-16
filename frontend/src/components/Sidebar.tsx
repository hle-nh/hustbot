import { useChatStore } from '../store/chatStore';
import ConversationItem from './ConversationItem';
import hustLogo from '../assets/hust_logo.png';
import './Sidebar.css';

export default function Sidebar() {
  const { conversations, activeConversationId, newConversation, selectConversation, deleteConversation } =
    useChatStore();

  return (
    <aside className="sidebar" aria-label="Danh sách cuộc trò chuyện">
      {/* Header / Logo */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-badge">
            <img
              src={hustLogo}
              alt="Logo HUST"
              className="sidebar-logo-img"
              onError={(e) => {
                const target = e.currentTarget;
                target.style.display = 'none';
                const parent = target.parentElement;
                if (parent) {
                  parent.innerHTML = '<span class="sidebar-logo-fallback">BK</span>';
                }
              }}
            />
          </div>
          <div className="sidebar-logo-text">
            <span className="sidebar-logo-title">HUSTBot</span>
            <span className="sidebar-logo-sub">Trợ lý học vụ BKHN</span>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="sidebar-actions">
        <button
          id="new-chat-btn"
          className="new-chat-btn"
          onClick={() => newConversation()}
          aria-label="Tạo cuộc trò chuyện mới"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Cuộc trò chuyện mới
        </button>
      </div>

      {/* Conversations list */}
      <nav className="sidebar-nav">
        {conversations.length === 0 ? (
          <div className="sidebar-empty">
            <p>Chưa có cuộc trò chuyện nào.</p>
            <p>Nhấn nút ở trên để bắt đầu!</p>
          </div>
        ) : (
          <ul className="conv-list" role="list">
            {conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isActive={conv.id === activeConversationId}
                onSelect={() => selectConversation(conv.id)}
                onDelete={() => deleteConversation(conv.id)}
              />
            ))}
          </ul>
        )}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-footer-info">
          <div className="sidebar-footer-dot" />
          <span>Đại học Bách khoa Hà Nội</span>
        </div>
        <span className="sidebar-footer-version">v2.0</span>
      </div>
    </aside>
  );
}
