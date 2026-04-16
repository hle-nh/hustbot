# src/retriever.py

import os
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'

from dotenv import load_dotenv

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from pydantic import Field
from typing import List
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

CHROMA_DIR  = os.getenv("CHROMA_DIR", "./chroma_db")
RETRIEVER_K = int(os.getenv("RETRIEVER_K", 4))

SYNONYMS = {
    # Học phí
    "học phí":              "mức học phí tín chỉ học phí TCHP",
    "đóng tiền học":        "học phí tín chỉ học phí",
    "tiền học kỳ":          "học phí học kỳ",
    "tín chỉ":               "TCHP",
    "Chương trình elitech": "Chương trình tiên tiến",
    "Quốc phòng":           "GDQP-AN",            


    # Ngoại ngữ
    "ielts":                "IELTS chuẩn ngoại ngữ đầu ra bậc",
    "toeic":                "TOEIC chuẩn ngoại ngữ đầu ra bậc",
    "chuẩn tiếng anh":      "chuẩn ngoại ngữ đầu ra bậc trình độ",
    "miễn tiếng anh":       "miễn học phần ngoại ngữ cơ bản",
    "b1 b2":                "bậc 3 bậc 4 khung năng lực ngoại ngữ",

    # Thường gặp
    "điểm rèn luyện":       "điểm đánh giá rèn luyện sinh viên",
    "rớt môn":              "không đạt học phần",
    "nợ môn":               "tín chỉ nợ đọng",
    "học lại":              "đăng ký học lại học phần",
    "bằng khá":             "xếp loại tốt nghiệp loại khá",
    "điểm tích lũy":        "điểm trung bình tích lũy CPA",
    "cảnh cáo học vụ":      "cảnh báo học tập",
}

def expand_query(query: str) -> str:
    q = query.lower()
    for student_term, official_term in SYNONYMS.items():
        if student_term in q:
            q = q + " " + official_term  # thêm vào, không xóa
    return q


# ==============================================
# VIETNAMESE TOKENIZER cho BM25
# ==============================================

def vietnamese_tokenizer(text: str) -> List[str]:
    """
    Tokenizer đơn giản cho tiếng Việt:
    - Lowercase
    - Tách theo khoảng trắng
    - Giữ lại các n-gram 2 từ (bigrams) để BM25 hiểu cụm từ ghép
      ví dụ: "bằng giỏi" → ["bằng", "giỏi", "bằng_giỏi"]
    Không cần underthesea/pyvi — hoạt động offline.
    """
    text = text.lower().strip()
    tokens = text.split()
    # Thêm bigrams
    bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    return tokens + bigrams


# ==============================================
# HYBRID RETRIEVER
# ==============================================

class HybridRetriever(BaseRetriever):
    """Hybrid retriever kết hợp BM25 + Semantic search."""

    bm25_retriever: BM25Retriever
    semantic_retriever: object = Field(exclude=True)
    k: int = 4

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(self, query: str) -> List[Document]:
        bm25_docs     = self.bm25_retriever.invoke(query)
        semantic_docs = self.semantic_retriever.invoke(query)

        # Dedup dùng toàn bộ nội dung làm key (không chỉ 100 ký tự đầu)
        seen   = set()
        merged = []
        # Xen kẽ để đảm bảo cả hai nguồn đều có đại diện
        for doc in _interleave(bm25_docs, semantic_docs):
            key = doc.page_content.strip()
            if key not in seen:
                seen.add(key)
                merged.append(doc)

        return merged[:self.k * 2]  # trả về nhiều hơn để reranker/fallback chọn lọc


def _interleave(list_a: list, list_b: list) -> list:
    """Xen kẽ hai list: a[0], b[0], a[1], b[1], ..."""
    result = []
    for a, b in zip(list_a, list_b):
        result.append(a)
        result.append(b)
    # Phần còn dư
    result.extend(list_a[len(list_b):])
    result.extend(list_b[len(list_a):])
    return result


# ==============================================
# BƯỚC 1: KẾT NỐI LẠI CHROMADB
# ==============================================

def load_vectorstore() -> Chroma:
    print("📦 Đang kết nối ChromaDB...")

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={"device": os.getenv("DEVICE", "cpu")},
        encode_kwargs={"normalize_embeddings": True}
    )

    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name="hust_regulations"
    )

    count = vectorstore._collection.count()
    print(f"✅ Đã kết nối — {count} chunks trong database")
    return vectorstore


