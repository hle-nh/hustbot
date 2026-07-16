"""Load preprocessed retrieval chunks from a CSV corpus."""
from __future__ import annotations

import csv
from pathlib import Path

from langchain_core.documents import Document


METADATA_COLUMNS = {
    "chunk_id",
    "source",
    "page",
    "document_type",
    "category",
    "section",
    "article",
    "year",
    "is_table",
    "prefix_context",
    "topic_tags",
    "char_count",
    "word_count",
    "quality_flags",
}


def _coerce_metadata_value(value: str) -> str | int | bool:
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def load_dataset_csv(csv_path: str | Path) -> list[Document]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset CSV not found: {path}")

    docs: list[Document] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "content" not in reader.fieldnames:
            raise ValueError("Dataset CSV must contain a 'content' column")

        for row in reader:
            content = (row.get("content") or "").strip()
            if not content:
                continue

            include_value = (row.get("include_for_retrieval") or "true").strip().lower()
            if include_value == "false":
                continue

            metadata = {
                key: _coerce_metadata_value(row[key])
                for key in METADATA_COLUMNS
                if key in row and row[key] not in (None, "")
            }
            docs.append(Document(page_content=content, metadata=metadata))

    print(f"  Loaded {len(docs)} chunks from {path}")
    return docs
