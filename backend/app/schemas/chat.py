from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(
        default=None,
        description="UUID của conversation. Nếu None → tạo conversation mới."
    )
    message: str = Field(..., min_length=1, max_length=2000)
    web_search: bool = Field(
        default=False,
        description="Nếu True → bật tìm kiếm Web cho request này, bất kể cấu hình server."
    )
    category: Optional[str] = Field(
        default="all",
        description="Phân loại mục đích tra cứu: 'all' (tất cả), 'academic' (quy chế/học vụ), 'admissions' (tuyển sinh)."
    )


# ── Source citation ─────────────────────────────────────────────

class Source(BaseModel):
    file: str
    page: int | str
    preview: str


# ── Response ────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: list[Source]
    elapsed_seconds: float
    web_search_used: bool = False


# ── Conversation / Message (cho GET endpoints) ──────────────────

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}
