# src/chain.py

import os
import sys
import time
import re

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from retriever import init_retriever, retrieve


load_dotenv()

GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", 0))

# Danh sách model ưu tiên — tự động chuyển khi hết quota
MODEL_PRIORITY = [
    os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]
MODEL_PRIORITY = list(dict.fromkeys(MODEL_PRIORITY))


# ==============================================
# BƯỚC 1: PROMPT TEMPLATE
# ==============================================

SYSTEM_PROMPT = """Bạn là trợ lý tư vấn học vụ của Đại học Bách khoa Hà Nội (HUST).

QUY TẮC:
1. Trả lời dựa trên tài liệu trong phần [TÀI LIỆU].
2. Nếu câu hỏi yêu cầu TÍNH TOÁN (GPA, tín chỉ, điểm trung bình...):
   - Lấy công thức/ngưỡng từ tài liệu
   - Dùng số liệu sinh viên cung cấp để tính
   - Trình bày rõ từng bước tính
3. Nếu câu hỏi là tra cứu thuần túy: chỉ dùng thông tin trong tài liệu.
4. Nếu tài liệu KHÔNG có thông tin liên quan → trả lời:
   "Tôi không tìm thấy thông tin này trong tài liệu hiện có."
5. Cuối câu trả lời ghi nguồn: 📚 Nguồn: [tên file] — trang [số trang]
6. Trả lời bằng tiếng Việt, ngắn gọn và rõ ràng.

[TÀI LIỆU]
{context}
"""

HUMAN_PROMPT = "Câu hỏi: {question}"

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human",  HUMAN_PROMPT),
])


# ==============================================
# BƯỚC 2: ĐỊNH DẠNG CONTEXT
# ==============================================

def format_context(docs: list) -> str:
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page",   "?")
        chunk_text = f"[{i}] Nguồn: {source} — trang {page}\n{doc.page_content}\n"
        formatted.append(chunk_text)
    return "\n---\n".join(formatted)


# ==============================================
# BƯỚC 3: MODEL MANAGER — tự động đổi model khi hết quota
# ==============================================

class ModelManager:
    """
    Quản lý danh sách model và tự động fallback khi gặp 429.

    Logic:
    - Lỗi quota NGÀY (PerDay/RPD) → đánh dấu model đã hết, chuyển model khác
    - Lỗi quota PHÚT (rate limit) → chờ rồi thử lại trên model hiện tại
    - Hết tất cả model → raise lỗi với hướng dẫn rõ ràng
    """

    def __init__(self, api_key: str):
        self.api_key       = api_key
        self.models        = MODEL_PRIORITY.copy()
        self.current_index = 0
        self.exhausted     = set()

    @property
    def current_model(self) -> str:
        return self.models[self.current_index]

    def _build_llm(self, model_name: str):
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.api_key,
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=1000,
        )

    def invoke_with_fallback(self, chain_input: dict) -> str:
        for i, model_name in enumerate(self.models):
            if model_name in self.exhausted:
                continue

            try:
                llm   = self._build_llm(model_name)
                chain = prompt | llm | StrOutputParser()

                if i != self.current_index:
                    print(f"🔄 Chuyển sang model: {model_name}")
                    self.current_index = i

                return chain.invoke(chain_input)

            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    # Kiểm tra hết quota ngày hay quota phút
                    is_daily_limit = any(
                        keyword in err
                        for keyword in ["PerDay", "per_day", "PerDayPer", "quotaValue"]
                    )

                    if is_daily_limit:
                        print(f"❌ {model_name}: hết quota ngày → thử model khác")
                        self.exhausted.add(model_name)
                        continue
                    else:
                        # Quota phút — chờ rồi retry
                        wait = 30
                        match = re.search(r"retry[^0-9]*(\d+)s", err, re.IGNORECASE)
                        if match:
                            wait = int(match.group(1)) + 2
                        print(f"⏳ {model_name}: giới hạn tốc độ, chờ {wait}s...")
                        time.sleep(wait)
                        try:
                            llm   = self._build_llm(model_name)
                            chain = prompt | llm | StrOutputParser()
                            return chain.invoke(chain_input)
                        except Exception:
                            print(f"❌ {model_name}: vẫn lỗi → thử model khác")
                            self.exhausted.add(model_name)
                            continue
                else:
                    raise  # lỗi khác (không phải quota) → raise thẳng

        # Hết tất cả model
        raise RuntimeError(
            "❌ Tất cả model đều hết quota hôm nay.\n"
            "   Giải pháp:\n"
            "   1. Chờ đến 00:00 UTC để quota reset\n"
            "   2. Bật billing trên Google AI Studio để bỏ giới hạn\n"
            "   3. Đổi sang OpenAI API (gpt-4o-mini) — rẻ và không giới hạn RPD"
        )

    def status(self) -> str:
        available = [m for m in self.models if m not in self.exhausted]
        exhausted = list(self.exhausted)
        return (
            f"✅ Còn dùng được: {available}\n"
            f"❌ Hết quota hôm nay: {exhausted if exhausted else 'không có'}"
        )


