# Báo cáo chấm lại RAGAS - HUSTBot

Ngày chạy: 2026-06-08
Input: `backend/results/eval_raw_v3.json`
Output điểm chi tiết: `backend/results/eval_scores_rerun_20260608.json`
Số mẫu đánh giá: 64/64 câu thành công
Evaluator: OpenAI `gpt-4o-mini`, embeddings `text-embedding-3-small`
Metrics: faithfulness, answer_relevancy, context_precision, context_recall

Ghi chú: lần chạy trong sandbox cho kết quả `NaN` do lỗi kết nối API. Lần chạy hợp lệ đã được chạy lại với quyền mạng; trong quá trình này có 2 job timeout lẻ, dẫn đến 1 giá trị `NaN` ở `context_precision` và 1 giá trị `NaN` ở `context_recall`. Trung bình dưới đây được tính theo mặc định của pandas/RAGAS là bỏ qua `NaN`.

## Quantitative Result

| Metric | Điểm trung bình | Nhận xét |
|---|---:|---|
| Faithfulness | 0.7717 | Khá cao: đa số câu trả lời bám vào context hoặc từ chối khi thiếu thông tin. |
| Answer Relevancy | 0.4131 | Thấp: nhiều câu trả lời không khớp trực tiếp intent/ground truth, hoặc trả lời dạng "không tìm thấy" dù benchmark có đáp án. |
| Context Precision | 0.5488 | Trung bình: retrieval lấy được tài liệu đúng nhưng thường kèm nhiều chunk nhiễu, không liên quan. |
| Context Recall | 0.7222 | Khá: nhiều câu có đủ bằng chứng trong context, nhưng vẫn có các câu recall bằng 0 do thiếu nguồn đúng. |
| Overall RAGAS Score | 0.6139 | Mức trung bình khá, bị kéo xuống chủ yếu bởi answer relevancy và context precision. |

So với lần chấm cũ `eval_scores_v3.json`:

| Metric | Cũ | Mới | Chênh lệch |
|---|---:|---:|---:|
| Faithfulness | 0.7604 | 0.7717 | +0.0113 |
| Answer Relevancy | 0.4113 | 0.4131 | +0.0018 |
| Context Precision | 0.5344 | 0.5488 | +0.0144 |
| Context Recall | 0.6797 | 0.7222 | +0.0425 |
| Overall | 0.5964 | 0.6139 | +0.0175 |

Theo độ khó:

| Complexity | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---:|---:|---:|---:|
| Cơ bản | 0.8136 | 0.4855 | 0.5257 | 0.7407 |
| Trung bình | 0.6725 | 0.3042 | 0.5010 | 0.6739 |
| Khó | 0.8537 | 0.4523 | 0.6685 | 0.7692 |

Theo category:

| Category | Số câu | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---:|---:|---:|---:|---:|
| Học bổng | 5 | 0.8470 | 0.4435 | 0.6611 | 0.8000 |
| Học phí | 10 | 0.8476 | 0.4504 | 0.4404 | 0.8000 |
| Hỗ trợ kỹ thuật | 1 | 1.0000 | 0.4426 | 0.0000 | 0.0000 |
| Hỗ trợ sinh viên | 1 | 0.5000 | 0.0000 | 1.0000 | 1.0000 |
| Quy chế đào tạo | 21 | 0.8356 | 0.3573 | 0.7025 | 0.7381 |
| Thông tin chung | 10 | 0.6467 | 0.4864 | 0.2639 | 0.7000 |
| Tuyển sinh | 16 | 0.6976 | 0.4316 | 0.5735 | 0.6667 |

Phân phối đáng chú ý:

- `answer_relevancy = 0`: 25/64 câu.
- `context_recall = 0`: 17/64 câu.
- `context_precision = 0`: 16/64 câu.
- Median cao hơn mean ở một số metric, cho thấy hệ thống có nhiều câu làm tốt nhưng bị kéo xuống bởi các failure case rõ rệt.

## Qualitative Result

Các điểm mạnh:

- Câu trả lời thường trung thực với context. Khi context có bằng chứng trực tiếp, hệ thống trả lời khá gọn và có số liệu đúng. Ví dụ các câu về năm thành lập, thư viện, học bổng, bảo lưu trúng tuyển, rút/hủy đăng ký học phần đạt điểm cao.
- Khả năng bao phủ context tương đối ổn ở nhiều nhóm học phí, học bổng, quy chế đào tạo. Điều này cho thấy retriever thường tìm được ít nhất một đoạn chứa thông tin cần thiết.
- Những câu có thông tin nằm rõ trong sổ tay/quy chế được xử lý tốt hơn, nhất là câu hỏi dạng factoid hoặc quy định một bước.

Các điểm yếu:

