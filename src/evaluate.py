# src/evaluate.py

import os
import sys
import json
from dotenv import load_dotenv
from datasets import Dataset

sys.path.insert(0, os.path.dirname(__file__))

# Fix import deprecated
from ragas.metrics.collections import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from chain import init_chain

load_dotenv()

TEST_FILE   = os.getenv("TEST_FILE",   "./tests/test_questions.json")
RESULT_FILE = os.getenv("RESULT_FILE", "./tests/eval_results.json")


# ==============================================
# BƯỚC 1: KHỞI TẠO RAGAS DÙNG GEMINI
# ==============================================

def build_ragas_config():
    """
    Cấu hình RAGAS dùng Gemini thay vì OpenAI mặc định.
    - LLM: gemini-2.5-flash-lite (tiết kiệm quota khi chạy nhiều câu)
    - Embeddings: embedding-001 của Google
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Khong tim thay GOOGLE_API_KEY trong file .env")

    llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0,
        )
    )

    embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=api_key,
        )
    )

    # Gán LLM và embeddings cho từng metric
    metrics = [faithfulness(llm=llm), answer_relevancy(llm=llm, embeddings=embeddings), context_precision(llm=llm), context_recall(llm=llm),]

    print("Ragas: dung Gemini (gemini-2.5-flash-lite + embedding-001)")
    return metrics


# ==============================================
# BƯỚC 2: LOAD BỘ CÂU HỎI TEST
# ==============================================

def load_test_questions(filepath: str) -> list:
    with open(filepath, "r", encoding="utf-8") as f:
        questions = json.load(f)
    print(f"Da load {len(questions)} cau hoi test")
    return questions


# ==============================================
# BƯỚC 3: CHẠY RAG VÀ THU THẬP KẾT QUẢ
# ==============================================

def run_rag_on_testset(questions: list, chat) -> dict:
    all_questions    = []
    all_answers      = []
    all_contexts     = []
    all_ground_truth = []

    print("\nDang chay RAG tren bo test...\n")

    for i, item in enumerate(questions, 1):
        question     = item["question"]
        ground_truth = item["ground_truth"]

        print(f"[{i}/{len(questions)}] {question[:60]}...")

        try:
            result = chat.chat(question)

            # Dùng full page_content thay vì preview để RAGAS đánh giá chính xác hơn
            contexts = [
                src.get("preview", "")
                for src in result["sources"]
            ]

            all_questions.append(question)
            all_answers.append(result["answer"])
            all_contexts.append(contexts)
            all_ground_truth.append(ground_truth)

        except Exception as e:
            print(f"  Loi cau {i}: {e}")
            all_questions.append(question)
            all_answers.append("ERROR")
            all_contexts.append([""])
            all_ground_truth.append(ground_truth)

    return {
        "question":     all_questions,
        "answer":       all_answers,
        "contexts":     all_contexts,
        "ground_truth": all_ground_truth,
    }


# ==============================================
# BƯỚC 4: CHẠY RAGAS
# ==============================================

def run_ragas(data: dict, metrics: list) -> dict:
    print("\nDang chay RAGAS evaluation...")

    dataset = Dataset.from_dict(data)

    results = evaluate(
        dataset=dataset,
        metrics=metrics,
    )

    return results


# ==============================================
# BƯỚC 5: IN VÀ LƯU KẾT QUẢ
# ==============================================

def print_results(results) -> dict:
    scores = {
        "faithfulness":      round(float(results["faithfulness"]),      4),
        "answer_relevancy":  round(float(results["answer_relevancy"]),  4),
        "context_precision": round(float(results["context_precision"]), 4),
        "context_recall":    round(float(results["context_recall"]),    4),
    }

    print("\n" + "=" * 50)
    print("  KET QUA RAGAS EVALUATION")
    print("=" * 50)

    thresholds = {
        "faithfulness":      (0.85, "Cau tra loi co bia khong?"),
        "answer_relevancy":  (0.80, "Co tra loi dung cau hoi khong?"),
        "context_precision": (0.75, "Chunk retrieve co sach khong?"),
        "context_recall":    (0.75, "Co bo sot thong tin khong?"),
    }

    for metric, score in scores.items():
        threshold, desc = thresholds[metric]
        status = "OK" if score >= threshold else "FAIL"
        bar    = "#" * int(score * 20) + "." * (20 - int(score * 20))
        print(f"\n[{status}] {metric}")
        print(f"   {desc}")
        print(f"   [{bar}] {score:.2f} (nguong: {threshold})")

    avg = sum(scores.values()) / len(scores)
    print(f"\n{'='*50}")
    print(f"   Diem trung binh: {avg:.2f}")

    if avg >= 0.80:
        print("   Pipeline dat chat luong tot!")
    elif avg >= 0.70:
        print("   Pipeline o muc trung binh -- can toi uu them")
    else:
        print("   Pipeline can cai thien dang ke")

    print("=" * 50)
    return scores


def save_results(scores: dict, data: dict, filepath: str) -> None:
    output = {
        "scores": scores,
        "details": [
            {
                "question":     q,
                "answer":       a,
                "ground_truth": g,
                "contexts":     c,
            }
            for q, a, g, c in zip(
                data["question"],
                data["answer"],
                data["ground_truth"],
                data["contexts"],
            )
        ]
    }

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDa luu ket qua chi tiet: {filepath}")


# ==============================================
# MAIN
# ==============================================

def main():
    print("=" * 50)
    print("  HUST RAG -- RAGAS EVALUATION")
    print("=" * 50)

    # Khởi động RAG pipeline
    chat = init_chain()

    # Cấu hình RAGAS dùng Gemini
    metrics = build_ragas_config()

    # Load bộ câu hỏi test
    questions = load_test_questions(TEST_FILE)

    # Chạy RAG trên toàn bộ test set
    data = run_rag_on_testset(questions, chat)

    # Chạy RAGAS
    results = run_ragas(data, metrics)

    # In và lưu kết quả
    scores = print_results(results)
    save_results(scores, data, RESULT_FILE)


if __name__ == "__main__":
    main()