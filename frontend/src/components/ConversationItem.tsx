import { useState } from 'react';
import type { Conversation } from '../types';
import './ConversationItem.css';

interface Props {
  conversation: Conversation;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

const CATEGORY_ICON: Record<string, string> = {
  academic: '🎓',
  admissions: '🎯',
  all: '💬',
};

export default function ConversationItem({ conversation, isActive, onSelect, onDelete }: Props) {
  const [showDelete, setShowDelete] = useState(false);
  const categoryIcon = CATEGORY_ICON[conversation.category ?? 'all'];

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete();
  };

  return (
    <li
      className={`conv-item${isActive ? ' conv-item--active' : ''}`}
      onMouseEnter={() => setShowDelete(true)}
      onMouseLeave={() => setShowDelete(false)}
      role="listitem"
    >
      <button
        id={`conv-${conversation.id}`}
        className="conv-item-btn"
        onClick={onSelect}
        aria-current={isActive ? 'page' : undefined}
        aria-label={`Chọn cuộc trò chuyện: ${conversation.title}`}
      >
        <span className="conv-cat-icon" title={`Danh mục: ${conversation.category ?? 'all'}`}>
          {categoryIcon}
        </span>
        <span className="conv-title">{conversation.title}</span>
      </button>

      {(showDelete || isActive) && (
        <button
          className="conv-delete-btn"
          onClick={handleDelete}
          aria-label="Xóa cuộc trò chuyện"
          title="Xóa"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
          </svg>
        </button>
      )}
    </li>
  );
}
