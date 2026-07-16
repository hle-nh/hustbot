# HUSTBot Backend

## Cấu trúc thư mục

```
backend/
├── app/
│   ├── api/routes/     # FastAPI routes (chat, health)
│   ├── core/           # config.py, database.py
│   ├── models/         # SQLAlchemy ORM (conversation, message)
│   ├── schemas/        # Pydantic schemas (request/response)
│   ├── services/       # Business logic (conversation_service, rag_service)
│   └── rag/            # RAG modules (retriever, reranker, prompt_builder, generator)
├── ingest/             # PDF ingestion pipeline
├── alembic/            # Database migrations
├── docker-compose.yml  # PostgreSQL
├── requirements.txt
└── .env
```

## Quick Start

### 1. Cài dependencies

```bash
cd backend/
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Khởi động PostgreSQL

```bash
docker compose up -d
```

### 3. Chạy migrations

```bash
alembic upgrade head
```

### 4. (Lần đầu) Build vector database

```bash
# Nếu chưa có chroma_db/ hoặc muốn rebuild
python -m ingest.pipeline
```

### 5. Khởi động API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/chat` | Gửi câu hỏi, nhận trả lời |
| GET | `/chat/conversations/{id}` | Xem lịch sử conversation |
| DELETE | `/chat/conversations/{id}` | Xóa conversation |
| GET | `/health` | Health check |
| GET | `/health/detailed` | Status chi tiết (model quota, retriever) |

## Request / Response

```json
POST /chat
{
  "conversation_id": null,
  "message": "Điều kiện tốt nghiệp là gì?"
}

→ 200 OK
{
  "conversation_id": "uuid-here",
  "answer": "Theo quy định HUST...",
  "sources": [
    {"file": "QCDT_2025.pdf", "page": 24, "preview": "..."}
  ],
  "elapsed_seconds": 2.3
}
```

## Cấu hình `.env`

| Biến | Mặc định | Mô tả |
|------|---------|-------|
| `GOOGLE_API_KEY` | — | Bắt buộc |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model ưu tiên |
| `DATABASE_URL` | localhost:5432 | PostgreSQL async URL |
| `CHROMA_DIR` | `../chroma_db` | Đường dẫn ChromaDB |
| `RETRIEVER_K` | `6` | Số chunks trả về |
| `SLIDING_WINDOW_SIZE` | `8` | Số messages lịch sử đưa vào LLM |
| `MAX_OUTPUT_TOKENS` | `2048` | Giới hạn output LLM |
