"""Retrieval evaluation script v4 -- benchmark-driven, no LLM calls."""
from __future__ import annotations

import os

# Must be set before any imports that trigger model loading
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("PYTHONUTF8", "1")

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

# Allow imports from the backend root (parent of evaluation/)
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.retriever import retrieve

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BENCHMARK_PATH = Path(
    r"C:\Users\hoang le\OneDrive - Hanoi University of Science and Technology"
    r"\Desktop\hustbot\benchmark_rag_v4.xlsx"
)
OUTPUT_PATH = Path(
    r"C:\Users\hoang le\OneDrive - Hanoi University of Science and Technology"
    r"\Desktop\hustbot\backend\evaluation\results\retrieval_eval_v4.json"
)

# ---------------------------------------------------------------------------
# Column name constants matching the actual Excel file column headers.
# The file uses full parenthetical names e.g. "Phan loai (Category)".
# ---------------------------------------------------------------------------
COL_ID = "Ma ID"
COL_CATEGORY = "Phan loai (Category)"
COL_COMPLEXITY = "Muc do (Complexity)"
COL_INTENT = "Muc dich kiem thu (Intent/Goal)"
COL_QUESTION = "Cau hoi dau vao (User Prompt)"
COL_GROUND_TRUTH = "Cau tra loi chuan (Ground Truth / Expected Output)"

# We also keep a flag so the column lookup falls back to positional if needed.
# Excel column order (0-indexed): ID=0, Category=1, Complexity=2, Intent=3,
# Question=4, GroundTruth=5
COL_IDX_QUESTION = 4
COL_IDX_GROUND_TRUTH = 5
COL_IDX_CATEGORY = 1
COL_IDX_COMPLEXITY = 2
COL_IDX_ID = 0

# Category value that signals out-of-scope questions (Vietnamese)
OUT_OF_SCOPE_CATEGORY = "ngoai scope"

