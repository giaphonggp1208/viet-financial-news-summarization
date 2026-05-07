# Báo cáo đồ án: Tóm tắt văn bản tiếng Việt bảo toàn số liệu

## 1. Giới thiệu

Bài toán của nhóm là xây dựng hệ thống tóm tắt văn bản tiếng Việt trên miền chuyên biệt, trong đó bản tóm tắt phải ngắn gọn nhưng không làm sai lệch số liệu. Nhóm chọn miền chứng khoán Việt Nam trên CafeF, trọng tâm là chuyên mục Thị trường chứng khoán, vì văn bản thường chứa nhiều thực thể số như ngày tháng, chỉ số chứng khoán, tỷ đồng, đồng/cp, phần trăm cổ tức, khối lượng cổ phiếu, doanh thu, lợi nhuận và thống kê thị trường.

Mục tiêu chính:

- Fine-tune ít nhất hai mô hình encoder-decoder pretrained cho tiếng Việt/đa ngôn ngữ.
- Bảo toàn số liệu trong quá trình sinh tóm tắt.
- Kiểm soát độ dài output ở mức 20-25% văn bản gốc.
- Đánh giá bằng cả độ đo trùng bề mặt, ngữ nghĩa và metric ràng buộc nghiệp vụ.

## 2. Dữ liệu

Nguồn dữ liệu dự kiến là chuyên mục Thị trường chứng khoán trên CafeF: `https://cafef.vn/thi-truong-chung-khoan.chn`. Quy trình thu thập đọc trang chuyên mục để lấy URL bài viết, sau đó trích nội dung từng bài bằng `trafilatura`.

Định dạng mỗi mẫu:

```json
{"id":"...","url":"...","source":"văn bản gốc","summary":"bản tóm tắt thủ công"}
```

Quy tắc biên tập tóm tắt:

- Summary dài 20-25% số từ của source.
- Tất cả số liệu trong source phải xuất hiện nguyên dạng trong summary.
- Không thêm số liệu ngoài source.
- Test set được kiểm tra thủ công và không trùng train/val.

Do yêu cầu test tối thiểu 100 mẫu và chia 80/10/10, nhóm đặt mục tiêu thu thập tối thiểu 1000 cặp hợp lệ.

## 3. Tiền xử lý và kiểm tra dữ liệu

Pipeline gồm bốn bước:

1. Thu thập bài viết bằng `scripts/collect_from_rss.py`.
2. Sinh sheet gán nhãn bằng `scripts/make_annotation_sheet.py`.
3. Nhóm viết hoặc biên tập summary thủ công.
4. Kiểm tra số liệu/độ dài và chia tập bằng `scripts/prepare_dataset.py`.

Regex số liệu nhận diện:

- Ngày tháng: `12/03/2025`, `ngày 12/03/2025`, `quý I/2025`.
- Số tiền: `18.500 tỷ đồng`, `82 USD`.
- Phần trăm: `12%`, `3,8%`.
- Chỉ số, số lượng, thống kê: `1.248,33 điểm`, `27 mã`, `91 mã`.

Metric nội bộ sử dụng so sánh multiset số liệu giữa source và summary. Cách này phát hiện cả số thiếu, số thừa và số bị thay đổi.

## 4. Mô hình

Nhóm fine-tune các mô hình:

- `VietAI/vit5-base`: T5 tiếng Việt, phù hợp tác vụ seq2seq.
- `vinai/bartpho-syllable`: BART tiếng Việt mức âm tiết, tránh yêu cầu word segmentation phức tạp.
- Tuỳ chọn điểm cộng: `google/mt5-base` với LoRA/PEFT để giảm tài nguyên.

Hyperparameter mặc định:

| Model | Epoch | LR | Batch | Grad Accum | Beam | Length Penalty | Max Source | Max Target |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ViT5-base | 5 | 3e-5 | 2 | 8 | 4 | 1.0 | 1024 | 256 |
| BARTpho-syllable | 5 | 2e-5 | 2 | 8 | 5 | 0.9 | 1024 | 256 |
| mT5-base LoRA | 5 | 1e-4 | 2 | 8 | 4 | 1.0 | 1024 | 256 |

## 5. Ràng buộc số liệu và độ dài

Kiểm soát độ dài:

- Khi generation, `min_length` và `max_length` được tính động theo 20-25% số token đầu vào.
- Trong đánh giá, độ dài được kiểm tra lại bằng số từ để đúng yêu cầu báo cáo.

Bảo toàn số liệu:

- Trước huấn luyện: loại hoặc đưa vào danh sách lỗi các cặp summary không giữ đủ số liệu.
- Sau sinh: trích số liệu từ source và prediction, so sánh multiset.
- Tuỳ chọn hậu xử lý: chèn danh sách số liệu còn thiếu để debug ràng buộc, nhưng báo cáo nên phân biệt rõ kết quả raw và post-processed.

