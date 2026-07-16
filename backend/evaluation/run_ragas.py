import os
import sys
import json
import pandas as pd
from datasets import Dataset
from datetime import datetime
from types import ModuleType

# Monkeypatch to bypass VertexAI import issue in older/newer langchain-community integrations with Ragas
dummy_vertex = ModuleType("langchain_community.chat_models.vertexai")
dummy_vertex.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = dummy_vertex

# Đảm bảo import được các module của app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

def run_ragas_evaluation(raw_results_path: str, output_path: str):
    print("=== STARTING RAGAS EVALUATION ===")
    print(f"Raw Results Path: {raw_results_path}")

    # 1. Đọc kết quả thô đã sinh từ run_eval.py
    if not os.path.exists(raw_results_path):
        raise FileNotFoundError(f"Không tìm thấy file kết quả thô tại {raw_results_path}. Vui lòng chạy run_eval.py trước!")

    with open(raw_results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Lọc ra các câu thành công
    valid_data = [d for d in data if d.get("status") == "success"]
    if not valid_data:
        print("Không có câu hỏi nào chạy thành công để đánh giá Ragas!")
        return

    print(f"Số lượng câu hỏi hợp lệ để đánh giá Ragas: {len(valid_data)}/{len(data)}")

    # 2. Chuẩn bị dữ liệu cho RAGAS
    questions = [d["question"] for d in valid_data]
    answers = [d["answer"] for d in valid_data]
    contexts = [d["contexts"] for d in valid_data]
    # Ragas yêu cầu list of lists cho contexts
    # Đảm bảo không có context nào rỗng
    contexts = [c if c else ["Không tìm thấy tài liệu liên quan."] for c in contexts]
    ground_truths = [d["ground_truth"] for d in valid_data]

    # Ragas chấp nhận cả "ground_truth" hoặc "ground_truths" tùy phiên bản, ta dùng "ground_truth" và copy thêm trường kia cho an toàn
    rag_data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }

    dataset = Dataset.from_dict(rag_data)

    # 3. Khởi tạo LLM & Embeddings cho Ragas
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key and "sk-" in openai_api_key:
        print("Đang khởi tạo OpenAI làm giám khảo chấm điểm (gpt-4o-mini)...")
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        evaluator_llm = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=openai_api_key.strip(),
            temperature=0.0
        )
        evaluator_embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_api_key.strip()
        )
    else:
        print("Đang khởi tạo Gemini làm giám khảo chấm điểm...")
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("Thiếu biến môi trường GOOGLE_API_KEY!")

        evaluator_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=google_api_key,
            temperature=0.0
        )

        print("Đang khởi tạo Google Gemini Embeddings cho Ragas...")
        evaluator_embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=google_api_key
        )

    # 4. Cấu hình LLM & Embeddings cho các metrics
    print("Đang cấu hình Ragas metrics...")
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    ragas_llm = LangchainLLMWrapper(evaluator_llm)
    ragas_embeddings = LangchainEmbeddingsWrapper(evaluator_embeddings)

    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    for metric in metrics:
        metric.llm = ragas_llm
        if hasattr(metric, "embeddings"):
            metric.embeddings = ragas_embeddings

    # Thích ứng prompt của Ragas sang tiếng Việt
    print("Đang thích ứng các prompt của Ragas sang tiếng Việt...")
    import asyncio
    async def adapt_metrics():
        for metric in metrics:
            try:
                print(f"  Thích ứng metric: {metric.name}...")
                adapted = await metric.adapt_prompts("vietnamese", ragas_llm, adapt_instruction=True)
                metric.set_prompts(**adapted)
                print(f"  ✓ Đã thích ứng prompt cho metric: {metric.name}")
            except Exception as ex:
                print(f"  ✗ Không thể thích ứng prompt cho metric {metric.name}: {str(ex)}")

    asyncio.run(adapt_metrics())

    # 5. Chạy đánh giá Ragas
    print("Bắt đầu chấm điểm bằng Ragas (Quá trình này có thể mất vài phút)...")
    try:
        # Sử dụng evaluate của ragas
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=ragas_llm,
            embeddings=ragas_embeddings
        )

        # 6. Hiển thị báo cáo kết quả
        scores_df = result.to_pandas()

        # Merge các thông tin phụ vào báo cáo điểm số
        for i, row in scores_df.iterrows():
            scores_df.at[i, "id"] = valid_data[i]["id"]
            scores_df.at[i, "category"] = valid_data[i]["category"]
            scores_df.at[i, "complexity"] = valid_data[i]["complexity"]

        # 6. Lưu file báo cáo trước để bảo toàn dữ liệu
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        scores_df.to_json(output_path, orient="records", force_ascii=False, indent=2)

        # 7. Tính toán điểm trung bình từ dataframe để đảm bảo tương thích mọi phiên bản Ragas
        m_faithfulness = scores_df["faithfulness"].mean()
        m_answer_relevancy = scores_df["answer_relevancy"].mean()
        m_context_precision = scores_df["context_precision"].mean()
        m_context_recall = scores_df["context_recall"].mean()

        print("\n=== ĐIỂM SỐ RAGAS TRUNG BÌNH ===")
        print(f"Faithfulness (Sự trung thực):     {m_faithfulness:.4f}")
        print(f"Answer Relevancy (Độ phù hợp):     {m_answer_relevancy:.4f}")
        print(f"Context Precision (Độ chính xác):  {m_context_precision:.4f}")
        print(f"Context Recall (Độ bao phủ):       {m_context_recall:.4f}")

        # Tính điểm trung bình cộng (Ragas Score)
        ragas_score = (m_faithfulness + m_answer_relevancy + m_context_precision + m_context_recall) / 4
        print(f"--------------------------------------------------")
        print(f"OVERALL RAGAS SCORE:               {ragas_score:.4f}")
        print(f"\nBáo cáo điểm số chi tiết từng câu đã lưu tại: {output_path}")

    except Exception as e:
        print(f"Lỗi khi chạy Ragas evaluate: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="results/eval_raw_v3.json")
    parser.add_argument("--output", default="results/eval_scores_v3.json")
    args = parser.parse_args()

    raw_file = os.path.abspath(args.input)
    output_file = os.path.abspath(args.output)

    run_ragas_evaluation(raw_file, output_file)
