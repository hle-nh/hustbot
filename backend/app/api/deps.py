"""FastAPI dependency injection."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService

# Type aliases cho dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_conversation_service(db: DbSession) -> ConversationService:
    return ConversationService(db)


def get_rag_service(db: DbSession) -> RAGService:
    return RAGService(db)


ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]
RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]
