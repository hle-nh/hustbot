from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.rag.generator import get_model_manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    """Kiểm tra server còn sống không."""
    return JSONResponse({"status": "ok"})


@router.get("/health/detailed")
async def health_detailed() -> JSONResponse:
    """Kiểm tra trạng thái chi tiết: DB, retriever, model quota."""
    manager = get_model_manager()
    model_status = manager.status()

    # Kiểm tra retriever đã load chưa
    from app.rag.retriever import _retriever_instance
    retriever_ready = _retriever_instance is not None

    return JSONResponse({
        "status": "ok",
        "retriever_loaded": retriever_ready,
        "model": model_status,
    })
