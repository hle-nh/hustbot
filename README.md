# 🎓 HUSTBot — Trợ lý Tư vấn Học vụ HUST

A Retrieval-Augmented Generation (RAG) chatbot for academic advising at Hanoi University of Science and Technology (HUST). HUSTBot answers student questions about regulations, GPA calculation, graduation requirements, and more — grounded in official university documents.

---

## ✨ Features

- **Hybrid Retrieval** — combines BM25 (with Vietnamese tokenizer + bigrams) and semantic search (BGE-M3 embeddings) for robust document retrieval
- **Automatic Model Fallback** — cycles through Gemini models (`gemini-2.5-flash` → `gemini-2.5-pro` → `gemini-2.5-flash-lite`) when quota is exhausted
- **Query Rewriting** — strips personal numeric data (GPA values, credit counts) before retrieval to reduce noise
- **Multi-turn Conversation** — maintains last 2 turns of chat history for context-aware follow-up questions
- **Optional Reranker** — uses `BAAI/bge-reranker-v2-m3` to rerank candidate chunks for higher precision
- **Table-aware Ingestion** — extracts both plain text and structured tables from PDFs via `pdfplumber`
- **RAGAS Evaluation** — automated pipeline to evaluate faithfulness, answer relevancy, context precision, and context recall

---


## 🗂️ Project Structure

```
hustbot/
├── app.py                  # Flask web server
├── demo_UI.html            # Chat interface (served at localhost:5000)
├── src/
│   ├── chain.py            # RAG chain, model manager, conversation logic
│   ├── retriever.py        # Hybrid retriever (BM25 + semantic + reranker)
│   ├── ingest.py           # PDF ingestion → chunking → ChromaDB
│   └── evaluate.py         # RAGAS evaluation pipeline
├── data/                   # Place your PDF documents here
├── chroma_db/              # Auto-generated vector database
├── tests/
│   ├── test_questions.json # Evaluation question set
│   └── eval_results.json   # Evaluation output
└── .env                    # API keys and config
```

---

## ⚙️ Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/hustbot.git
cd hustbot
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key_here

# Optional — defaults shown
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0
CHROMA_DIR=./chroma_db
DATA_DIR=./data
CHUNK_SIZE=500
CHUNK_OVERLAP=75
RETRIEVER_K=4
DEVICE=cpu          # Change to "cuda" if you have a GPU
```

### 3. Add your PDF documents

Place university regulation PDFs in the `data/` folder:

```
data/
├── quy_che_dao_tao.pdf
├── quy_dinh_hoc_phi.pdf
└── ...
```

### 4. Build the vector database

```bash
python src/ingest.py
```

This will extract text and tables from all PDFs, chunk them, embed with `BAAI/bge-m3`, and store in ChromaDB. **First run downloads the model (~5 minutes).**

### 5. Start the server

```bash
python app.py
```

Open your browser at [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 🔌 API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/`      | Serve the chat UI |
| `POST` | `/ask`   | Ask a question |
| `GET`  | `/health`| Health check |

### POST `/ask`

**Request:**
```json
{
  "question": "Điều kiện xét tốt nghiệp là gì?"
}
```

**Response:**
```json
{
  "answer": "Để xét tốt nghiệp, sinh viên cần...",
  "sources": [
    {
      "file": "quy_che_dao_tao.pdf",
      "page": 12,
      "preview": "Điều kiện xét tốt nghiệp bao gồm..."
    }
  ]
}
```

---

## 🧠 Architecture

```
User Question
     │
     ▼
Query Rewriting          ← strips personal numbers for cleaner retrieval
     │
     ▼
Hybrid Retrieval
  ├── BM25 (Vietnamese tokenizer + bigrams)
  └── Semantic Search (BGE-M3 embeddings)
     │
     ▼
Reranker (BGE-reranker-v2-m3)   ← optional, improves precision
     │
     ▼
Context Formatting
     │
     ▼
Gemini LLM  ←  auto-fallback across models on quota errors
     │
     ▼
Answer + Sources
```

---

## 📊 Evaluation

To run RAGAS evaluation on a test set:

1. Create `tests/test_questions.json`:
```json
[
  {
    "question": "Điều kiện xét tốt nghiệp là gì?",
    "ground_truth": "Sinh viên cần tích lũy đủ số tín chỉ theo chương trình..."
  }
]
```

2. Run evaluation:
```bash
python src/evaluate.py
```

Results are saved to `tests/eval_results.json` and printed to the console with pass/fail thresholds:

| Metric | Threshold | Description |
|--------|-----------|-------------|
| Faithfulness | ≥ 0.85 | Are answers grounded in the retrieved context? |
| Answer Relevancy | ≥ 0.80 | Does the answer address the question? |
| Context Precision | ≥ 0.75 | Are retrieved chunks relevant? |
| Context Recall | ≥ 0.75 | Is important information being retrieved? |

---

## 🛠️ Requirements

- Python 3.10+
- `flask`, `flask-cors`
- `langchain`, `langchain-core`, `langchain-community`, `langchain-google-genai`
- `langchain-chroma`, `langchain-huggingface`
- `pdfplumber`, `PyMuPDF`
- `sentence-transformers` (for BGE-M3)
- `FlagEmbedding` *(optional, for reranker)*
- `ragas`, `datasets` *(optional, for evaluation)*

---

## 🔧 Troubleshooting

**`ImportError` on startup** — Make sure you're using `langchain >= 0.1.0`. Run:
```bash
pip install --upgrade langchain langchain-core langchain-community
```

**`GOOGLE_API_KEY` not found** — Ensure your `.env` file is in the project root and contains a valid key from [Google AI Studio](https://aistudio.google.com).

**Quota exhausted (429 error)** — HUSTBot automatically tries fallback models. If all models are exhausted, wait until 00:00 UTC for quota reset or enable billing on Google AI Studio.

**Reranker not working** — Install the optional dependency:
```bash
pip install FlagEmbedding
```

---

## 📄 License

This project is for academic and research purposes at HUST. See `LICENSE` for details.
