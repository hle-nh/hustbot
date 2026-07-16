import type { Conversation } from '../types';
import { useChatStore } from '../store/chatStore';
import type { Category } from '../types';
import hustLogo from '../assets/hust_logo.png';
import './Topbar.css';

interface Props {
  conversation?: Conversation;
}

const CATEGORY_OPTIONS: { value: Category; label: string; icon: string }[] = [
  { value: 'all',        label: 'Tất cả',        icon: '🔍' },
  { value: 'academic',   label: 'Học vụ',         icon: '🎓' },
  { value: 'admissions', label: 'Tuyển sinh',     icon: '🎯' },
];

export default function Topbar({ conversation }: Props) {
  const { deleteConversation, newConversation, setConversationCategory } = useChatStore();
  const currentCategory = conversation?.category ?? 'all';

  const handleCategoryChange = (value: Category) => {
    if (conversation) {
      setConversationCategory(conversation.id, value);
    }
  };

  return (
    <header className="topbar" role="banner">
      <div className="topbar-left">
        {/* HUST Branding */}
        <div className="topbar-brand">
          <img
            src={hustLogo}
            alt="Logo HUST"
            className="topbar-brand-logo"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
          <span className="topbar-brand-name">BKHN</span>
          <div className="topbar-brand-divider" />
        </div>

        {conversation ? (
          <>
            <div className="topbar-status" aria-hidden="true" />
            <h1 className="topbar-title" id="conversation-title">
              {conversation.title}
            </h1>
          </>
        ) : (
          <h1 className="topbar-title topbar-title--empty" id="conversation-title">
            HUSTBot — Trợ lý học vụ
          </h1>
        )}
      </div>

      <div className="topbar-right">
        {/* Category selector (shown when there's an active conversation) */}
        {conversation && (
          <div className="topbar-category" role="group" aria-label="Chọn danh mục tra cứu">
            {CATEGORY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                id={`topbar-cat-${opt.value}`}
                className={`topbar-cat-btn${currentCategory === opt.value ? ' topbar-cat-btn--active' : ''}`}
                onClick={() => handleCategoryChange(opt.value)}
                title={opt.label}
                aria-pressed={currentCategory === opt.value}
              >
                <span>{opt.icon}</span>
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        )}

        <button
          id="topbar-new-chat"
          className="topbar-btn topbar-btn--primary"
          onClick={() => newConversation()}
          aria-label="Tạo cuộc trò chuyện mới"
          title="Cuộc trò chuyện mới"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          <span>Mới</span>
        </button>

        {conversation && (
          <button
            id="topbar-delete-conv"
            className="topbar-btn topbar-btn--danger"
            onClick={() => deleteConversation(conversation.id)}
            aria-label="Xóa cuộc trò chuyện này"
            title="Xóa cuộc trò chuyện"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
            </svg>
            <span>Xóa</span>
          </button>
        )}
      </div>
    </header>
  );
}