def build_model_manager() -> ModelManager:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("❌ Không tìm thấy GOOGLE_API_KEY trong file .env")
    manager = ModelManager(api_key)
    print(f"🤖 Model ưu tiên: {manager.models}")
    return manager


# BƯỚC 3B: QUERY REWRITING — tách search query và LLM query

def rewrite_for_search(question: str) -> str:
    """
    Làm sạch câu hỏi để dùng cho retrieval.
    Bỏ số liệu cá nhân (tín chỉ cụ thể, CPA cụ thể...)
    vì chúng làm nhiễu BM25 và semantic search.

    Câu hỏi gốc vẫn được giữ nguyên để đưa vào LLM.

    Ví dụ:
    "tôi có 80 tín chỉ CPA 3.11 cần lên giỏi"
    → "tôi có tín chỉ CPA cần lên giỏi"
    """
    q = question

    # Bỏ số kèm đơn vị tín chỉ: "80 tín chỉ", "50 TC", "32 tín"
    q = re.sub(r'\b\d+[.,]?\d*\s*(tín chỉ|TC|tín)\b', 'tín chỉ', q, flags=re.IGNORECASE)

    # Bỏ giá trị CPA/GPA cụ thể: "CPA 3.11", "GPA 2.5"
    q = re.sub(r'\b(CPA|GPA)\s+\d+[.,]\d+\b', r'\1', q, flags=re.IGNORECASE)

    # Bỏ số nguyên đứng một mình từ 2 chữ số trở lên (năm học, số điểm...)
    q = re.sub(r'(?<![\w,.])\b\d{2,}\b(?![\w,.])', '', q)

    # Chuẩn hóa khoảng trắng
    q = re.sub(r'\s+', ' ', q).strip()

    return q


# BƯỚC 4: HÀM TRẢ LỜI CHÍNH

def ask(
    question: str,
    retriever,
    model_manager: ModelManager,
    search_question: str = None,  # thêm tham số này
    use_reranker: bool = True,
    verbose: bool = False
) -> dict:

    # Nếu có câu hỏi riêng cho search thì dùng nó, không thì dùng question
    raw_search = search_question if search_question else question
    search_query = rewrite_for_search(raw_search)

    if search_query != raw_search:
        print(f"🔍 Search query: {search_query}")

    docs = retrieve(search_query, retriever, use_reranker=use_reranker)
    # LLM vẫn nhận full_question có lịch sử
    context = format_context(docs)   # thêm dòng này
    answer = model_manager.invoke_with_fallback({
        "context":  context,
        "question": question,
    })

    sources = [
        {
            "file":    doc.metadata.get("source", "unknown"),
            "page":    doc.metadata.get("page",   "?"),
            "preview": doc.page_content[:150] + "..."
        }
        for doc in docs
    ]

    return {
        "question": question,
        "answer":   answer,
        "sources":  sources,
        "context":  context,
    }

# BƯỚC 5: HỘI THOẠI NHIỀU LƯỢT

class RAGChat:

    def __init__(self, retriever, model_manager: ModelManager):
        self.retriever     = retriever
        self.model_manager = model_manager
        self.history       = []

    def chat(self, question: str) -> dict:
        if self.history:
            history_text = "\n".join([
                f"Sinh viên: {h['question']}\nTrợ lý: {h['answer']}"
                for h in self.history[-2:]
            ])
            full_question = f"Lịch sử hội thoại:\n{history_text}\n\nCâu hỏi hiện tại: {question}"
        else:
            full_question = question

        result = ask(
            question=full_question,
            retriever=self.retriever,
            model_manager=self.model_manager,
            # Truyền thêm câu hỏi gốc để rewrite đúng
            search_question=question  # <-- chỉ rewrite câu này
        )
        self.history.append({
            "question": question, 
            "answer": result["answer"]
        })

        # QUAN TRỌNG 2: Phải return result để các file khác (main, evaluate) sử dụng được
        return result


    def clear_history(self):
        self.history = []
        print("🗑️  Đã xóa lịch sử hội thoại")

    def model_status(self):
        """Gõ /status trong chatbot để xem trạng thái quota các model."""
        print(self.model_manager.status())


# KHỞI TẠO

def init_chain() -> RAGChat:
    print("\n🚀 Đang khởi động RAG pipeline...")
    retriever     = init_retriever()
    model_manager = build_model_manager()
    chat          = RAGChat(retriever, model_manager)
    print("✅ Sẵn sàng!\n")
    return chat


if __name__ == "__main__":
    chat = init_chain()
    questions = [
        "Điều kiện xét tốt nghiệp là gì?",
        "Vậy nếu tôi bị cảnh báo học vụ thì có ảnh hưởng không?",
    ]
    for q in questions:
        print(f"\n{'='*55}")
        print(f"❓ {q}")
        result = chat.chat(q)
        print(f"\n💬 {result['answer']}")