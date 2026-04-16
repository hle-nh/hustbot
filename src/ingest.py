# src/ingest.py

import os
import re
import fitz                          # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

DATA_DIR   = os.getenv("DATA_DIR",   "./data")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE",   500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 75))


# ==============================================
# BƯỚC 1: LOAD PDF
# ==============================================

import pdfplumber

def load_pdf(filepath: str) -> list[Document]:
    docs = []
    filename = Path(filepath).name

    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Thử extract bảng trước
            tables = page.extract_tables()
            table_text = ""
            if tables:
                for table in tables:
                    for row in table:
                        # Lọc ô None, ghép thành dòng
                        clean_row = [cell or "" for cell in row]
                        table_text += " | ".join(clean_row) + "\n"

            # Extract text thường
            plain_text = page.extract_text() or ""

            # Ghép lại — bảng được đặt cuối để LLM dễ parse
            combined = plain_text
            if table_text:
                combined += "\n\n[BẢNG DỮ LIỆU]\n" + table_text

            if len(combined.strip()) < 50:
                continue

            docs.append(Document(
                page_content=combined,
                metadata={
                    "source":      filename,
                    "page":        page_num + 1,
                    "total_pages": len(pdf.pages),
                    "source_page": f"{filename}::p{page_num + 1}",
                }
            ))

    print(f"  ✅ {filename}: {len(docs)} trang")
    return docs


def load_all_pdfs(data_dir: str) -> list[Document]:
    """Quét toàn bộ thư mục data/, load tất cả file PDF."""
    all_docs = []
    pdf_files = list(Path(data_dir).rglob("*.pdf"))  # tìm cả trong thư mục con

    if not pdf_files:
        raise FileNotFoundError(f"Không tìm thấy PDF nào trong {data_dir}")

    print(f"\n📂 Tìm thấy {len(pdf_files)} file PDF:")
    for pdf_path in pdf_files:
        docs = load_pdf(str(pdf_path))
        all_docs.extend(docs)

    print(f"\n📄 Tổng cộng: {len(all_docs)} trang")
    return all_docs


# ==============================================
# BƯỚC 2: CLEAN TEXT
# ==============================================

def clean_text(text: str) -> str:
    """
    Làm sạch text trước khi chunk.
    Loại bỏ header/footer lặp lại, khoảng trắng thừa.
    """
    # Xóa header/footer phổ biến trong tài liệu HUST
    noise_patterns = [
        r"Trường Đại học Bách khoa Hà Nội",
        r"HANOI UNIVERSITY OF SCIENCE AND TECHNOLOGY",
        r"Trang\s*\d+\s*/\s*\d+",       # "Trang 1/20"
        r"^\s*\d+\s*$",                  # số trang đứng một mình
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)

    # Chuẩn hóa khoảng trắng
    text = re.sub(r"\n{3,}", "\n\n", text)   # nhiều dòng trống → 2 dòng
    text = re.sub(r"[ \t]+", " ", text)       # nhiều space → 1 space
    text = text.strip()

    return text


# ==============================================
# BƯỚC 3: CHUNK
# ==============================================

def split_documents(docs: list[Document]) -> list[Document]:
    """
    Chia nhỏ document thành các chunk.
    Giữ nguyên metadata gốc (source, page) cho mỗi chunk.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n\n",    # ưu tiên cắt theo đoạn văn
            "\n",      # sau đó theo dòng
            ".",       # sau đó theo câu
            " ",       # cuối cùng theo từ
        ],
        length_function=len,
    )

    # Clean text trước khi split
    for doc in docs:
        doc.page_content = clean_text(doc.page_content)

    # Bỏ doc rỗng sau khi clean
    docs = [d for d in docs if len(d.page_content.strip()) > 50]

    chunks = splitter.split_documents(docs)
    print(f"\n✂️  Tổng chunks sau khi split: {len(chunks)}")

    # Kiểm tra nhanh
    avg_len = sum(len(c.page_content) for c in chunks) / len(chunks)
    print(f"📏 Độ dài chunk trung bình: {avg_len:.0f} ký tự")

    return chunks


# ==============================================
# BƯỚC 4: EMBED + LƯU CHROMADB
# ==============================================

def embed_and_store(chunks: list[Document]) -> Chroma:
    """
    Chuyển chunks thành vector bằng BGE-M3,
    sau đó lưu vào ChromaDB local.
    """
    print("\n⏳ Đang tải model BGE-M3 (lần đầu ~5 phút)...")

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={
            "device": os.getenv("DEVICE", "cpu")  # đổi "cuda" nếu có GPU
        },
        encode_kwargs={
            "normalize_embeddings": True,   # cần thiết cho cosine similarity
            "batch_size": 32                # giảm xuống 16 nếu RAM yếu
        }
    )

    print(f"💾 Đang embed và lưu vào ChromaDB tại: {CHROMA_DIR}")

    # Chia batch để hiển thị progress bar
    batch_size = 100
    vectorstore = None

    for i in tqdm(range(0, len(chunks), batch_size), desc="Embedding"):
        batch = chunks[i : i + batch_size]

        if vectorstore is None:
            # Lần đầu: tạo mới vectorstore
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                persist_directory=CHROMA_DIR,
                collection_name="hust_regulations"
            )
        else:
            # Các lần sau: thêm vào vectorstore đã có
            vectorstore.add_documents(batch)

    print(f"\n✅ Hoàn tất! Đã lưu {len(chunks)} chunks vào ChromaDB")
    return vectorstore


# ==============================================
# MAIN
# ==============================================

def main():
    print("=" * 50)
    print("  HUST RAG — XÂY DỰNG VECTOR DATABASE")
    print("=" * 50)

    # Kiểm tra thư mục data tồn tại
    if not Path(DATA_DIR).exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục: {DATA_DIR}")

    # Chạy pipeline
    docs   = load_all_pdfs(DATA_DIR)       # Bước 1
    chunks = split_documents(docs)          # Bước 2 + 3
    embed_and_store(chunks)                 # Bước 4

    print("\n🎉 Vector database đã sẵn sàng!")
    print(f"   Vị trí: {CHROMA_DIR}/")
    print("   Bước tiếp theo: chạy main.py để hỏi đáp")


if __name__ == "__main__":
    main()
