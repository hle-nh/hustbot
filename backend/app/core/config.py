from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Thư mục gốc của backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Google Gemini ──────────────────────────────────────────
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.0

    # ── Multi-provider LLM ─────────────────────────────────────
    LLM_PROVIDER: str = "google"
    LLM_MODEL: str = "gemini-2.5-flash"
    ENABLE_WEB_SEARCH: bool = False
    WEB_SEARCH_THRESHOLD: float = 0.38

    OPENAI_API_KEY: str | None = None

    # ── PostgreSQL ────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://hustbot:hustbot@localhost:5432/hustbot_db"
    )

    # ── RAG ───────────────────────────────────────────────────
    CHROMA_DIR: str = str(BASE_DIR.parent / "chroma_db")
    DATA_DIR: str = str(BASE_DIR.parent / "data")
    RETRIEVER_K: int = 6
    DEVICE: str = "cpu"
    # Ngưỡng điểm reranker (normalized 0-1): loại chunk nhiễu trước khi đưa vào LLM.
    # MẶC ĐỊNH 0.0 = TẮT (giữ recall tối đa). Local retrieval eval cho thấy ngưỡng > 0
    # làm rớt câu hỏi đa phần (vd BM_066) vì chunk đáp án có điểm rerank thấp.
    # Chỉ bật (vd 0.1-0.2) khi đã đo được Answer Relevancy tăng qua RAGAS.
    RERANK_SCORE_THRESHOLD: float = 0.0
    RERANK_MIN_KEEP: int = 4

    # ── Rate Limiting ─────────────────────────────────────────
    RATE_LIMIT: str = "20/minute"  # Có thể set trong .env: RATE_LIMIT=10/minute

    # ── Memory ────────────────────────────────────────────────
    SLIDING_WINDOW_SIZE: int = 8  # số messages gần nhất đưa vào LLM

    # ── LLM Output ───────────────────────────────────────────
    MAX_OUTPUT_TOKENS: int = 2048

    # ── Model fallback priority ───────────────────────────────
    @property
    def model_priority(self) -> list[str]:
        return list(dict.fromkeys([
            self.GEMINI_MODEL,
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
        ]))


settings = Settings()
