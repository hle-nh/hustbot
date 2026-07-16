import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.api.deps import ConversationServiceDep, RAGServiceDep
from app.schemas.chat import ChatRequest, ChatResponse, ConversationOut
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
limiter = Limiter(key_func=get_remote_address)


# ── POST /chat ─────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT)
async def chat(
    request: Request,
    chat_request: ChatRequest,
    rag_service: RAGServiceDep,
) -> ChatResponse:
    """
    Nhận câu hỏi, trả về câu trả lời từ RAG pipeline.

    - Nếu `conversation_id` là null → tạo conversation mới.
    - Lịch sử được load từ PostgreSQL (sliding window).
    - Câu trả lời và context được lưu lại vào DB.
    """
    try:
        response = await rag_service.chat(chat_request)
        return response
    except RuntimeError as e:
        # Model hết quota
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Lỗi xử lý chat: %s", e)
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")


# ── GET /chat/conversations/{id} ───────────────────────────────

@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    conv_service: ConversationServiceDep,
) -> ConversationOut:
    """Lấy toàn bộ lịch sử của một conversation."""
    conv = await conv_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation không tồn tại")
    return ConversationOut.model_validate(conv)


# ── DELETE /chat/conversations/{id} ───────────────────────────

@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    conv_service: ConversationServiceDep,
) -> None:
    """Xóa conversation và toàn bộ messages (cascade)."""
    from app.models.conversation import Conversation

    result = await conv_service.db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation không tồn tại")

    await conv_service.db.delete(conv)
    await conv_service.db.flush()
