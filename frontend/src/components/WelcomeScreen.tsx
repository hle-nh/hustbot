import { useState } from 'react';
import { useChatStore } from '../store/chatStore';
import type { Category } from '../types';
import hustLogo from '../assets/hust_logo.png';
import './WelcomeScreen.css';

interface CategoryOption {
  value: Category;
  icon: string;
  label: string;
  sublabel: string;
  color: string;
  suggestions: string[];
}

const CATEGORIES: CategoryOption[] = [
  {
    value: 'academic',
    icon: '🎓',
    label: 'Quy chế & Học vụ',
    sublabel: 'Dành cho sinh viên BKHN',
    color: 'academic',
    suggestions: [
      'Điều kiện tốt nghiệp là gì?',
      'Quy định chuẩn ngoại ngữ đầu ra K70?',
      'Học phí học kỳ 2025-2026 là bao nhiêu?',
      'Bị cảnh cáo học vụ thì xử lý thế nào?',
    ],
  },
  {
    value: 'admissions',
    icon: '🎯',
    label: 'Tuyển sinh',
    sublabel: 'Học sinh THPT & Phụ huynh',
    color: 'admissions',
    suggestions: [
      'Điểm chuẩn xét tuyển năm 2025?',
      'Phương thức xét tuyển tài năng là gì?',
      'Ngành nào điểm chuẩn cao nhất?',
      'Thủ tục đăng ký xét tuyển như thế nào?',
    ],
  },
  {
    value: 'all',
    icon: '🔍',
    label: 'Tra cứu tổng hợp',
    sublabel: 'Tìm kiếm toàn bộ tài liệu',
    color: 'all',
    suggestions: [
      'Quy chế đào tạo đại học của BKHN?',
      'Học phí học kỳ 2025-2026 là bao nhiêu?',
      'Điều kiện tốt nghiệp là gì?',
      'Điểm chuẩn xét tuyển năm 2025?',
    ],
  },
];

export default function WelcomeScreen() {
  const { sendMessage, newConversation, activeConversationId, setConversationCategory, activeConversation } =
    useChatStore();

  const conv = activeConversation();
  const [selected, setSelected] = useState<Category>(conv?.category ?? 'all');

  const currentSuggestions = CATEGORIES.find((c) => c.value === selected)?.suggestions ?? CATEGORIES[2].suggestions;

  const handleSelectCategory = (cat: Category) => {
    setSelected(cat);
    // Apply to the active conversation (or new one if none)
    let convId = activeConversationId;
    if (!convId) {
      convId = newConversation();
    }
    setConversationCategory(convId, cat);
  };

  const handleSuggestion = async (text: string) => {
    if (!activeConversationId) newConversation();
    await sendMessage(text);
  };

  return (
    <div className="welcome-screen">
      {/* Hero */}
      <div className="welcome-hero">
        <div className="welcome-logo-wrap">
          <img
            src={hustLogo}
            alt="Logo Đại học Bách khoa Hà Nội"
            className="welcome-logo"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        </div>
        <h2 className="welcome-title">Xin chào! Tôi là HUSTBot</h2>
        <p className="welcome-sub">
          Trợ lý thông minh của <strong>Đại học Bách khoa Hà Nội</strong>.<br />
          Chọn mục đích tra cứu để tôi có thể trả lời chính xác hơn.
        </p>
      </div>

      {/* Category cards */}
      <div className="welcome-categories" role="group" aria-label="Chọn mục đích tra cứu">
        <p className="welcome-categories-label">Bạn muốn tìm hiểu về:</p>
        <div className="welcome-cards">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              id={`welcome-cat-${cat.value}`}
              className={`welcome-card welcome-card--${cat.color}${selected === cat.value ? ' welcome-card--active' : ''}`}
              onClick={() => handleSelectCategory(cat.value)}
              aria-pressed={selected === cat.value}
            >
              <span className="welcome-card-icon">{cat.icon}</span>
              <span className="welcome-card-label">{cat.label}</span>
              <span className="welcome-card-sub">{cat.sublabel}</span>
              {selected === cat.value && (
                <span className="welcome-card-check" aria-hidden="true">✓</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Suggestion chips */}
      <div className="welcome-suggestions" aria-label="Câu hỏi gợi ý">
        <p className="welcome-suggestions-label">Bạn có thể hỏi:</p>
        <div className="welcome-chips">
          {currentSuggestions.map((s) => (
            <button
              key={s}
              id={`suggestion-${s.slice(0, 20).replace(/\s/g, '-')}`}
              className="welcome-chip"
              onClick={() => handleSuggestion(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
