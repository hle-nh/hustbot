"""
Retriever module — refactor từ src/retriever.py.

Thay đổi chính:
- Vectorstore và BM25 được khởi tạo một lần (singleton) qua init_retriever()
- expand_query + vietnamese_tokenizer giữ nguyên
- Reranker tách sang reranker.py
"""
from __future__ import annotations

import logging
import os
import re
from typing import List

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import Field

from app.core.config import settings
from app.rag.reranker import rerank

logger = logging.getLogger(__name__)


# ── Synonym expansion cho BM25 ─────────────────────────────────

SYNONYMS: dict[str, str] = {
    # Học phí
    "học phí":               "mức học phí tín chỉ học phí TCHP",
    "đóng tiền học":         "học phí tín chỉ học phí",
    "tiền học kỳ":           "học phí học kỳ",
    "học phí vlvh":          "học phí vừa làm vừa học VLVH học phí hệ VLVH",
    "vlvh":                  "vừa làm vừa học",
    "tín chỉ":               "TCHP",
    "chương trình elitech":  "chương trình tiên tiến",
    "quốc phòng":            "GDQP-AN giáo dục quốc phòng an ninh",
    "quân sự":               "GDQP-AN giáo dục quốc phòng an ninh",
    "thể dục":               "GDTC giáo dục thể chất",
    "triết học":             "LLCT lý luận chính trị",
    "global ict":            "Công nghệ thông tin Việt-Nhật Global ICT ELITECH",
    # Tốt nghiệp
    "điều kiện tốt nghiệp":  "xét công nhận tốt nghiệp tiêu chuẩn tốt nghiệp",
    "xét tốt nghiệp":        "xét công nhận tốt nghiệp điều kiện xét",
    "bảo vệ đồ án":          "đồ án tốt nghiệp luận văn tốt nghiệp",
    "làm đồ án":             "thực hiện đồ án tốt nghiệp",
    "chuẩn đầu ra":          "yêu cầu chuẩn đầu ra tiêu chuẩn ngoại ngữ",
    # Ngoại ngữ
    "ielts":                 "IELTS chuẩn ngoại ngữ đầu ra bậc",
    "toeic":                 "TOEIC chuẩn ngoại ngữ đầu ra bậc",
    "chuẩn tiếng anh":       "chuẩn ngoại ngữ đầu ra bậc trình độ",
    "miễn tiếng anh":        "miễn học phần ngoại ngữ cơ bản",
    "b1 b2":                 "bậc 3 bậc 4 khung năng lực ngoại ngữ",
    # Đăng ký / học vụ
    "điểm rèn luyện":        "điểm đánh giá rèn luyện sinh viên",
    "rớt môn":               "không đạt học phần điểm F",
    "nợ môn":                "tín chỉ nợ đọng học phần chưa hoàn thành",
    "học lại":               "đăng ký học lại học phần",
    "đăng ký muộn":          "đăng ký học phần muộn hạn đăng ký",
    "bảo lưu":               "bảo lưu kết quả học tập tạm dừng",
    "thôi học":              "buộc thôi học xét thôi học",
    # Xếp loại
    "bằng khá":              "xếp loại tốt nghiệp loại khá",
    "bằng giỏi":             "xếp loại tốt nghiệp loại giỏi",
    "bằng xuất sắc":         "xếp loại tốt nghiệp loại xuất sắc",
    "điểm tích lũy":         "điểm trung bình tích lũy CPA GPA",
    "cảnh cáo học vụ":       "cảnh báo học tập",
    # Hệ đào tạo
    "hệ kỹ sư":              "chương trình đào tạo kỹ sư",
    "hệ cử nhân":            "chương trình đào tạo cử nhân",
    "hệ tiên tiến":          "chương trình tiên tiến elitech",
    "ct1 ct2 ct3":           "nhóm tín chỉ khối kiến thức",
    # Học bổng / Miễn giảm
    "học bổng":              "học bổng khuyến khích học tập miễn giảm học phí",
    "miễn học phí":          "miễn giảm học phí đối tượng chính sách",
    # Viết tắt chuyên ngành và thuật ngữ học phí
    "kỹ thuật":              "KT kỹ thuật",
    "kt":                    "KT kỹ thuật",
    "kỹ thuật in":           "KT in kỹ thuật in",
    "kt in":                 "KT in kỹ thuật in",
    "khoa học dữ liệu":      "KHDL khoa học dữ liệu Data Science",
    "khdl":                  "KHDL khoa học dữ liệu Data Science",
    "trí tuệ nhân tạo":      "TTNT trí tuệ nhân tạo AI",
    "ttnt":                  "TTNT trí tuệ nhân tạo AI",
    "khoa học dữ liệu và trí tuệ nhân tạo": "IT-E10 khoa học dữ liệu và trí tuệ nhân tạo KHDL TTNT",
    "it-e10":                "IT-E10 khoa học dữ liệu và trí tuệ nhân tạo KHDL TTNT",
    "chương trình tiên tiến": "tiên tiến elitech",
    "elitech":               "tiên tiến elitech",
}