- Answer relevancy thấp vì chatbot hay trả lời "không tìm thấy thông tin này trong tài liệu hiện có" trong khi ground truth có đáp án, hoặc trả lời đúng một phần nhưng không đi thẳng vào intent của câu hỏi.
- Retrieval còn nhiễu: top-k thường chứa chunk từ đúng tài liệu nhưng sai trang/sai mục, hoặc lẫn các đoạn bảng PDF bị OCR/parse kém. Điều này làm `context_precision` chỉ đạt 0.5488.
- Một số đáp án dựa vào context không đủ hoặc chọn sai thông tin liên hệ. Ví dụ câu eHUST sai mật khẩu lấy số điện thoại từ đoạn khác nên `context_precision` và `context_recall` bằng 0.
- Các câu cần thông tin ngoài corpus hoặc thông tin chung của trường như địa chỉ, HUST, cổng Parabol, KTX dễ thất bại nếu tài liệu nội bộ không chứa đúng đoạn hoặc retriever không lấy được đoạn đó.
- Nhóm "Trung bình" thấp nhất vì câu hỏi thường yêu cầu tổng hợp/diễn giải nhiều điều kiện, trong khi retrieval và generation vẫn thiên về trích một đoạn gần nhất.

Failure case tiêu biểu:

| ID | Vấn đề chính |
|---|---|
| BM_033 | Hỏi "SIE là gì?" nhưng hệ thống trả lời không tìm thấy; tất cả metric bằng 0. |
| BM_022 | Hỏi khác nhau giữa IT1 và IT2; câu trả lời có một phần liên quan nhưng context/ground truth không đủ khớp, overall rất thấp. |
| BM_040 | Hỏi dùng điểm ĐGNL ĐHQG HN xét tuyển; hệ thống phủ định theo context không đủ, trong khi ground truth khác. |
| BM_062 | Hỏi đồ án tốt nghiệp bao nhiêu tín chỉ; hệ thống trả lời công thức TCHT/TCHP thay vì số tín chỉ kỳ vọng. |
| BM_083 | Hỏi học bổng KKHT trả tiền mặt hay trừ học phí; hệ thống né câu trả lời vì context không chứa đủ thông tin. |

Case tốt tiêu biểu:

| ID | Lý do đạt điểm cao |
|---|---|
| BM_005 | Context chứa đúng tên thư viện, câu trả lời trực tiếp và đúng intent. |
| BM_056 | Context quy chế có đủ thông tin rút/hủy đăng ký môn học, câu trả lời bám sát nguồn. |
| BM_036 | Câu hỏi bảo lưu khi đi nghĩa vụ có bằng chứng rõ trong tài liệu tuyển sinh/quy chế. |
| BM_073 | Câu hỏi loại học bổng được retrieval đúng nhóm nội dung và generation tổng hợp tốt. |
| BM_074 | Câu hỏi CPA học bổng loại A có đáp án dạng điều kiện rõ ràng, ít cần suy luận ngoài context. |

## Giải thích điểm cao/thấp

`Faithfulness` cao vì prompt hiện tại có xu hướng bắt chatbot chỉ trả lời theo tài liệu và fallback khi không chắc. Điều này giảm hallucination, nhưng mặt trái là nếu retriever không đưa đúng context, chatbot sẽ từ chối hoặc trả lời thiếu.

`Answer Relevancy` thấp vì metric này đánh giá câu trả lời có đúng trọng tâm câu hỏi không. Nhiều câu trả lời an toàn nhưng không đáp ứng câu hỏi, ví dụ "không tìm thấy" hoặc gợi ý liên hệ phòng ban, nên bị chấm thấp dù không bịa.

`Context Precision` trung bình vì retriever trả về nhiều đoạn thừa. Một vài câu có đúng đoạn nằm trong top-k, nhưng các đoạn còn lại không liên quan làm precision giảm. Nhiễu đến từ PDF parse, bảng bị ghép dòng, và các câu hỏi ngắn dễ match sai như "địa chỉ", "cổng", "số điện thoại".

`Context Recall` khá nhưng chưa ổn định. Khi ground truth nằm trong corpus, hệ thống thường lấy được; nhưng nếu benchmark chứa đáp án không có trong tài liệu đã index hoặc câu hỏi cần thông tin cụ thể ngoài các PDF hiện có, recall rơi về 0.

## Kết luận

Chatbot hiện đạt mức trung bình khá về RAGAS: đáng tin cậy tương đối về mặt không bịa, nhưng chưa đủ tốt về trả lời đúng trọng tâm và retrieval chính xác. Nếu muốn tăng điểm nhanh, ưu tiên cải thiện retrieval trước: bổ sung tài liệu còn thiếu, làm sạch chunk PDF/bảng, tăng metadata theo mục/điều/trang, thêm query rewriting cho câu hỏi ngắn, và kiểm tra lại các ground truth không tồn tại trong corpus.
