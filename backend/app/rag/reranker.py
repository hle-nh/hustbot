"""
Reranker module — tách từ src/retriever.py.

FIX QUAN TRỌNG: Singleton pattern để tránh reload model mỗi query.
Model BAAI/bge-reranker-v2-m3 nặng ~600MB, reload mỗi query tốn 2-3 giây.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# ── Singleton instance ─────────────────────────────────────────
_reranker_instance = None


def get_reranker():
    """Lazy-load FlagReranker một lần duy nhất cho toàn bộ app lifetime."""
    global _reranker_instance
    if _reranker_instance is None:
        try:
            from FlagEmbedding import FlagReranker
            logger.info("Loading BAAI/bge-reranker-v2-m3...")
            _reranker_instance = FlagReranker(
                "BAAI/bge-reranker-v2-m3",
                use_fp16=True,
            )
            logger.info("Reranker loaded ✓")
        except ImportError:
            logger.warning(
                "FlagEmbedding chưa cài — reranker bị tắt. "
                "Cài bằng: pip install FlagEmbedding"
            )
            _reranker_instance = None
    return _reranker_instance


# ── Rerank function ────────────────────────────────────────────

def rerank(
    query: str,
    docs: list["Document"],
    top_k: int | None = None,
) -> list["Document"]:
    """
    Rerank docs theo relevance với query.
    Nếu FlagEmbedding chưa cài → fallback deduplicate by page.
    """
    if top_k is None:
        top_k = settings.RETRIEVER_K

    reranker = get_reranker()
    if reranker is None:
        # Fallback: deduplicate by (source, page)
        return _deduplicate_by_page(docs, top_k)

    pairs = [[query, doc.page_content] for doc in docs]
    try:
        scores = reranker.compute_score(pairs, normalize=True)
    except Exception as exc:
        logger.warning(
            "Reranker failed at runtime; falling back to deduplicate-by-page: %s",
            exc,
        )
        return _deduplicate_by_page(docs, top_k)

    ranked = sorted(
        zip(scores, docs),
        key=lambda x: x[0],
        reverse=True,
    )

    # Lọc theo ngưỡng điểm để loại chunk nhiễu khỏi context.
    # Giữ tối thiểu RERANK_MIN_KEEP chunk điểm cao nhất nếu tất cả dưới ngưỡng,
    # tránh trả về context rỗng cho câu hỏi hợp lệ nhưng điểm tương đồng thấp.
    threshold = settings.RERANK_SCORE_THRESHOLD
    min_keep = settings.RERANK_MIN_KEEP
    above = [(s, d) for s, d in ranked if s >= threshold]

    if len(above) >= min_keep:
        kept = above
    else:
        kept = ranked[:min_keep]

    top_docs = [doc for _, doc in kept[:top_k]]
    logger.debug(
        "Reranker: %d → %d chunks (threshold=%.2f, %d above)",
        len(docs), len(top_docs), threshold, len(above),
    )
    return top_docs


def _deduplicate_by_page(
    docs: list["Document"], top_k: int
) -> list["Document"]:
    """Fallback khi không có reranker: loại các chunk trùng lặp cùng file+trang, giữ lại các dòng bảng khác nhau."""
    seen: set[str] = set()
    result: list[Document] = []
    for doc in docs:
        src = doc.metadata.get("source", "")
        page = doc.metadata.get("page", "")
        is_table = doc.metadata.get("is_table", False)

        if is_table:
            t_idx = doc.metadata.get("table_index", "")
            r_idx = doc.metadata.get("table_row", "")
            key = f"{src}_{page}_table_{t_idx}_{r_idx}"
        else:
            # Đối với text thường, sử dụng hash nội dung để tránh loại bỏ các chunk văn bản khác nhau trên cùng trang
            content_hash = hash(doc.page_content)
            key = f"{src}_{page}_{content_hash}"

        if key not in seen:
            seen.add(key)
            result.append(doc)
        if len(result) >= top_k:
            break
    return result