## 6. Chương riêng: Phương pháp đánh giá

### 6.1. Nhóm trùng bề mặt

ROUGE-1/2/L đo mức trùng n-gram và chuỗi con dài nhất giữa prediction và reference. ROUGE phù hợp cho tóm tắt vì phản ánh mức bao phủ thông tin so với bản tóm tắt chuẩn. Điểm yếu là không hiểu đồng nghĩa và không đảm bảo tính đúng số liệu: một summary có ROUGE cao vẫn có thể đổi `18%` thành `16%`.

BLEU đo độ chính xác n-gram, thường dùng trong dịch máy. Với tóm tắt, BLEU hữu ích để xem prediction có gần reference về bề mặt hay không, nhưng có xu hướng phạt các cách diễn đạt hợp lệ khác reference. BLEU cũng không trực tiếp kiểm tra độ dài 20-25% hay tính nhất quán số liệu.

METEOR có xét stemming/đồng nghĩa ở một số ngôn ngữ và cân bằng precision-recall tốt hơn BLEU. Tuy nhiên với tiếng Việt, tài nguyên ngôn ngữ hạn chế khiến METEOR kém ổn định hơn tiếng Anh. METEOR vẫn không đủ để phát hiện sai số liệu nếu phần lớn câu còn lại giống reference.

### 6.2. Nhóm ngữ nghĩa

BERTScore dùng embedding ngữ cảnh để đo độ tương đồng ngữ nghĩa giữa prediction và reference. Ưu điểm là ít phụ thuộc trùng từng từ, phù hợp khi tóm tắt có cách diễn đạt khác reference. Nhược điểm lớn trong bài toán này là embedding có thể xem `3,8%` và `4,5%` gần nhau theo ngữ cảnh, trong khi đây là lỗi nghiêm trọng.

### 6.3. LLM làm trọng tài

LLM-as-a-judge có thể chấm các tiêu chí phức tạp như đầy đủ ý, mạch lạc, lỗi suy diễn và tính hữu ích. Với bài toán bảo toàn số liệu, prompt có thể yêu cầu LLM liệt kê từng số liệu trong source và đối chiếu summary. Tuy nhiên phương pháp này tốn chi phí, có độ bất định, phụ thuộc prompt và vẫn cần kiểm chứng bằng rule-based regex cho số liệu.

### 6.4. Lựa chọn độ đo của nhóm

Nhóm chọn bộ metric chính:

- ROUGE-1, ROUGE-2, ROUGE-L để so sánh với các nghiên cứu tóm tắt phổ biến.
- BLEU để bổ sung góc nhìn precision n-gram.
- BERTScore để đo tương đồng ngữ nghĩa.
- Number Accuracy để kiểm tra ràng buộc quan trọng nhất của đề bài.
- Length Compliance để kiểm tra tỉ lệ 20-25%.

Trong báo cáo, Number Accuracy và Length Compliance được xem là metric bắt buộc. Một mô hình có ROUGE/BERTScore cao nhưng Number Accuracy thấp không đạt yêu cầu nghiệp vụ.

## 7. Thực nghiệm

Thiết lập:

- Train/val/test: 80/10/10.
- Test set được soát thủ công.
- Decode bằng beam search, length penalty và no-repeat n-gram.
- Mỗi model được đánh giá trên cùng test set.

Bảng kết quả:

| Model | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU | BERTScore F1 | Number Accuracy | Length Compliance |
|---|---:|---:|---:|---:|---:|---:|---:|
| ViT5-base | | | | | | | |
| BARTpho-syllable | | | | | | | |
| mT5-base LoRA | | | | | | | |

## 8. Phân tích lỗi

Các nhóm lỗi cần thống kê:

- Thiếu số liệu trong source.
- Thêm số liệu không có trong source.
- Chép sai đơn vị tiền tệ/phần trăm.
- Summary vượt quá hoặc thấp hơn 20-25%.
- Tóm tắt đúng số nhưng thiếu ý chính.

## 9. Demo

Demo Gradio cho phép nhập văn bản tài chính, chọn checkpoint, sinh summary và hiển thị:

- Bản tóm tắt.
- Number Accuracy ở mức từng mẫu.
- Length Compliance và tỉ lệ độ dài.
- Danh sách số thiếu/số lạ nếu có.

## 10. Kết luận

Đồ án nhấn mạnh rằng tóm tắt trong miền giàu số liệu không chỉ cần giống reference về bề mặt hoặc ngữ nghĩa, mà còn phải đúng ràng buộc nghiệp vụ. Vì vậy hệ thống kết hợp fine-tuning mô hình encoder-decoder với hậu kiểm rule-based để phát hiện lỗi số liệu và độ dài.