def expand_query(query: str) -> str:
    """Mở rộng query với từ đồng nghĩa từ SYNONYMS dict."""
    q = query.lower()
    for student_term, official_term in SYNONYMS.items():
        if student_term in q:
            q = q + " " + official_term
    return q


# ── Query rewriting cho search (không cho LLM) ─────────────────

def rewrite_for_search(question: str) -> str:
    """
    Làm sạch câu hỏi cho retrieval — bỏ số liệu cá nhân gây nhiễu BM25.
    Chỉ xóa số rõ ràng là personal data, không xóa số học vụ quan trọng.
    """
    q = question

    # Bỏ số kèm đơn vị tín chỉ: "80 tín chỉ", "50 TC"
    q = re.sub(
        r"\b\d+[.,]?\d*\s*(tín chỉ|TC|tín)\b", "tín chỉ", q,
        flags=re.IGNORECASE
    )

    # Bỏ giá trị CPA/GPA cụ thể: "CPA 3.11", "GPA 2.5"
    q = re.sub(
        r"\b(CPA|GPA)\s+\d+[.,]\d+\b", r"\1", q,
        flags=re.IGNORECASE
    )

    # Normalize whitespace
    q = re.sub(r"\s+", " ", q).strip()
    return q


# ── Vietnamese tokenizer cho BM25 ──────────────────────────────

def vietnamese_tokenizer(text: str) -> List[str]:
    """
    Tokenizer đơn giản: lowercase + bigrams.
    Không cần underthesea — hoạt động offline.
    """
    text = text.lower().strip()
    tokens = text.split()
    bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    return tokens + bigrams


# ── Hybrid Retriever ────────────────────────────────────────────

class HybridRetriever(BaseRetriever):
    """BM25 + Semantic search, kết quả được xen kẽ (interleave)."""

    bm25_retriever: BM25Retriever
    semantic_retriever: object = Field(exclude=True)
    k: int = 6

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(self, query: str) -> List[Document]:
        bm25_docs = self.bm25_retriever.invoke(query)
        semantic_docs = self.semantic_retriever.invoke(query)

        seen: set[str] = set()
        merged: list[Document] = []
        for doc in _interleave(bm25_docs, semantic_docs):
            key = doc.page_content.strip()
            if key not in seen:
                seen.add(key)
                merged.append(doc)

        # Trả nhiều hơn k để reranker có thêm candidates (tăng 2x → 2.5x)
        return merged[: int(self.k * 2.5)]


def _interleave(list_a: list, list_b: list) -> list:
    result = []
    for a, b in zip(list_a, list_b):
        result.append(a)
        result.append(b)
    result.extend(list_a[len(list_b):])
    result.extend(list_b[len(list_a):])
    return result


# ── Category → file mapping ──────────────────────────────────────

# Tên file (basename) thuộc nhóm tuyển sinh
_ADMISSIONS_FILENAMES = {"5730_qd-dhbk-qcts.pdf"}


def _get_category_source_paths(
    vectorstore: Chroma,
    category: str,
) -> list[str] | None:
    """
    Trả về danh sách đường dẫn tuyệt đối của các file thuộc danh mục.
    Trả về None nếu category == 'all' (không lọc).
    """
    if category == "all":
        return None

    result = vectorstore._collection.get(include=["metadatas"])
    all_source_paths: set[str] = {
        meta["source"]
        for meta in result["metadatas"]
        if meta.get("source")
    }

    if category == "admissions":
        filtered = [
            p for p in all_source_paths
            if any(fname in p for fname in _ADMISSIONS_FILENAMES)
        ]
    else:  # "academic"
        filtered = [
            p for p in all_source_paths
            if not any(fname in p for fname in _ADMISSIONS_FILENAMES)
        ]

    logger.info(
        "Category '%s': lọc %d / %d file nguồn",
        category, len(filtered), len(all_source_paths),
    )
    return filtered


# ── Singleton retriever ─────────────────────────────────────────

_retriever_instance: HybridRetriever | None = None
_all_docs_cache: list[Document] = []  # Cache cho BM25 filtering


