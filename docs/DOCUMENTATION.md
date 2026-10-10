# Tài Liệu Chi Tiết Thư Mục `docs/`

Thư mục [`docs/`](file:///home/thai/Downloads/omniparser/docs) chứa tài liệu học thuật và kết quả đánh giá chuẩn (Benchmark Leaderboard) của Microsoft cho mô hình **OmniParser** trên các tập dữ liệu **ScreenSpot**, **Mind2Web** và **AITW (Android In The Wild)**.

---

## 1. Nội Dung Tệp [`docs/Evaluation.md`](file:///home/thai/Downloads/omniparser/docs/Evaluation.md)

Tệp [`Evaluation.md`](file:///home/thai/Downloads/omniparser/docs/Evaluation.md#L1-L21) tổng hợp cách thức đánh giá mô hình và dẫn chiếu tới mã nguồn thực thi trong thư mục [`eval/`](file:///home/thai/Downloads/omniparser/eval/DOCUMENTATION.md):
- Sử dụng trọng số `icon_detect` (YOLOv9-E) và `icon_caption_florence` (Florence-2-base fine-tuned).
- Chạy script [`eval/ss_pro_gpt4o_omniv2.py`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py) để đánh giá khả năng Grounding của GPT-4o khi được bổ trợ bởi ảnh Set-of-Mark (SoM) và mô tả ngữ nghĩa của OmniParser.

