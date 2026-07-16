"""
ConversationService — thay thế self.history = [] trong RAGChat cũ.

Toàn bộ lịch sử hội thoại được lưu vào PostgreSQL.
Sliding window: chỉ load SLIDING_WINDOW_SIZE messages gần nhất để đưa vào LLM.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.message import Message

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Conversation CRUD ──────────────────────────────────────────

    async def get_or_create_conversation(
        self, conversation_id: str | None
    ) -> Conversation:
        """Lấy conversation hiện có hoặc tạo mới nếu conversation_id=None."""
        if conversation_id:
            result = await self.db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv
            logger.warning("conversation_id=%s không tồn tại → tạo mới", conversation_id)

        conv = Conversation()
        self.db.add(conv)
        await self.db.flush()  # flush để lấy id trước khi commit
        logger.info("Tạo conversation mới: id=%s", conv.id)
        return conv

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    # ── Message CRUD ──────────────────────────────────────────────

    async def get_recent_messages(self, conversation_id: str) -> list[Message]:
        """
        Sliding window: lấy SLIDING_WINDOW_SIZE messages gần nhất.

        Thay thế: self.history[-2:] trong RAGChat cũ
        Cải tiến: kích thước window cấu hình được qua .env
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(settings.SLIDING_WINDOW_SIZE)
        )
        messages = result.scalars().all()
        # Đảo lại để thứ tự cũ → mới
        return list(reversed(messages))

    async def add_user_message(
        self, conversation_id: str, content: str
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        retrieved_context: "dict[str, Any] | None" = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            retrieved_context=retrieved_context,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    # ── Auto-title ────────────────────────────────────────────────

    async def maybe_set_title(
        self, conversation_id: str, first_question: str
    ) -> None:
        """Đặt title cho conversation từ câu hỏi đầu tiên (truncated)."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv and not conv.title:
            conv.title = first_question[:80]
            await self.db.flush()

    # ── Format history cho LLM ────────────────────────────────────

    @staticmethod
    def format_history_for_prompt(messages: list[Message]) -> str:
        """
        Chuyển list Message thành chuỗi lịch sử để đưa vào system prompt.

        Ví dụ output:
          Sinh viên: Điều kiện tốt nghiệp là gì?
          Trợ lý: Theo quy định HUST...
        """
        if not messages:
            return ""

        lines = []
        for msg in messages:
            speaker = "Sinh viên" if msg.role == "user" else "Trợ lý"
            lines.append(f"{speaker}: {msg.content}")

        return "\n".join(lines)
