"""Text cleaning + chunking — cải thiện từ src/ingest.py.

Thay đổi so với v1:
- CHUNK_SIZE: 700 → 850, CHUNK_OVERLAP: 150 → 300
- Enrich Metadata: đính kèm [Tài liệu | Chương | Điều] vào đầu mỗi chunk
  để LLM không bị nhầm lẫn ngữ cảnh giữa các hệ đào tạo khác nhau.
"""
from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE    = int(__import__("os").getenv("CHUNK_SIZE",    "850"))
CHUNK_OVERLAP = int(__import__("os").getenv("CHUNK_OVERLAP", "300"))

# ── Cleaner ───────────────────────────────────────────────────

NOISE_PATTERNS = [
    r"Trường Đại học Bách khoa Hà Nội",
    r"HANOI UNIVERSITY OF SCIENCE AND TECHNOLOGY",
    r"Trang\s*\d+\s*/\s*\d+",    # "Trang 1/20"
    r"^\s*\d+\s*$",              # số trang đứng một mình
    r"©.*?HUST",                 # copyright
]


def clean_text(text: str) -> str:
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)    # nhiều dòng trống → 2
    text = re.sub(r"[ \t]+", " ", text)       # nhiều space → 1
    text = re.sub(r"\n ", "\n", text)          # khoảng trắng đầu dòng
    return text.strip()


# ── Metadata prefix builder ───────────────────────────────────

_DIEU_RE    = re.compile(r"(Điều\s+\d+[^\n\.]*)", re.IGNORECASE)
_CHUONG_RE  = re.compile(r"(Chương\s+[IVXLCDM\d]+[^\n]*)", re.IGNORECASE)
_MUC_RE     = re.compile(r"(Mục\s+\d+[^\n]*)", re.IGNORECASE)


def _extract_structural_context(text: str) -> str:
    """
    Trích xuất ngữ cảnh cấu trúc từ nội dung chunk để đính kèm làm tiêu đề.
    Ưu tiên: Điều > Mục > Chương.
    """
    m = _DIEU_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    m = _MUC_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    m = _CHUONG_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    return ""


def enrich_chunk(doc: Document) -> Document:
    """
    Thêm prefix [Tài liệu: xxx | Điều: yyy] vào đầu mỗi chunk.
    Giúp LLM biết chunk đang thuộc điều khoản nào, tránh nhầm lẫn chéo.
    """
    source  = doc.metadata.get("source", "")
    page    = doc.metadata.get("page", "")
    context = _extract_structural_context(doc.page_content)

    parts = []
    if source:
        parts.append(f"Tài liệu: {source}")
    if page:
        parts.append(f"trang {page}")
    if context:
        parts.append(context)

    if parts:
        prefix = "[" + " | ".join(parts) + "]\n"
        doc.page_content = prefix + doc.page_content
    return doc


# ── Chunker ───────────────────────────────────────────────────

def split_documents(docs: list[Document]) -> list[Document]:
    """
    Chunk_size=850, overlap=300.
    Tách tài liệu thông thường và tài liệu bảng biểu:
    - Tài liệu thông thường: split thành nhiều chunks nhỏ hơn.
    - Tài liệu bảng biểu (is_table = True): giữ nguyên không split để bảo toàn cấu trúc bảng.
    Sau đó enrich mỗi chunk với prefix cấu trúc.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "],
        length_function=len,
    )

    non_tables = [d for d in docs if not d.metadata.get("is_table", False)]
    tables = [d for d in docs if d.metadata.get("is_table", False)]

    # 1. Xử lý tài liệu thông thường (clean + split)
    cleaned_non_tables = []
    for doc in non_tables:
        doc.page_content = clean_text(doc.page_content)
        if len(doc.page_content.strip()) > 50:
            cleaned_non_tables.append(doc)
    chunks = splitter.split_documents(cleaned_non_tables)

    # 2. Xử lý tài liệu bảng biểu (clean, KHÔNG split)
    for doc in tables:
        doc.page_content = clean_text(doc.page_content)
        chunks.append(doc)

    # Enrich metadata prefix cho mỗi chunk
    chunks = [enrich_chunk(c) for c in chunks]

    if chunks:
        avg = sum(len(c.page_content) for c in chunks) / len(chunks)
        print(f"✂️  {len(chunks)} chunks | avg {avg:.0f} ký tự (sau enrich)")

    return chunks
