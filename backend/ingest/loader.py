"""
Ingest pipeline — cải thiện từ src/ingest.py.

Thay đổi:
- chunk_size=700 (cũ: 500), overlap=150 (cũ: 75)
- Metadata phong phú hơn: section, article, year, document_type
- Tách thành: loader / cleaner / chunker / pipeline
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

import pdfplumber

from langchain_core.documents import Document

DATA_DIR = os.getenv("DATA_DIR", "./data")


# ── Metadata patterns ─────────────────────────────────────────

# Nhận diện loại tài liệu từ tên file
DOCUMENT_TYPE_MAP = {
    "quy_che": "dao_tao",
    "quychе": "dao_tao",
    "hoc_phi": "hoc_phi",
    "ngoai_ngu": "ngoai_ngu",
    "ren_luyen": "ren_luyen",
    "hoc_bong": "hoc_bong",
}

# Nhận diện điều khoản: "Điều 19", "Khoản 2", "Mục 3.1"
ARTICLE_RE = re.compile(
    r"(Điều\s+\d+|Khoản\s+\d+|Mục\s+[\d.]+)",
    re.IGNORECASE | re.UNICODE,
)

# Nhận diện section headers
SECTION_RE = re.compile(
    r"^(CHƯƠNG|PHẦN|MỤC)\s+[IVX\d]+[.:]?\s+(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def detect_document_type(filename: str) -> str:
    name_lower = filename.lower().replace(" ", "_")
    for key, doc_type in DOCUMENT_TYPE_MAP.items():
        if key in name_lower:
            return doc_type
    return "khac"


def extract_year(filename: str) -> int | None:
    """Trích xuất năm từ tên file, ví dụ 'QCDT_2025.pdf' → 2025."""
    m = re.search(r"(20\d{2})", filename)
    if m:
        return int(m.group(1))
    return None


def extract_article(text: str) -> str | None:
    """Tìm Điều/Khoản đầu tiên trong đoạn text."""
    m = ARTICLE_RE.search(text)
    if m:
        return m.group(1)
    return None


def extract_section(text: str) -> str | None:
    """Tìm tên section từ header."""
    m = SECTION_RE.search(text)
    if m:
        return m.group(2).strip()[:80]
    return None


def _clean_cell(value: object | None) -> str:
    """Normalize text extracted from a PDF table cell."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _forward_fill_merged_cells(
    table: Sequence[Sequence[object | None]],
) -> list[list[str]]:
    """Fill vertically merged cells that pdfplumber returns as None."""
    if not table:
        return []

    width = max(len(row) for row in table)
    previous = [""] * width
    result: list[list[str]] = []

    for row_index, row in enumerate(table):
        filled: list[str] = []
        for column_index in range(width):
            raw_value = row[column_index] if column_index < len(row) else None
            value = _clean_cell(raw_value)
            if row_index > 0 and raw_value is None:
                if column_index >= 2 and filled[-1]:
                    value = filled[-1]
                elif previous[column_index]:
                    value = previous[column_index]
            if value:
                previous[column_index] = value
            filled.append(value)
        result.append(filled)

    return result


def _find_table_context(
    plain_text: str,
    first_header: str,
    occurrence_index: int,
    max_lines: int = 8,
) -> str:
    """Return nearby text before a table to preserve its program scope."""
    if not plain_text or not first_header:
        return ""

    header_prefix = _clean_cell(first_header).lower()
    lines = plain_text.splitlines()
    matching_line_indexes = [
        index
        for index, line in enumerate(lines)
        if _clean_cell(line).lower().startswith(header_prefix)
    ]
    if not matching_line_indexes:
        return ""

    line_index = matching_line_indexes[
        min(occurrence_index, len(matching_line_indexes) - 1)
    ]
    preceding_lines = [
        _clean_cell(line)
        for line in lines[:line_index][-max_lines:]
        if _clean_cell(line)
    ]
    marker_indexes = [
        index
        for index, line in enumerate(preceding_lines)
        if re.match(r"^\d+\)", line)
        or "mức học phí đối với" in line.lower()
    ]
    if marker_indexes:
        preceding_lines = preceding_lines[marker_indexes[-1]:]
    else:
        preceding_lines = preceding_lines[-4:]
    context_lines = preceding_lines
    return " ".join(context_lines)