# Vietnamese stopwords to exclude from key-term extraction
VIET_STOPWORDS = {
    "la", "cua", "va", "hoac", "co", "khong", "duoc", "trong", "tren",
    "duoi", "theo", "voi", "tu", "den", "cho", "ve", "tai", "cac", "mot",
    "nhung", "nay", "do", "khi", "thi", "ma", "nen", "vi", "nhung",
    "cung", "da", "se", "dang", "bi", "con", "neu", "nhu", "sau", "truoc",
    "qua", "lai", "ra", "vao", "len", "xuong", "nguoi", "sinh", "vien",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """NFC normalise + lowercase + collapse whitespace."""
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def get_col(row_dict: dict, name: str, positional_idx: int, all_values: list) -> str:
    """Return cell value preferring named key, falling back to positional."""
    val = row_dict.get(name)
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        # Try positional fallback
        if 0 <= positional_idx < len(all_values):
            val = all_values[positional_idx]
    return "" if val is None or str(val).strip().lower() == "nan" else str(val).strip()


def extract_key_terms(ground_truth: str) -> tuple[list[str], list[str]]:
    """Return (numbers, key_words) extracted from the ground truth string.

    numbers   -- every numeric token (may contain commas/dots as thousands sep)
    key_words -- tokens longer than 3 chars that are not Vietnamese stopwords
    """
    gt_norm = normalize(ground_truth)

    # All numeric tokens (prices, credit counts, thresholds, etc.)
    numbers = re.findall(r"\d+(?:[.,]\d+)?", gt_norm)

    # Split on whitespace, commas, semicolons, slashes, parentheses, colons
    tokens = re.split(r"[\s,;/():\-]+", gt_norm)
    key_words = [
        t for t in tokens
        if len(t) > 3 and t not in VIET_STOPWORDS and not re.fullmatch(r"\d+", t)
    ]

    return numbers, key_words


def chunk_passes(chunk_text: str, numbers: list[str], key_words: list[str]) -> bool:
    """A chunk passes if it contains at least one number AND one key word from GT.

    Fallback: if GT has no numbers -> keyword-only; if no keywords -> number-only.
    """
    norm_chunk = normalize(chunk_text)

    has_number = any(num in norm_chunk for num in numbers) if numbers else True
    has_keyword = any(kw in norm_chunk for kw in key_words) if key_words else True

    return has_number and has_keyword


def first_match_rank(docs: list[Any], numbers: list[str], key_words: list[str]) -> int | None:
    """Return 1-based rank of first chunk that passes, or None."""
    for rank, doc in enumerate(docs, start=1):
        if chunk_passes(doc.page_content, numbers, key_words):
            return rank
    return None


# ---------------------------------------------------------------------------
# Per-question evaluation
# ---------------------------------------------------------------------------

def evaluate_question(row_dict: dict, row_values: list) -> dict:
    qid = get_col(row_dict, COL_ID, COL_IDX_ID, row_values)
    category = get_col(row_dict, COL_CATEGORY, COL_IDX_CATEGORY, row_values)
    complexity = get_col(row_dict, COL_COMPLEXITY, COL_IDX_COMPLEXITY, row_values)
    question = get_col(row_dict, COL_QUESTION, COL_IDX_QUESTION, row_values)
    ground_truth = get_col(row_dict, COL_GROUND_TRUTH, COL_IDX_GROUND_TRUTH, row_values)

    base = {
        "id": qid,
        "category": category,
        "complexity": complexity,
        "question": question,
    }

    # ------------------------------------------------------------------
    # Out-of-scope: only check that retrieve returns < 3 results
    # ------------------------------------------------------------------
    cat_norm = normalize(category)
    if OUT_OF_SCOPE_CATEGORY in cat_norm or "ngoai scope" in cat_norm:
        try:
            docs, web_used = retrieve(question, use_reranker=True, web_search_override=False)
        except Exception as exc:
            return {**base, "status": "error", "error": str(exc)}

        low_result_check = len(docs) < 3
        return {
            **base,
            "status": "out_of_scope",
            "low_result_check": low_result_check,
            "num_results": len(docs),
            "web_search_used": web_used,
        }

    # ------------------------------------------------------------------
    # In-scope: full recall evaluation
    # ------------------------------------------------------------------
    numbers, key_words = extract_key_terms(ground_truth)

    try:
        docs, web_used = retrieve(question, use_reranker=True, web_search_override=False)
    except Exception as exc:
        return {**base, "status": "error", "error": str(exc)}

    top6 = docs[:6]

    rank = first_match_rank(top6, numbers, key_words)

    passed_at_1 = rank is not None and rank <= 1
    passed_at_3 = rank is not None and rank <= 3
    passed_at_6 = rank is not None and rank <= 6
    mrr = (1.0 / rank) if rank is not None else 0.0

    return {
        **base,
        "status": "evaluated",
        "ground_truth": ground_truth,
        "extracted_numbers": numbers,
        "extracted_keywords": key_words,
        "first_match_rank": rank,
        "passed_at_1": passed_at_1,
        "passed_at_3": passed_at_3,
        "passed_at_6": passed_at_6,
        "mrr": mrr,
        "web_search_used": web_used,
        "retrieved": [
            {
                "rank": r,
                "source": doc.metadata.get("source"),
                "page": doc.metadata.get("page"),
                "table_row": doc.metadata.get("table_row"),
                "preview": doc.page_content[:300],
                "passes": chunk_passes(doc.page_content, numbers, key_words),
            }
            for r, doc in enumerate(top6, start=1)
        ],
    }


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def recall_by_field(results: list[dict], field: str) -> dict[str, float]:
    groups: dict[str, list[bool]] = {}
    for r in results:
        if r.get("status") != "evaluated":
            continue
        key = str(r.get(field, "unknown"))
        groups.setdefault(key, []).append(r.get("passed_at_6", False))
    return {k: safe_mean([float(v) for v in vs]) for k, vs in sorted(groups.items())}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"[INFO] Reading benchmark: {BENCHMARK_PATH}", flush=True)
    try:
        df = pd.read_excel(BENCHMARK_PATH, engine="openpyxl")
    except Exception as exc:
        print(f"[ERROR] Cannot read benchmark file: {exc}", file=sys.stderr)
        return 1

    print(f"[INFO] Loaded {len(df)} rows. Columns: {list(df.columns)}", flush=True)

    # Build a column name -> index mapping for positional fallback
    col_list = list(df.columns)

    results: list[dict] = []
    errors: list[str] = []

    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        row_values = list(row)

        # Use positional fallback for question field to decide whether to skip
        question_val = get_col(row_dict, COL_QUESTION, COL_IDX_QUESTION, row_values)
        if not question_val:
            print(f"[SKIP] Row {idx}: empty question", flush=True)
            continue

        qid_val = get_col(row_dict, COL_ID, COL_IDX_ID, row_values)
        print(f"[{idx + 1}/{len(df)}] Evaluating {qid_val} ...", flush=True)

        result = evaluate_question(row_dict, row_values)
        results.append(result)

        if result.get("status") == "error":
            errors.append(f"{qid_val}: {result.get('error')}")
            print(f"  [ERROR] {result.get('error')}", flush=True)
        elif result.get("status") == "out_of_scope":
            lrc = result.get("low_result_check", False)
            print(f"  [OUT-OF-SCOPE] num_results={result.get('num_results')}, low_result_check={lrc}", flush=True)
        else:
            r6 = result.get("passed_at_6", False)
            rank = result.get("first_match_rank")
            print(f"  [OK] passed@6={r6}, first_match_rank={rank}", flush=True)

    # ------------------------------------------------------------------
    # Aggregate metrics (in-scope only)
    # ------------------------------------------------------------------
    in_scope = [r for r in results if r.get("status") == "evaluated"]
    out_of_scope = [r for r in results if r.get("status") == "out_of_scope"]
    error_rows = [r for r in results if r.get("status") == "error"]

    n = len(in_scope)

    recall_at_1 = safe_mean([float(r.get("passed_at_1", False)) for r in in_scope])
    recall_at_3 = safe_mean([float(r.get("passed_at_3", False)) for r in in_scope])
    recall_at_6 = safe_mean([float(r.get("passed_at_6", False)) for r in in_scope])
    mrr = safe_mean([r.get("mrr", 0.0) for r in in_scope])

    oos_passed = sum(1 for r in out_of_scope if r.get("low_result_check", False))
    oos_total = len(out_of_scope)

    recall_by_cat = recall_by_field(results, "category")
    recall_by_complexity = recall_by_field(results, "complexity")

    report = {
        "summary": {
            "in_scope_total": n,
            "out_of_scope_total": oos_total,
            "out_of_scope_low_result_pass": oos_passed,
            "errors": len(error_rows),
            "recall_at_1": round(recall_at_1, 4),
            "recall_at_3": round(recall_at_3, 4),
            "recall_at_6": round(recall_at_6, 4),
            "mrr": round(mrr, 4),
        },
        "recall_at_6_by_category": {k: round(v, 4) for k, v in recall_by_cat.items()},
        "recall_at_6_by_complexity": {k: round(v, 4) for k, v in recall_by_complexity.items()},
        "error_list": errors,
        "results": results,
    }

    # ------------------------------------------------------------------
    # Save JSON
    # ------------------------------------------------------------------
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[INFO] Results written to: {OUTPUT_PATH}", flush=True)

    # ------------------------------------------------------------------
    # Print summary table
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RETRIEVAL EVALUATION v4 -- SUMMARY")
    print("=" * 60)
    print(f"  In-scope questions evaluated : {n}")
    print(f"  Out-of-scope questions        : {oos_total}  (low-result pass: {oos_passed}/{oos_total})")
    print(f"  Errors                        : {len(error_rows)}")
    print()
    print(f"  Recall@1  : {recall_at_1:.2%}")
    print(f"  Recall@3  : {recall_at_3:.2%}")
    print(f"  Recall@6  : {recall_at_6:.2%}")
    print(f"  MRR       : {mrr:.4f}")
    print()
    print("  Recall@6 by category:")
    for cat, val in recall_by_cat.items():
        print(f"    {cat:<40s} {val:.2%}")
    print()
    print("  Recall@6 by complexity:")
    for cplx, val in recall_by_complexity.items():
        print(f"    {cplx:<40s} {val:.2%}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
