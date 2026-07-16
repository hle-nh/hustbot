# Dataset Improvement Report - 2026-06-08

## Scope

Mục tiêu: cải thiện `data/dataset.csv` để dùng như corpus chuẩn hóa cho RAG, rebuild Chroma từ corpus đã lọc, và chấm lại benchmark/RAGAS.

## Files Added/Updated

- `backend/ingest/prepare_dataset_csv.py`: script chuẩn hóa `data/dataset.csv`.
- `backend/ingest/csv_loader.py`: loader để ingest trực tiếp từ CSV đã xử lý.
- `backend/ingest/pipeline.py`: thêm tùy chọn `DATASET_CSV` để rebuild Chroma từ CSV thay vì parse PDF lại.
- `data/dataset_clean.csv`: corpus audit đầy đủ, giữ toàn bộ 1.136 chunks.
- `data/dataset_retrieval.csv`: corpus đề xuất cho retrieval, còn 1.127 chunks sau khi lọc.
- `data/dataset_quality_report.md`: báo cáo chất lượng dataset tự sinh.
- `backend/results/eval_raw_after_dataset_clean.json`: raw benchmark sau khi rebuild Chroma.
- `backend/results/eval_scores_after_dataset_clean.json`: điểm RAGAS sau cải thiện.
- `backend/results/eval_raw_after_dataset_clean_reranker.json`: raw benchmark cuối sau khi bật reranker.
- `backend/results/eval_scores_after_dataset_clean_reranker.json`: điểm RAGAS cuối sau khi bật reranker.

## Dataset Changes

Trước cải thiện, `data/dataset.csv` có 1.136 dòng nhưng metadata còn yếu:

- `category` rỗng 1.136/1.136 dòng.
- `section` thiếu 1.037/1.136 dòng.
- `article` thiếu 815/1.136 dòng.
- Không có `chunk_id`, `document_type`, `is_table`, `topic_tags`, `quality_flags`, `include_for_retrieval`.

Sau cải thiện:

- Điền `category` cho 1.136/1.136 dòng theo source PDF.
- Thêm `chunk_id` ổn định để audit/dedup.
- Thêm `document_type`, `year`, `is_table`, `prefix_context`, `topic_tags`.
- Thêm thống kê `char_count`, `word_count`.
- Thêm `quality_flags` để đánh dấu chunk yếu.
- Thêm `include_for_retrieval` để tách corpus audit và corpus dùng cho vector DB.
- Loại khỏi retrieval 9 chunks gồm title/cover page, chunk quá ngắn không có tín hiệu hữu ích, và 1 table row thông tin thấp.

Phân bố `dataset_retrieval.csv`:

| Item | Count |
|---|---:|
| Original chunks | 1.136 |
| Retrieval chunks | 1.127 |
| Excluded chunks | 9 |
| Sources | 6 |

## Chroma Rebuild

Đã rebuild Chroma từ `data/dataset_retrieval.csv` bằng:

```powershell
cd backend
$env:DATASET_CSV='../data/dataset_retrieval.csv'
python -m ingest.pipeline
```

Kết quả: collection `hust_regulations` hiện có 1.127 chunks, kèm metadata mới như `chunk_id`, `category`, `document_type`, `topic_tags`, `char_count`, `word_count`.

## RAGAS Before/After

So sánh với lần chấm lại trước đó (`eval_scores_rerun_20260608.json`):

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Faithfulness | 0.7717 | 0.7306 | -0.0410 |
| Answer Relevancy | 0.4131 | 0.4766 | +0.0635 |
| Context Precision | 0.5488 | 0.5500 | +0.0012 |
| Context Recall | 0.7222 | 0.7109 | -0.0113 |
| Overall | 0.6139 | 0.6170 | +0.0031 |

Sau đó đã sửa môi trường reranker:

- Cài `FlagEmbedding`.
- Hạ `transformers` từ `5.9.0` về `4.57.6` vì `FlagEmbedding` lỗi runtime với nhánh 5.x.
- Thêm fallback runtime trong `app/rag/reranker.py` để nếu reranker lỗi thì chatbot không crash.
- `pip check` không báo broken requirements.
- Retrieval regression học phí đạt `4/4`, `recall@6 = 1.0` với reranker hoạt động.

Kết quả cuối cùng sau dataset cleanup + reranker:

| Metric | Before | Dataset only | Dataset + reranker | Final Delta |
|---|---:|---:|---:|---:|
| Faithfulness | 0.7717 | 0.7306 | 0.7548 | -0.0169 |
| Answer Relevancy | 0.4131 | 0.4766 | 0.5049 | +0.0919 |
| Context Precision | 0.5488 | 0.5500 | 0.6582 | +0.1094 |
| Context Recall | 0.7222 | 0.7109 | 0.6328 | -0.0894 |
| Overall | 0.6139 | 0.6170 | 0.6377 | +0.0237 |

Các chỉ báo phụ:

| Indicator | Before | After |
|---|---:|---:|
| `answer_relevancy = 0` | 25 | 19 |
| `context_precision = 0` | 16 | 14 |
| `context_recall = 0` | 17 | 18 |
| RAGAS NaN values | 2 | 0 |

## Interpretation

Kết quả tốt hơn ở `answer_relevancy`: số câu bị chấm 0 về relevance giảm từ 25 xuống 19. Điều này cho thấy câu trả lời sau rebuild thường đi gần intent của câu hỏi hơn.

`context_precision` gần như không đổi, nghĩa là việc lọc 9 chunk nhiễu giúp làm sạch corpus nhưng chưa đủ để thay đổi mạnh ranking. Đây là hợp lý vì chỉ loại 0,8% corpus.

`faithfulness` giảm vì một số câu trả lời sau run mới trực tiếp hơn nhưng có thể ít bám sát context hơn theo evaluator. Đây là trade-off thường gặp khi answer relevancy tăng.

`context_recall` giảm nhẹ và vẫn còn nhiều case recall thấp vì corpus vẫn thiếu một số thông tin benchmark yêu cầu, ví dụ SIE, cổng Parabol, KTX, một số thông tin chung/trực tuyến.

## Important Caveat

Reranker hiện đã chạy được sau khi hạ `transformers` về 4.x. Tuy nhiên full benchmark có chi phí thời gian/API cao hơn đáng kể vì reranker chạy CPU và mỗi câu mất nhiều thời gian hơn. Lần chạy cuối dùng `--resume` để chỉ gọi generation API cho 9 câu còn thiếu, tránh chạy lại 55 câu đã có.

## Remaining Work

Ưu tiên tiếp theo:

1. Bổ sung corpus cho các thông tin benchmark còn thiếu: SIE, HUST, địa chỉ, KTX, cổng Parabol, IT1/IT2, hỗ trợ eHUST.
2. Tạo supplemental curated facts CSV cho các FAQ không nằm rõ trong PDF.
3. Giảm chi phí reranker bằng candidate filtering tốt hơn hoặc cache rerank scores cho benchmark.
4. Cập nhật `requirements.txt` pin `transformers<5` nếu tiếp tục dùng `FlagEmbedding`.
