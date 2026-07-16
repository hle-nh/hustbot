"""Prepare a cleaner canonical CSV corpus for retrieval.

Input:
    data/dataset.csv

Outputs:
    data/dataset_clean.csv      - all chunks, enriched with metadata + quality flags
    data/dataset_retrieval.csv  - chunks recommended for vector DB ingestion
    data/dataset_quality_report.md
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
INPUT_CSV = DATA_DIR / "dataset.csv"
CLEAN_CSV = DATA_DIR / "dataset_clean.csv"
RETRIEVAL_CSV = DATA_DIR / "dataset_retrieval.csv"
REPORT_PATH = DATA_DIR / "dataset_quality_report.md"


SOURCE_MAP = {
    "06_ Quy định ngoại ngữ từ K70_chính quy_final.pdf": {
        "document_type": "ngoai_ngu",
        "category": "Ngoại ngữ",
    },
    "5730_qd-dhbk-qcts.pdf": {
        "document_type": "tuyen_sinh",
        "category": "Tuyển sinh",
    },
    "909703909-So-Tay-Sinh-Vien-2025-1.pdf": {
        "document_type": "so_tay_sinh_vien",
        "category": "Sổ tay sinh viên",
    },
    "QCDT_2025_5445_QD-DHBK.pdf": {
        "document_type": "quy_che_dao_tao",
        "category": "Quy chế đào tạo",
    },
    "QD HOC PHI - 2025-2026-final.pdf": {
        "document_type": "hoc_phi",
        "category": "Học phí",
    },
    "quy_che_ctsv_2025.pdf": {
        "document_type": "cong_tac_sinh_vien",
        "category": "Công tác sinh viên",
    },
}

TOPIC_PATTERNS = {
    "hoc_phi": ["học phí", "tchp", "tín chỉ học phí"],
    "hoc_bong": ["học bổng", "khuyến khích học tập", "kkht"],
    "tuyen_sinh": ["tuyển sinh", "xét tuyển", "trúng tuyển", "sat", "act"],
    "dao_tao": ["đào tạo", "học phần", "đăng ký học", "tín chỉ"],
    "ngoai_ngu": ["ngoại ngữ", "ielts", "toeic", "tiếng anh"],
    "ky_tuc_xa": ["ký túc xá", "ktx"],
    "ehust": ["ehust", "office 365", "mật khẩu"],
    "lien_he": ["điện thoại", "email", "liên hệ", "024"],
    "dia_diem": ["địa chỉ", "cổng", "tòa", "nhà", "phòng"],
}

PREFIX_RE = re.compile(
    r"^\[Tài liệu:\s*(?P<source>.*?)\s*\|\s*trang\s*(?P<page>\d+)"
    r"(?:\s*\|\s*(?P<context>[^\]]+))?\]\s*",
    re.IGNORECASE | re.DOTALL,
)
ARTICLE_RE = re.compile(r"\b(Điều\s+\d+|Khoản\s+\d+|Mục\s+[\d.]+)\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})(?:\s*-\s*(20\d{2}))?\b")


def normalize_space(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_prefix(content: str) -> tuple[str | None, int | None, str | None, str]:
    match = PREFIX_RE.match(content)
    if not match:
        return None, None, None, content
    source = match.group("source")
    page = int(match.group("page"))
    context = match.group("context")
    body = content[match.end() :]
    return source, page, context, body.strip()


def infer_article(existing: object, prefix_context: str | None, body: str) -> str:
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    if prefix_context:
        match = ARTICLE_RE.search(prefix_context)
        if match:
            return match.group(1)
    match = ARTICLE_RE.search(body)
    if match:
        return match.group(1)
    return ""


def infer_year(source: str, body: str) -> str:
    source_match = YEAR_RE.search(source)
    if source_match:
        return source_match.group(0)
    body_match = YEAR_RE.search(body[:600])
    if body_match:
        return body_match.group(0)
    return ""


def infer_topics(text: str) -> str:
    lower = text.lower()
    topics = [
        topic
        for topic, terms in TOPIC_PATTERNS.items()
        if any(term in lower for term in terms)
    ]
    return ";".join(topics)


def is_low_information_table(body: str, word_count: int) -> bool:
    if "[BẢNG DỮ LIỆU" not in body:
        return False
    compact = re.sub(r"\s+", " ", body)
    alpha_tokens = re.findall(r"[A-Za-zÀ-ỹ]{3,}", compact)
    numeric_pairs = re.findall(r"\b\d+\s*:\s*\d+\b", compact)
    if word_count < 35:
        return True
    return len(numeric_pairs) >= 1 and len(alpha_tokens) < 12


def is_title_or_cover(body: str, page: int | None, char_count: int) -> bool:
    if page is None or page > 2 or char_count > 320:
        return False
    upper = body.upper()
    title_markers = ["QUY CHẾ", "QUY ĐỊNH", "QUYẾT ĐỊNH", "HÀ NỘI"]
    return sum(marker in upper for marker in title_markers) >= 2


def has_useful_contact_signal(text: str) -> bool:
    return bool(re.search(r"\b024[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}\b", text)) or "@" in text


def make_chunk_id(source: str, page: int | None, row_number: int, content: str) -> str:
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    safe_source = re.sub(r"[^A-Za-z0-9]+", "_", source).strip("_").lower()[:40]
    return f"{safe_source}_p{page or 0}_{row_number:04d}_{digest}"


def prepare() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input CSV: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)
    rows: list[dict] = []

    for row_number, row in enumerate(df.to_dict("records"), start=1):
        raw_content = normalize_space(str(row["content"]))
        prefix_source, prefix_page, prefix_context, body = parse_prefix(raw_content)
        source = str(row.get("source") or prefix_source or "").strip()
        page = int(row.get("page") or prefix_page or 0)
        source_info = SOURCE_MAP.get(source, {"document_type": "khac", "category": "Khác"})

        body = normalize_space(body)
        content = raw_content
        char_count = len(content)
        word_count = len(content.split())
        is_table = "[BẢNG DỮ LIỆU" in body
        low_info_table = is_low_information_table(body, word_count)
        title_or_cover = is_title_or_cover(body, page, char_count)
        too_short = char_count < 260 or word_count < 45
        too_long = char_count > 1600
        useful_contact = has_useful_contact_signal(content)

        quality_flags: list[str] = []
        if low_info_table:
            quality_flags.append("low_information_table")
        if title_or_cover:
            quality_flags.append("title_or_cover_page")
        if too_short:
            quality_flags.append("too_short")
        if too_long:
            quality_flags.append("too_long")

        include_for_retrieval = True
        if low_info_table:
            include_for_retrieval = False
        if title_or_cover:
            include_for_retrieval = False
        if too_short and not useful_contact and not is_table:
            include_for_retrieval = False

        clean_row = {
            "chunk_id": make_chunk_id(source, page, row_number, content),
            "source": source,
            "page": page,
            "document_type": source_info["document_type"],
            "category": source_info["category"],
            "section": "" if pd.isna(row.get("section")) else str(row.get("section")).strip(),
            "article": infer_article(row.get("article"), prefix_context, body),
            "year": infer_year(source, body),
            "is_table": is_table,
            "prefix_context": prefix_context or "",
            "topic_tags": infer_topics(content),
            "char_count": char_count,
            "word_count": word_count,
            "quality_flags": ";".join(quality_flags),
            "include_for_retrieval": include_for_retrieval,
            "content": content,
        }
        rows.append(clean_row)

    clean_df = pd.DataFrame(rows)
    clean_df.to_csv(CLEAN_CSV, index=False, encoding="utf-8-sig")
    retrieval_df = clean_df[clean_df["include_for_retrieval"]].copy()
    retrieval_df.to_csv(RETRIEVAL_CSV, index=False, encoding="utf-8-sig")
    write_report(clean_df, retrieval_df)
    return clean_df


def write_report(clean_df: pd.DataFrame, retrieval_df: pd.DataFrame) -> None:
    flag_counts = (
        clean_df["quality_flags"]
        .str.get_dummies(sep=";")
        .sum()
        .sort_values(ascending=False)
    )
    topic_counts = (
        clean_df["topic_tags"]
        .str.get_dummies(sep=";")
        .sum()
        .sort_values(ascending=False)
    )

    report = [
        "# Dataset Quality Report",
        "",
        f"Input: `{INPUT_CSV.relative_to(ROOT_DIR)}`",
        f"Clean output: `{CLEAN_CSV.relative_to(ROOT_DIR)}`",
        f"Retrieval output: `{RETRIEVAL_CSV.relative_to(ROOT_DIR)}`",
        "",
        "## Summary",
        "",
        f"- Original chunks: {len(clean_df)}",
        f"- Recommended retrieval chunks: {len(retrieval_df)}",
        f"- Excluded chunks: {len(clean_df) - len(retrieval_df)}",
        f"- Sources: {clean_df['source'].nunique()}",
        f"- Categories filled: {clean_df['category'].notna().sum()}/{len(clean_df)}",
        f"- Articles filled: {(clean_df['article'] != '').sum()}/{len(clean_df)}",
        f"- Sections filled: {(clean_df['section'] != '').sum()}/{len(clean_df)}",
        "",
        "## What Changed",
        "",
        "- Filled the empty `category` column from source-file mapping.",
        "- Added stable `chunk_id` values for auditing and deduplication.",
        "- Added `document_type`, `year`, `is_table`, `prefix_context`, `topic_tags`, "
        "`char_count`, `word_count`, `quality_flags`, and `include_for_retrieval`.",
        "- Flagged low-quality chunks such as short title pages, very short chunks, "
        "over-long chunks, and low-information table rows.",
        "- Produced a retrieval-only CSV that excludes chunks likely to hurt retrieval precision.",
        "- Added an optional CSV loader for the ingest pipeline via `DATASET_CSV`.",
        "",
        "## Chunks By Category",
        "",
        series_to_markdown(clean_df["category"].value_counts(), "category", "chunks"),
        "",
        "## Quality Flags",
        "",
        series_to_markdown(flag_counts, "flag", "chunks") if not flag_counts.empty else "No quality flags.",
        "",
        "## Topic Tags",
        "",
        series_to_markdown(topic_counts.head(20), "topic", "chunks") if not topic_counts.empty else "No topic tags.",
        "",
        "## Recommendation",
        "",
        "Use `dataset_clean.csv` as the canonical audited corpus. Use "
        "`dataset_retrieval.csv` when rebuilding the vector database, because it "
        "removes low-information table rows, title-only pages, and short chunks "
        "without useful contact signals.",
        "",
        "Rebuild Chroma from the cleaned retrieval corpus with:",
        "",
        "```powershell",
        "cd backend",
        "$env:DATASET_CSV='../data/dataset_retrieval.csv'",
        "python -m ingest.pipeline",
        "```",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def series_to_markdown(series: pd.Series, name_column: str, value_column: str) -> str:
    lines = [
        f"| {name_column} | {value_column} |",
        "|---|---:|",
    ]
    for key, value in series.items():
        lines.append(f"| {key} | {int(value)} |")
    return "\n".join(lines)


if __name__ == "__main__":
    prepared = prepare()
    print(f"Wrote {CLEAN_CSV}")
    print(f"Wrote {RETRIEVAL_CSV}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Rows: {len(prepared)}")
    print(f"Included: {int(prepared['include_for_retrieval'].sum())}")
