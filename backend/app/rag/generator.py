"""
Generator module — tách từ src/chain.py.

Thay đổi chính:
- max_output_tokens tăng lên 2048 (cũ: 1000)
- ModelManager giữ nguyên logic fallback quota
- Sử dụng settings từ config thay vì hardcode
"""
from __future__ import annotations

import logging
import re
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.rag.prompt_builder import PROMPT

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Quản lý LLM calls với auto-fallback khi hết quota.

    Logic:
    - Lỗi quota NGÀY (PerDay) → đánh dấu model đã hết, chuyển model khác
    - Lỗi quota PHÚT (rate limit) → chờ rồi retry trên model hiện tại
    - Hết tất cả model → raise RuntimeError rõ ràng
    """

    def __init__(self) -> None:
        self.api_key = settings.GOOGLE_API_KEY
        self.models = settings.model_priority.copy()
        self.current_index = 0
        self.exhausted: set[str] = set()

    @property
    def current_model(self) -> str:
        if settings.LLM_PROVIDER.lower() != "google":
            return settings.LLM_MODEL
        return self.models[self.current_index]

    def _build_llm(self, model_name: str) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.api_key,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,  # FIX: 2048 thay vì 1000
        )

    def _build_openai_llm(self, model_name: str):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Vui lòng cài đặt langchain-openai: pip install langchain-openai")
        if not settings.OPENAI_API_KEY:
            raise ValueError("Vui lòng cấu hình OPENAI_API_KEY trong file .env")
        return ChatOpenAI(
            model=model_name,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=settings.GEMINI_TEMPERATURE,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )

    def generate(self, prompt_inputs: dict, use_web_search: bool = False) -> tuple[str, list[dict]]:
        """
        Invoke LLM với auto-fallback.
        prompt_inputs: dict với keys {question, context, history}
        use_web_search: Nếu True -> Bật tính năng Google Search grounding cho Gemini
        """
        # Nếu dùng Web Search Grounding, thay đổi prompt system để cho phép dùng kết quả search
        if use_web_search and settings.LLM_PROVIDER.lower() == "google":
            from app.rag.prompt_builder import SYSTEM_PROMPT, HUMAN_PROMPT
            from langchain_core.prompts import ChatPromptTemplate

            web_system_prompt = SYSTEM_PROMPT.replace(
                "Chỉ trả lời dựa trên thông tin trong phần [TÀI LIỆU] bên dưới.",
                "Sử dụng công cụ tìm kiếm Google Search để tìm kiếm và trả lời các thông tin chính xác về HUST (bao gồm điểm chuẩn, học phí, thủ tục tuyển sinh năm 2025, 2024, v.v.)."
            ).replace(
                "Chỉ dùng câu này khi đã đọc kỹ tất cả đoạn tài liệu và thực sự không tìm thấy:\n     \"Tôi không tìm thấy thông tin này trong tài liệu hiện có.\"",
                "Trả lời dựa trên kết quả tìm kiếm Google Search được cung cấp."
            )

            web_prompt = ChatPromptTemplate.from_messages([
                ("system", web_system_prompt),
                ("human",  HUMAN_PROMPT),
            ])
        else:
            from app.rag.prompt_builder import PROMPT as web_prompt

        provider = settings.LLM_PROVIDER.lower()
        if provider == "openai":
            llm = self._build_openai_llm(settings.LLM_MODEL)
            chain = web_prompt | llm | StrOutputParser()
            return chain.invoke(prompt_inputs), []

        # Mặc định: Google (Gemini) với fallback vòng tròn giữa các model Gemini
        for i, model_name in enumerate(self.models):
            if model_name in self.exhausted:
                continue

            try:
                llm = self._build_llm(model_name)

                # Bật công cụ Google Search Grounding nếu được yêu cầu
                if use_web_search:
                    llm = llm.bind(tools=[{"google_search": {}}])

                # Không sử dụng StrOutputParser khi dùng tools để có thể trích xuất metadata response
                chain = web_prompt | llm

                if i != self.current_index:
                    logger.info("Chuyển sang model: %s", model_name)
                    self.current_index = i

                response = chain.invoke(prompt_inputs)

                # Trích xuất content dạng text và metadata
                answer = response.content if hasattr(response, 'content') else str(response)

                google_sources = []
                if hasattr(response, 'response_metadata'):
                    meta = response.response_metadata
                    grounding_meta = meta.get("grounding_metadata", {})
                    if "grounding_chunks" in grounding_meta:
                        for chunk in grounding_meta["grounding_chunks"]:
                            web = chunk.get("web", {})
                            if web:
                                google_sources.append({
                                    "title": web.get("title", "Google Search"),
                                    "uri": web.get("uri", "")
                                })

                return answer, google_sources

            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    is_daily = any(
                        kw in err
                        for kw in ["PerDay", "per_day", "PerDayPer", "quotaValue"]
                    )
                    if is_daily:
                        logger.warning("%s: hết quota ngày → thử model khác", model_name)
                        self.exhausted.add(model_name)
                        continue
                    else:
                        # Rate limit phút — chờ và retry
                        wait = 30
                        m = re.search(r"retry[^0-9]*(\d+)s", err, re.IGNORECASE)
                        if m:
                            wait = int(m.group(1)) + 2
                        logger.warning(
                            "%s: rate limit, chờ %ds...", model_name, wait
                        )
                        time.sleep(wait)
                        try:
                            llm = self._build_llm(model_name)
                            if use_web_search:
                                llm = llm.bind(tools=[{"google_search": {}}])
                            chain = web_prompt | llm
                            response = chain.invoke(prompt_inputs)
                            answer = response.content if hasattr(response, 'content') else str(response)
                            google_sources = []
                            if hasattr(response, 'response_metadata'):
                                meta = response.response_metadata
                                grounding_meta = meta.get("grounding_metadata", {})
                                if "grounding_chunks" in grounding_meta:
                                    for chunk in grounding_meta["grounding_chunks"]:
                                        web = chunk.get("web", {})
                                        if web:
                                            google_sources.append({
                                                "title": web.get("title", "Google Search"),
                                                "uri": web.get("uri", "")
                                            })
                            return answer, google_sources
                        except Exception:
                            logger.error("%s: vẫn lỗi sau retry → thử model khác", model_name)
                            self.exhausted.add(model_name)
                            continue
                else:
                    logger.error("LLM error (non-quota): %s", err)
                    raise

        # TỰ ĐỘNG DỰ PHÒNG SANG OPENAI KHI GEMINI HẾT QUOTA HÀNG NGÀY
        if settings.OPENAI_API_KEY:
            logger.warning("Tất cả Gemini model đều hết quota ngày. Tự động chuyển sang OpenAI gpt-4o-mini dự phòng...")
            try:
                llm = self._build_openai_llm("gpt-4o-mini")
                chain = web_prompt | llm | StrOutputParser()
                return chain.invoke(prompt_inputs), []
            except Exception as e:
                logger.error("Lỗi khi gọi model dự phòng OpenAI: %s", str(e))

        raise RuntimeError(
            "Tất cả Gemini model đều hết quota hôm nay và không có OpenAI dự phòng hợp lệ.\n"
            "Giải pháp:\n"
            "  1. Chờ đến 00:00 UTC để quota reset\n"
            "  2. Bật billing trên Google AI Studio\n"
            "  3. Cấu hình OPENAI_API_KEY dự phòng trong file .env"
        )

    def status(self) -> dict:
        return {
            "current_model": self.current_model,
            "available": [m for m in self.models if m not in self.exhausted],
            "exhausted": list(self.exhausted),
        }


# ── Singleton model manager ─────────────────────────────────────

_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Lazy-load ModelManager một lần duy nhất."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
        logger.info("ModelManager init: %s", _model_manager.models)
    return _model_manager
