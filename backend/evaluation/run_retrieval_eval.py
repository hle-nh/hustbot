"""Targeted retrieval regression checks that do not call an LLM."""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.retriever import retrieve


CASES = [
    {
        "id": "BM_064",
        "question": (
            "Học phí một tín chỉ học phí của ngành Kỹ thuật Cơ điện tử, "
            "Khoa học máy tính hệ chuẩn năm học 2025-2026 là bao nhiêu?"
        ),
        "required_groups": [
            ["cơ điện tử", "khoa học máy tính", "630"],
        ],
    },
    {
        "id": "BM_065",
        "question": (
            "Em học ngành Toán tin / Quản trị kinh doanh / Kế toán hệ đào tạo "
            "chuẩn thì học phí kỳ này tính bao nhiêu tiền một tín chỉ học phí?"
        ),
        "required_groups": [
            ["toán tin", "quản trị kinh doanh", "kế toán", "600"],
        ],
    },
    {
        "id": "BM_066",
        "question": (
            "Em học chương trình tiên tiến Global ICT, các môn chuyên ngành học "
            "phí cao rồi, còn các môn như Triết học, Thể dục, Quân sự thì tính "
            "giá thế nào?"
        ),
        "required_groups": [
            ["global ict", "llct", "gdtc", "gdqp-an", "700"],
        ],
    },
    {
        "id": "BM_067",
        "question": (
            "Sinh viên học các lớp ngoại ngữ cơ bản trình độ tiếng Anh A1.1 "
            "hoặc tiếng Nhật 2 tại trường phải đóng học phí bao nhiêu?"
        ),
        "required_groups": [
            ["a1.1", "tiếng anh", "725"],
            ["tiếng nhật 2", "855"],
        ],
    },
]


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).lower()
    return " ".join(normalized.split())


def evaluate_case(case: dict, top_k: int) -> dict:
    docs, web_search_used = retrieve(
        case["question"],
        use_reranker=True,
        web_search_override=False,
        category="academic",
    )
    docs = docs[:top_k]
    normalized_docs = [normalize(doc.page_content) for doc in docs]

    group_results = []
    for required_terms in case["required_groups"]:
        matched_rank = next(
            (
                rank
                for rank, content in enumerate(normalized_docs, start=1)
                if all(normalize(term) in content for term in required_terms)
            ),
            None,
        )
        group_results.append({
            "required_terms": required_terms,
            "matched_rank": matched_rank,
        })

    return {
        "id": case["id"],
        "passed": all(result["matched_rank"] is not None for result in group_results),
        "web_search_used": web_search_used,
        "groups": group_results,
        "retrieved": [
            {
                "rank": rank,
                "source": doc.metadata.get("source"),
                "page": doc.metadata.get("page"),
                "table_row": doc.metadata.get("table_row"),
                "preview": doc.page_content[:300],
            }
            for rank, doc in enumerate(docs, start=1)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = [evaluate_case(case, args.top_k) for case in CASES]
    passed = sum(result["passed"] for result in results)
    report = {
        "passed": passed,
        "total": len(results),
        "recall_at_k": passed / len(results),
        "top_k": args.top_k,
        "results": results,
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