def get_retriever() -> HybridRetriever:
    """
    Lazy-load HybridRetriever một lần duy nhất.
    Bao gồm: ChromaDB connection + BM25 index từ tất cả chunks.
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = _build_retriever()
    return _retriever_instance


def _build_retriever() -> HybridRetriever:
    global _all_docs_cache
    k = settings.RETRIEVER_K

    # 1. Load ChromaDB
    logger.info("Kết nối ChromaDB tại: %s", settings.CHROMA_DIR)
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={"device": settings.DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )
    vectorstore = Chroma(
        persist_directory=settings.CHROMA_DIR,
        embedding_function=embeddings,
        collection_name="hust_regulations",
    )
    count = vectorstore._collection.count()
    logger.info("ChromaDB: %d chunks ✓", count)

    # 2. Load all chunks cho BM25
    result = vectorstore._collection.get(include=["documents", "metadatas"])
    all_docs = [
        Document(page_content=text, metadata=meta)
        for text, meta in zip(result["documents"], result["metadatas"])
    ]
    _all_docs_cache = all_docs  # Lưu cache để dùng cho category filtering
    logger.info("BM25 index: %d chunks ✓", len(all_docs))

    # 3. Build retrievers
    candidate_k = int(k * 2.5)
    semantic_retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": candidate_k},
    )
    bm25_retriever = BM25Retriever.from_documents(
        all_docs, preprocess_func=vietnamese_tokenizer
    )
    bm25_retriever.k = candidate_k

    return HybridRetriever(
        bm25_retriever=bm25_retriever,
        semantic_retriever=semantic_retriever,
        k=k,
    )


# ── Main retrieve function ─────────────────────────────────────────────────

def retrieve(
    query: str,
    use_reranker: bool = True,
    web_search_override: bool | None = None,
    category: str = "all",
) -> tuple[list[Document], bool]:
    """
    Full retrieval pipeline:
    query → expand → rewrite → hybrid search (with category filter) → rerank → top K docs

    Args:
        category: 'all' | 'academic' | 'admissions'
            - 'admissions': chỉ tìm trong tài liệu tuyển sinh (5730_qd-dhbk-qcts.pdf)
            - 'academic': loại trừ tài liệu tuyển sinh, chỉ tìm quy chế học vụ
            - 'all': tìm trong toàn bộ tài liệu

    Returns:
        (docs, web_search_used): danh sách docs và flag web search đã dùng hay không.
    """
    retriever = get_retriever()
    vectorstore = retriever.semantic_retriever.vectorstore

    # Expand synonyms + rewrite for search
    expanded = expand_query(query)
    search_q = rewrite_for_search(expanded)

    if search_q != query:
        logger.debug("Search query rewritten: %r → %r", query, search_q)

    # ── Category filtering ────────────────────────────────────────
    filtered_paths = _get_category_source_paths(vectorstore, category)

    # Xác định có dùng Web Search không
    # Priority: per-request override > server settings (ENABLE_WEB_SEARCH)
    use_web_search = False
    if web_search_override is True:
        use_web_search = True
    elif web_search_override is False:
        use_web_search = False
    else:
        use_web_search = settings.ENABLE_WEB_SEARCH

    # Kiểm tra Web Search Fallback nếu được bật
    if use_web_search:
        try:
            raw_results = vectorstore.similarity_search_with_relevance_scores(search_q, k=1)
            max_score = raw_results[0][1] if raw_results else 0.0
            logger.info("ChromaDB Max Similarity Score: %.4f (Ngưỡng: %.4f)", max_score, settings.WEB_SEARCH_THRESHOLD)

            if max_score < settings.WEB_SEARCH_THRESHOLD:
                logger.info(
                    "Độ tương đồng ngữ cảnh HUST thấp (< %.2f). Chuyển sang tìm kiếm Web...",
                    settings.WEB_SEARCH_THRESHOLD
                )
                return [], True
        except Exception as e:
            logger.error("Lỗi khi kiểm tra độ tương đồng ChromaDB: %s", str(e))

    # ── Hybrid search với category filter ────────────────────────
    k = settings.RETRIEVER_K
    candidate_k = int(k * 2.5)

    if filtered_paths is not None and len(filtered_paths) > 0:
        # Chroma: lọc theo source metadata
        chroma_filter: dict = (
            {"source": filtered_paths[0]}
            if len(filtered_paths) == 1
            else {"source": {"$in": filtered_paths}}
        )
        semantic_docs = vectorstore.similarity_search(
            search_q, k=candidate_k, filter=chroma_filter
        )

        # BM25: lọc all_docs_cache theo source
        filtered_docs = [
            doc for doc in _all_docs_cache
            if doc.metadata.get("source") in filtered_paths
        ]
        if filtered_docs:
            bm25_filtered = BM25Retriever.from_documents(
                filtered_docs, preprocess_func=vietnamese_tokenizer
            )
            bm25_filtered.k = candidate_k
            bm25_docs = bm25_filtered.invoke(search_q)
        else:
            bm25_docs = []

        # Interleave BM25 + Semantic
        seen: set[str] = set()
        candidates: list[Document] = []
        for doc in _interleave(bm25_docs, semantic_docs):
            key = doc.page_content.strip()
            if key not in seen:
                seen.add(key)
                candidates.append(doc)
        candidates = candidates[: int(k * 2.5)]
        logger.info(
            "Category '%s': %d candidates từ %d Chroma + %d BM25",
            category, len(candidates), len(semantic_docs), len(bm25_docs),
        )
    else:
        # Không lọc — dùng HybridRetriever thông thường
        candidates = retriever.invoke(search_q)

    if use_reranker:
        final_docs = rerank(query, candidates)
    else:
        from app.rag.reranker import _deduplicate_by_page
        final_docs = _deduplicate_by_page(candidates, settings.RETRIEVER_K)

    logger.info(
        "Retrieved %d docs for query: %r (category=%s)",
        len(final_docs), query[:60], category,
    )
    return final_docs, False
