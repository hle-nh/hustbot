# HUSTBot

HUSTBot is a Vietnamese academic advising chatbot for Hanoi University of Science and Technology. The system helps students ask natural questions about academic regulations, tuition, English requirements, graduation conditions, warnings, and admissions information, then returns concise answers grounded in official university documents.

## System Overview

University regulations are usually distributed as long PDF documents with formal wording, tables, article numbers, and scattered policy details. This makes it difficult for students to quickly find the exact rule they need. HUSTBot addresses this problem with a retrieval-augmented generation (RAG) architecture: instead of relying only on the language model's memory, it retrieves relevant passages from a local knowledge base and uses them as evidence for answer generation.

The project is organized as a full-stack application. The backend handles document ingestion, retrieval, reranking, prompt construction, answer generation, conversation storage, and evaluation scripts. The frontend provides a chat-style interface where students can ask informal Vietnamese questions and inspect the cited sources.

## Main Objectives

- Build a searchable knowledge base from official HUST academic documents.
- Support informal Vietnamese student questions and map them to formal academic terms.
- Combine keyword-based and semantic retrieval to improve evidence coverage.
- Generate grounded answers with visible source references.
- Evaluate retrieval and answer quality using benchmark questions and RAGAS-style metrics.

## Architecture

```text
Official PDFs / CSV dataset
        |
        v
Ingestion and chunking
        |
        v
ChromaDB vector store + BM25 keyword index
        |
        v
Hybrid retrieval + reranking
        |
        v
Prompt builder + LLM answer generation
        |
        v
FastAPI backend + React frontend
```

## RAG Pipeline

### Offline Phase

The offline phase prepares the knowledge base. Plain text is cleaned and split into overlapping chunks, while tables are converted into row-level chunks to preserve row-column relationships. Each chunk is enriched with metadata such as source file, page, document type, table flag, and article/table information. The processed chunks are embedded and stored in ChromaDB, while a BM25 index is built for keyword retrieval.

### Online Phase

When a student asks a question, the query is first normalized and expanded with academic synonyms. BM25 retrieval and dense retrieval search the knowledge base in parallel. Their results are merged into a candidate pool, reranked, and the top passages are passed to the LLM. The final response includes both the generated answer and source references.

## Data and Evaluation

The `data/` directory contains the prepared datasets used for retrieval and evaluation. Large runtime artifacts such as ChromaDB indexes, local databases, virtual environments, and raw archives are intentionally excluded from Git.

The benchmark file is:

```text
academic_advising_benchmark.xlsx
```

It contains curated academic advising questions with categories, difficulty levels, user prompts, and expected answers. The benchmark is used to evaluate retrieval quality and end-to-end RAG answer quality.

## Project Structure

```text
backend/    FastAPI API, RAG pipeline, ingestion, evaluation scripts
frontend/   React/Vite chatbot interface
data/       Official source documents and prepared datasets
```

## Demo

On Windows, the fastest way to run the local demo is:

```bat
start_demo.cmd
```

This starts the FastAPI backend and the Vite frontend. After both services are running, open:

```text
http://localhost:5173
```

The frontend sends chat requests to the backend at:

```text
http://localhost:8000
```

For manual startup, run the backend and frontend separately:

```bat
run_backend_demo.cmd
run_frontend_demo.cmd
```

## Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` from `backend/.env.example` and set the required API keys.

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` by default and calls the backend at `http://localhost:8000`.
