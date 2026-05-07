# Dàn ý slide thuyết trình

## Slide 1. Bài toán

- Tóm tắt văn bản tiếng Việt miền chứng khoán CafeF.
- Ràng buộc 1: giữ đúng 100% số liệu.
- Ràng buộc 2: summary dài 20-25% source.

## Slide 2. Vì sao chọn miền chứng khoán CafeF

- Nhiều số liệu: tỷ đồng, đồng/cp, ngày giao dịch, phần trăm, VN-Index, mã cổ phiếu.
- Sai một số có thể làm đổi nghĩa bản tin.
- Phù hợp để đánh giá Number Accuracy.

## Slide 3. Dữ liệu tự xây dựng

- Thu thập bài viết từ RSS/website.
- Viết hoặc biên tập summary thủ công.
- Kiểm tra regex số liệu và tỉ lệ độ dài.
- Chia train/val/test 80/10/10.

## Slide 4. Pipeline hệ thống

- Crawl bài viết.
- Tạo annotation sheet.
- Validate số liệu và độ dài.
- Fine-tune mô hình.
- Evaluate và demo.

## Slide 5. Mô hình

- ViT5-base.
- BARTpho-syllable.
- Tuỳ chọn mT5-base LoRA.
- Decode bằng beam search và length penalty.

## Slide 6. Bảo toàn số liệu

- Regex trích số từ source và summary.
- So sánh multiset số liệu.
- Báo thiếu số, thừa số, sai số.
- Optional post-processing để debug.

## Slide 7. Đánh giá

- ROUGE-1/2/L, BLEU, BERTScore.
- Number Accuracy.
- Length Compliance.
- LLM-as-a-judge dùng phân tích bổ sung.

## Slide 8. Kết quả thực nghiệm

- Bảng so sánh model.
- Nhận xét model tốt nhất theo metric tổng thể.
- Nhấn mạnh Number Accuracy và Length Compliance.

## Slide 9. Demo

- Nhập một bài tài chính.
- Sinh summary.
- Hiển thị audit số liệu và tỉ lệ độ dài.

## Slide 10. Kết luận

- Fine-tuning cải thiện chất lượng tóm tắt.
- Metric truyền thống chưa đủ phát hiện sai số.
- Rule-based audit giúp kiểm soát yêu cầu nghiệp vụ.