# ==============================================
# BƯỚC 2: LẤY TẤT CẢ CHUNKS CHO BM25
# ==============================================

def get_all_chunks(vectorstore: Chroma) -> list[Document]:
    result = vectorstore._collection.get(
        include=["documents", "metadatas"]
    )

    docs = []
    for text, meta in zip(result["documents"], result["metadatas"]):
        docs.append(Document(page_content=text, metadata=meta))

    print(f"📚 Đã load {len(docs)} chunks cho BM25")
    return docs


# ==============================================
# BƯỚC 3: XÂY DỰNG HYBRID RETRIEVER
# ==============================================

def build_hybrid_retriever(
    vectorstore: Chroma,
    all_chunks: list,
    k: int = RETRIEVER_K
) -> HybridRetriever:

    semantic_retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k * 2}
    )

    # Dùng Vietnamese tokenizer thay vì mặc định
    bm25_retriever = BM25Retriever.from_documents(
        all_chunks,
        preprocess_func=vietnamese_tokenizer
    )
    bm25_retriever.k = k * 2

    retriever = HybridRetriever(
        bm25_retriever=bm25_retriever,
        semantic_retriever=semantic_retriever,
        k=k,
    )

    print(f"🔍 Hybrid retriever: BM25 (Vietnamese) + Semantic, k={k}")
    return retriever


# ==============================================
# BƯỚC 4: RERANKER (tùy chọn)
# ==============================================

def rerank(
    query: str,
    docs: list[Document],
    top_k: int = RETRIEVER_K
) -> list[Document]:
    try:
        from FlagEmbedding import FlagReranker

        reranker = FlagReranker(
            "BAAI/bge-reranker-v2-m3",
            use_fp16=True
        )

        pairs  = [[query, doc.page_content] for doc in docs]
        scores = reranker.compute_score(pairs, normalize=True)

        ranked = sorted(
            zip(scores, docs),
            key=lambda x: x[0],
            reverse=True
        )

        top_docs = [doc for _, doc in ranked[:top_k]]
        print(f"🏆 Reranker: {len(docs)} → {len(top_docs)} chunks")
        return top_docs

    except ImportError:
        print("⚠️  FlagEmbedding chưa cài — bỏ qua reranker")
        return docs[:top_k]


# ==============================================
# HÀM CHÍNH: RETRIEVE
# ==============================================

def retrieve(
    query: str,
    hybrid_retriever: HybridRetriever,
    use_reranker: bool = True
) -> list[Document]:
    """
    Luồng: query → hybrid search → dedup → reranker → top K chunks
    """
    candidates = hybrid_retriever.invoke(query)

    if use_reranker:
        final_docs = rerank(query, candidates)
    else:
        # Fallback: đảm bảo không có duplicate trang từ cùng file
        final_docs = _deduplicate_by_page(candidates, top_k=RETRIEVER_K)

    print(f"\n📎 Nguồn tài liệu được chọn:")
    for i, doc in enumerate(final_docs, 1):
        src  = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        print(f"  {i}. {src} — trang {page}")

    return final_docs


def _deduplicate_by_page(docs: list[Document], top_k: int) -> list[Document]:
    """
    Khi không có reranker, loại bỏ các chunk từ cùng file + trang
    để tránh trả về 4 chunks toàn từ trang 18.
    """
    seen   = set()
    result = []
    for doc in docs:
        src  = doc.metadata.get("source", "")
        page = doc.metadata.get("page", "")
        key  = f"{src}_{page}"
        if key not in seen:
            seen.add(key)
            result.append(doc)
        if len(result) >= top_k:
            break
    return result


# ==============================================
# KHỞI TẠO
# ==============================================

def init_retriever() -> HybridRetriever:
    vectorstore = load_vectorstore()
    all_chunks  = get_all_chunks(vectorstore)
    retriever   = build_hybrid_retriever(vectorstore, all_chunks)
    return retriever


# ==============================================
# TEST NHANH
# ==============================================

if __name__ == "__main__":
    retriever = init_retriever()

    test_queries = [
        "bằng giỏi",
        "điều kiện xét tốt nghiệp",
        "cảnh báo học tập mức 3",
    ]

    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"❓ {query}")
        docs = retrieve(query, retriever)
        print(f"💬 Chunk liên quan nhất:")
        print(docs[0].page_content[:300])
        print("...")