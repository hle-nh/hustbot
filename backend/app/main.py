"""
HUSTBot FastAPI Application
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes import chat, health
from app.core.config import settings
from app.core.database import engine

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Rate Limiter ────────────────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])

# ── App ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="HUSTBot API",
    description="RAG chatbot tư vấn học vụ Đại học Bách khoa Hà Nội",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS (cho React frontend) ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(chat.router)


# ── Startup: warm up RAG pipeline ──────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 HUSTBot API đang khởi động...")
    logger.info("   Model: %s", settings.GEMINI_MODEL)
    logger.info("   ChromaDB: %s", settings.CHROMA_DIR)
    logger.info("   DB: %s", settings.DATABASE_URL.split("@")[-1])

    logger.info("✅ API sẵn sàng. Retriever sẽ được load lazy ở câu hỏi đầu tiên.")


@app.on_event("shutdown")
async def shutdown_event():
    await engine.dispose()
    logger.info("👋 HUSTBot API đã tắt.")


# ── Run directly ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
