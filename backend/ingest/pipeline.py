"""
Ingest pipeline — main entry point.

Chạy để rebuild vector database:
  cd backend/
  python -m ingest.pipeline

Hoặc với venv:
  python ingest/pipeline.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Load .env từ thư mục backend/
load_dotenv(Path(__file__).parent.parent / ".env")

from ingest.chunker import split_documents
from ingest.csv_loader import load_dataset_csv
from ingest.loader import load_all_pdfs

DATA_DIR   = os.getenv("DATA_DIR",   "../data")
CHROMA_DIR = os.getenv("CHROMA_DIR", "../chroma_db")
DEVICE     = os.getenv("DEVICE", "cpu")
DATASET_CSV = os.getenv("DATASET_CSV", "")


def embed_and_store(chunks):
    print("\n⏳ Đang load model BGE-M3...")
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={"device": DEVICE},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )

    print(f"💾 Đang embed và lưu vào: {CHROMA_DIR}")
    existing_store = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name="hust_regulations",
    )
    if existing_store._collection.count() > 0:
        print("🧹 Xóa collection cũ để tránh trùng lặp chunks...")
        existing_store.delete_collection()

    batch_size = 100
    vectorstore = None

    for i in tqdm(range(0, len(chunks), batch_size), desc="Embedding"):
        batch = chunks[i: i + batch_size]
        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                persist_directory=CHROMA_DIR,
                collection_name="hust_regulations",
            )
        else:
            vectorstore.add_documents(batch)

    print(f"\n✅ Đã lưu {len(chunks)} chunks vào ChromaDB")
    return vectorstore


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 55)
    print("  HUST RAG — XÂY DỰNG VECTOR DATABASE v2")
    print("=" * 55)
    print(f"  DATA_DIR:   {DATA_DIR}")
    print(f"  CHROMA_DIR: {CHROMA_DIR}")
    print(f"  DEVICE:     {DEVICE}")
    if DATASET_CSV:
        print(f"  DATASET_CSV: {DATASET_CSV}")
    print("=" * 55)

    if DATASET_CSV:
        chunks = load_dataset_csv(DATASET_CSV)
    elif not Path(DATA_DIR).exists():
        print(f"❌ Không tìm thấy thư mục: {DATA_DIR}")
        sys.exit(1)
    else:
        docs = load_all_pdfs(DATA_DIR)
        chunks = split_documents(docs)

    embed_and_store(chunks)

    print("\n🎉 Vector database đã sẵn sàng!")
    print(f"   Vị trí: {CHROMA_DIR}/")
    print("\n   Bước tiếp theo:")
    print("   1. docker compose up -d")
    print("   2. alembic upgrade head")
    print("   3. uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
