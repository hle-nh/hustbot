import os
import sys
import json
import time
import pandas as pd
from datetime import datetime

# Đảm bảo import được app và các module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.rag.retriever import retrieve
from app.rag.prompt_builder import format_context, build_prompt_inputs
from app.rag.generator import get_model_manager

def run_evaluation(excel_path: str, output_path: str, resume: bool = False):
    print("=== STARTING BATCH EVALUATION ===")
    print(f"Excel Path: {excel_path}")

    # 1. Đọc bộ câu hỏi benchmark
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Không tìm thấy file benchmark tại {excel_path}")

    df = pd.read_excel(excel_path)

    # Xác định các cột cần thiết
    col_id = "Mã ID"
    col_cat = "Phân loại (Category)"
    col_comp = "Mức độ (Complexity)"
    col_goal = "Mục đích kiểm thử (Intent/Goal)"
    col_question = "Câu hỏi đầu vào (User Prompt)"
    col_ground_truth = "Câu trả lời chuẩn (Ground Truth / Expected Output)"

    required_cols = [col_id, col_question, col_ground_truth]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Thiếu cột bắt buộc '{col}' trong file excel. Các cột hiện có: {df.columns.tolist()}")

    # 2. Khởi tạo Model Manager
    print("Đang khởi tạo Model Manager...")
    model_manager = get_model_manager()
    print(f"Model đang sử dụng: {model_manager.current_model}")

    # 3. Chạy từng câu hỏi
    total_questions = len(df)
    results = []
    start_idx = 0
    print(f"Tổng số câu hỏi cần test: {total_questions}")

    # Tạo thư mục output nếu chưa tồn tại
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if resume and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        start_idx = len(results)
        print(f"Resume mode: đã có {start_idx}/{total_questions} câu trong {output_path}")

    t_start = time.time()

    for idx, row in df.iterrows():
        if idx < start_idx:
            continue
        q_id = row[col_id]
        category = row.get(col_cat, "Unknown")
        complexity = row.get(col_comp, "Unknown")
        goal = row.get(col_goal, "Unknown")
        question = row[col_question]
        ground_truth = row[col_ground_truth]

        print(f"\n[{idx + 1}/{total_questions}] Đang chạy {q_id} ({complexity}): {question[:60]}...")

        t0 = time.time()
        try:
            # A. Retrieve tài liệu tham chiếu
            docs, _ = retrieve(question, use_reranker=True)
            context_text = format_context(docs)
            contexts = [doc.page_content for doc in docs]
            sources = [
                f"{doc.metadata.get('source', 'unknown')} — trang {doc.metadata.get('page', '?')}"
                for doc in docs
            ]

            # B. Sinh câu trả lời
            prompt_inputs = build_prompt_inputs(
                question=question,
                context=context_text,
                history=""
            )
            answer, _ = model_manager.generate(prompt_inputs)

            elapsed = time.time() - t0
            print(f"-> Hoàn thành trong {elapsed:.2f}s")

            results.append({
                "id": str(q_id),
                "category": str(category),
                "complexity": str(complexity),
                "goal": str(goal),
                "question": str(question),
                "ground_truth": str(ground_truth),
                "answer": str(answer),
                "contexts": contexts,
                "sources": sources,
                "elapsed_seconds": round(elapsed, 2),
                "status": "success"
            })
        except Exception as e:
            elapsed = time.time() - t0
            print(f"-> LỖI tại {q_id}: {str(e)}")
            results.append({
                "id": str(q_id),
                "category": str(category),
                "complexity": str(complexity),
                "goal": str(goal),
                "question": str(question),
                "ground_truth": str(ground_truth),
                "answer": f"Lỗi sinh câu trả lời: {str(e)}",
                "contexts": [],
                "sources": [],
                "elapsed_seconds": round(elapsed, 2),
                "status": "error"
            })

        # Lưu checkpoint sau mỗi 5 câu để tránh mất mát dữ liệu
        if (idx + 1) % 5 == 0 or (idx + 1) == total_questions:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"--- Đã lưu checkpoint tại {output_path} ---")

        # Rate-limit: tránh vượt 20 req/min của Gemini Free Tier
        if (idx + 1) < total_questions:
            time.sleep(4)

    total_elapsed = time.time() - t_start
    print(f"\n=== HOÀN THÀNH BỘ BENCHMARK ===")
    processed = max(total_questions - start_idx, 1)
    print(f"Tổng thời gian: {total_elapsed:.2f}s (Trung bình {total_elapsed/processed:.2f}s/câu mới)")
    print(f"Kết quả lưu tại: {output_path}")

if __name__ == "__main__":
    # Đọc cấu hình từ .env
    import argparse
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", default="../benchmark_rag_v3.xlsx")
    parser.add_argument("--output", default="results/eval_raw_v3.json")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    excel_file = os.path.abspath(args.excel)
    output_file = os.path.abspath(args.output)

    run_evaluation(excel_file, output_file, resume=args.resume)