def _detect_table_unit(
    plain_text: str,
    headers: Sequence[str],
    document_type: str = "",
) -> str:
    """Attach explicit units to numeric table values when the page defines one."""
    header_text = " ".join(headers).lower()
    page_text = plain_text.lower()
    is_fee_table = (
        "mức học phí" in header_text
        or (
            document_type == "hoc_phi"
            and "mức học phí" in page_text
        )
    )
    if not is_fee_table:
        return ""
    if "nghìn đồng" in page_text:
        return "nghìn đồng/TCHP"
    if "đồng/tchp" in page_text:
        return "đồng/TCHP"
    if document_type == "hoc_phi":
        return "nghìn đồng/TCHP"
    return ""


def table_to_row_documents(
    table: Sequence[Sequence[object | None]],
    *,
    plain_text: str,
    base_metadata: dict,
    table_index: int,
) -> list[Document]:
    """Convert a PDF table into self-contained documents, one per data row."""
    normalized = _forward_fill_merged_cells(table)
    if len(normalized) < 2:
        return []

    headers = [
        cell or f"Cột {index + 1}"
        for index, cell in enumerate(normalized[0])
    ]
    table_context = _find_table_context(
        plain_text,
        headers[0],
        occurrence_index=table_index - 1,
    )
    unit = _detect_table_unit(
        plain_text,
        headers,
        document_type=str(base_metadata.get("document_type", "")),
    )
    documents: list[Document] = []

    for row_index, row in enumerate(normalized[1:], start=1):
        fields = [
            f"{header}: {value}"
            for header, value in zip(headers, row)
            if value
        ]
        if not fields:
            continue

        content_parts = ["[BẢNG DỮ LIỆU - MỘT HÀNG]"]
        if table_context:
            content_parts.append(f"Ngữ cảnh bảng: {table_context}")
        if unit:
            content_parts.append(f"Đơn vị: {unit}")
        content_parts.extend(fields)

        meta = base_metadata.copy()
        meta.update({
            "is_table": True,
            "table_index": table_index,
            "table_row": row_index,
            "table_headers": " | ".join(headers),
        })
        if table_context:
            meta["table_context"] = table_context[:500]
        if unit:
            meta["unit"] = unit

        documents.append(
            Document(
                page_content="\n".join(content_parts),
                metadata=meta,
            )
        )

    return documents


# ── PDF Loader ────────────────────────────────────────────────

def load_pdf(filepath: str) -> list[Document]:
    """
    Load PDF với pdfplumber.
    Trích xuất text và tạo document riêng biệt cho mỗi bảng dữ liệu để giữ nguyên cấu trúc.
    """
    filename = Path(filepath).name
    doc_type = detect_document_type(filename)
    year = extract_year(filename)
    docs = []

    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            plain_text = page.extract_text() or ""

            # Base metadata cho trang
            base_metadata = {
                "source":        filename,
                "page":          page_num,
                "total_pages":   len(pdf.pages),
                "document_type": doc_type,
                "is_table":      False,
            }
            if year:
                base_metadata["year"] = year

            tables = page.extract_tables()
            if tables:
                # 1. Thêm plain text của trang
                if len(plain_text.strip()) >= 50:
                    section = extract_section(plain_text)
                    article = extract_article(plain_text)
                    meta = base_metadata.copy()
                    if section: meta["section"] = section
                    if article: meta["article"] = article
                    docs.append(Document(page_content=plain_text, metadata=meta))

                # 2. Tạo document riêng cho mỗi bảng (kèm theo plain_text làm ngữ cảnh)
                for t_idx, table in enumerate(tables, 1):
                    docs.extend(
                        table_to_row_documents(
                            table,
                            plain_text=plain_text,
                            base_metadata=base_metadata,
                            table_index=t_idx,
                        )
                    )
            else:
                if len(plain_text.strip()) >= 50:
                    section = extract_section(plain_text)
                    article = extract_article(plain_text)
                    meta = base_metadata.copy()
                    if section: meta["section"] = section
                    if article: meta["article"] = article
                    docs.append(Document(page_content=plain_text, metadata=meta))

    print(f"  ✅ {filename}: {len(docs)} tài liệu trang/bảng")
    return docs


def load_all_pdfs(data_dir: str = DATA_DIR) -> list[Document]:
    pdf_files = list(Path(data_dir).rglob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"Không tìm thấy PDF nào trong {data_dir}")

    print(f"\n📂 Tìm thấy {len(pdf_files)} file PDF:")
    all_docs = []
    for pdf_path in pdf_files:
        docs = load_pdf(str(pdf_path))
        all_docs.extend(docs)

    print(f"\n📄 Tổng cộng: {len(all_docs)} trang")
    return all_docs
