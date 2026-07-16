"""
RAGService — orchestrator kết hợp ConversationService + RAG pipeline.

Flow:
  1. Load conversation từ PostgreSQL
  2. Get recent messages (sliding window)
  3. Format history text
  4. Retrieve docs
  5. Build prompt inputs
  6. Generate answer
  7. Save user message + assistant message
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.rag.generator import get_model_manager
from app.rag.prompt_builder import build_prompt_inputs, format_context
from app.rag.retriever import retrieve
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

# Cache lưu trữ tối đa 500 câu hỏi trong 1 giờ (giảm chi phí gọi API và Reranker)
_query_cache = TTLCache(maxsize=500, ttl=3600)


class RAGService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conversation_svc = ConversationService(db)
        self.model_manager = get_model_manager()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()

        # ── 1. Get or create conversation ────────────────────────
        conv = await self.conversation_svc.get_or_create_conversation(
            request.conversation_id
        )

        # ── 2. Load lịch sử (sliding window) ────────────────────
        recent_messages = await self.conversation_svc.get_recent_messages(
            conv.id
        )
        history_text = ConversationService.format_history_for_prompt(
            recent_messages
        )

        # ── 3. Check Cache ──────────────────────────────────────────────────
        cache_key = (request.message.strip().lower(), history_text)
        cached_result = _query_cache.get(cache_key)

        if cached_result:
            logger.info("Cache HIT for question: %s", request.message)
            docs = cached_result["docs"]
            web_search_used = cached_result["web_search_used"]
            google_sources = cached_result["google_sources"]
            answer = cached_result["answer"]
        else:
            # ── 4. Retrieve docs ─────────────────────────────────────────────────
            docs, web_search_used = retrieve(
                request.message,
                use_reranker=True,
                web_search_override=True if request.web_search else None,
                category=request.category or "all",
            )
            context = format_context(docs)

            # ── 5. Build prompt & generate ────────────────────────────
            prompt_inputs = build_prompt_inputs(
                question=request.message,
                context=context,
                history=history_text,
            )

            logger.info(
                "chat conv=%s model=%s docs=%d",
                conv.id, self.model_manager.current_model, len(docs),
            )

            answer, google_sources = self.model_manager.generate(
                prompt_inputs, use_web_search=web_search_used
            )

            # Save to cache
            _query_cache[cache_key] = {
                "docs": docs,
                "web_search_used": web_search_used,
                "google_sources": google_sources,
                "answer": answer,
            }

        elapsed = time.perf_counter() - t0
        logger.info("chat done in %.2fs", elapsed)

        # ── 6. Save messages vào PostgreSQL ──────────────────────
        await self.conversation_svc.add_user_message(conv.id, request.message)

        # Lưu nguồn vào PostgreSQL
        db_sources = []
        if web_search_used and google_sources:
            db_sources = [
                {
                    "file": src.get("title", "Google Search"),
                    "page": "Web Result",
                }
                for src in google_sources
            ]
        else:
            db_sources = [
                {
                    "file": d.metadata.get("source", ""),
                    "page": d.metadata.get("page", "?"),
                }
                for d in docs
            ]

        await self.conversation_svc.add_assistant_message(
            conv.id,
            answer,
            retrieved_context={
                "docs_count": len(google_sources) if web_search_used else len(docs),
                "sources": db_sources,
            },
        )

        # Auto-set conversation title từ câu hỏi đầu tiên
        if not recent_messages:
            await self.conversation_svc.maybe_set_title(conv.id, request.message)

        # ── 7. Build response ─────────────────────────────────────
        if web_search_used and google_sources:
            sources = [
                Source(
                    file=src.get("title", "Google Search"),
                    page="Web Result",
                    preview=f"Link: {src.get('uri', '')}",
                )
                for src in google_sources
            ]
        else:
            sources = [
                Source(
                    file=doc.metadata.get("source", "unknown"),
                    page=doc.metadata.get("page", "?"),
                    preview=doc.page_content[:150] + "...",
                )
                for doc in docs
            ]

        return ChatResponse(
            conversation_id=conv.id,
            answer=answer,
            sources=sources,
            elapsed_seconds=round(elapsed, 2),
            web_search_used=web_search_used,
        )
