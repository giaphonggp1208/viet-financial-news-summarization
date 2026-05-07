# Vietnamese Financial News Summarization

Tóm tắt tin tài chính/chứng khoán tiếng Việt trên miền CafeF với hai ràng buộc chính:

- kiểm soát độ dài bản tóm tắt trong khoảng 20-25% văn bản gốc,
- kiểm tra và hậu xử lý số liệu để hạn chế sai số, thiếu số hoặc sinh số không có trong nguồn.

Repo này gồm pipeline crawl dữ liệu, tạo annotation sheet, chuẩn hóa train/val/test, fine-tune mô hình encoder-decoder, đánh giá và Web UI demo end-to-end bằng Gradio.

## Kết Quả Hiện Tại

Dataset chính: `data/processed_cafef_stock_1160`

| Split | Số mẫu |
| --- | ---: |
| Train | 928 |
| Validation | 116 |
| Test | 116 |
| Tổng | 1,160 |

Kết quả test trên 116 mẫu:

| Model / Variant | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU | BERTScore F1 | Number Accuracy | Length Compliance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ViT5-base LoRA | 53.25 | 33.19 | 31.48 | 15.19 | 76.01 | 4.31% | 6.90% |
| BARTpho-syllable LoRA | 68.97 | 41.29 | 39.01 | 22.69 | 72.78 | 55.17% | 62.07% |
| BARTpho + `repair_extra` | 69.10 | 41.55 | 39.22 | 22.83 | 72.80 | 68.10% | 62.93% |
| BARTpho + strict drop | 64.76 | 37.75 | 36.18 | 18.82 | 71.09 | 100.00% | 46.55% |

`Number Accuracy` ở đây dùng chế độ `summary_subset`: mọi số xuất hiện trong summary phải khớp với số có trong source, không cho phép số lạ/hallucinated. Chế độ `exact` nghiêm ngặt hơn nhiều vì yêu cầu summary chứa toàn bộ số của source.

## Web UI Demo

Chạy app:

```powershell
python demo/app.py
```

Mở trình duyệt tại:

```text
http://127.0.0.1:7860
```

UI hỗ trợ:

- nhập URL CafeF hoặc paste nội dung bài viết,
- chọn model: `BARTpho-syllable LoRA`, `ViT5-base LoRA`, baseline hoặc checkpoint custom,
- chọn hậu xử lý số liệu: `number_coverage`, `repair_extra`, `drop_extra_sentences`, `repair_then_drop_extra_sentences`,
- hiển thị summary, compression ratio, length compliance và bảng audit số liệu.

Nếu muốn chỉ định checkpoint:

```powershell
python demo/app.py --model-dir outputs/bartpho-syllable-lora-cafef-stock
```

Nếu chưa có checkpoint, chọn `Baseline extractive` trong UI để kiểm thử luồng demo.

## Cài Đặt

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu dùng GPU NVIDIA, nên cài PyTorch CUDA theo hướng dẫn chính thức của PyTorch trước khi train.

Kiểm tra nhanh:

```powershell
pytest
```

## Cấu Trúc Repo

```text
configs/                         Cấu hình fine-tune ViT5, BARTpho, mT5
checkpoints/                     LoRA adapter gọn để demo
data/processed_cafef_stock_1160/ Dataset train/val/test đã chuẩn hóa
demo/app.py                      Web UI Gradio
report/                          Ghi chú báo cáo và kết quả thực nghiệm
scripts/                         Crawl, tạo sheet, train, evaluate, inference
src/visum/                       Logic số liệu, metric, inference, post-processing
tests/                           Unit tests cho number audit và post-processing
```

Các thư mục/cache không nên commit:

```text
.venv/
.hf_cache/
.tmp/
outputs/
data/raw/
data/processed/
release/
```

## Dataset

Dataset final được chia sẵn:

```text
data/processed_cafef_stock_1160/
  train.jsonl
  val.jsonl
  test.jsonl
  dataset_stats.json
  validation_errors.jsonl
```

Mỗi dòng JSONL có dạng:

```json
{
  "id": "...",
  "url": "...",
  "title": "...",
  "source": "văn bản gốc",
  "summary": "bản tóm tắt",
  "audit": {
    "source_words": 853,
    "summary_words": 197,
    "compression_ratio": 0.2309,
    "length_ok": true,
    "number_ok": true
  }
}
```

Lưu ý: một phần summary trong các batch sau là draft/weakly-supervised, cần review thủ công thêm nếu dùng để công bố như bộ dữ liệu gán nhãn hoàn toàn thủ công.

## Crawl CafeF

Thu thập bài từ chuyên mục chứng khoán:

```powershell
python scripts/collect_cafef.py --category-url https://cafef.vn/thi-truong-chung-khoan.chn --pages 5 --max-articles 500 --output data/raw/cafef_chung_khoan.jsonl
python scripts/collect_from_rss.py --feed https://cafef.vn/thi-truong-chung-khoan.rss --limit-per-feed 500 --output data/raw/cafef_chung_khoan_rss.jsonl
python scripts/collect_cafef_sitemaps.py --max-sitemaps 80 --max-urls 5000 --max-articles 1200 --output data/raw/cafef_sitemap_stock_more_1200.jsonl
```

Gộp và tạo annotation sheet:

```powershell
python scripts/merge_jsonl.py --input data/raw/cafef_chung_khoan.jsonl --input data/raw/cafef_chung_khoan_rss.jsonl --output data/raw/cafef_chung_khoan_all.jsonl
python scripts/make_annotation_sheet.py --input data/raw/cafef_chung_khoan_all.jsonl --output data/processed/annotation_sheet.csv --allowed-domain cafef.vn --min-numbers 5
```

Chuẩn hóa và chia train/val/test:

```powershell
python scripts/prepare_dataset.py --input data/processed/annotation_combined_cafef_stock_1160.csv --output-dir data/processed_cafef_stock_1160 --number-mode summary_subset
```

## Fine-Tuning

ViT5-base LoRA:

```powershell
python scripts/train.py --config configs/vit5_base_lora_3060.yaml --data-dir data/processed_cafef_stock_1160
```

BARTpho-syllable LoRA:

```powershell
python scripts/train.py --config configs/bartpho_syllable_lora_3060.yaml --data-dir data/processed_cafef_stock_1160
```

Checkpoint mặc định sau train được lưu vào `outputs/`. Repo cũng có bản LoRA adapter gọn trong `checkpoints/` để Web UI có thể demo ngay sau khi clone. Khi chạy lần đầu, Transformers vẫn cần tải base model tương ứng từ Hugging Face.

## Đánh Giá

Ví dụ evaluate BARTpho:

```powershell
python scripts/evaluate.py `
  --model-dir outputs/bartpho-syllable-lora-cafef-stock `
  --test-file data/processed_cafef_stock_1160/test.jsonl `
  --output-dir outputs/bartpho-syllable-lora-cafef-stock/eval_test `
  --num-beams 2 `
  --length-penalty 0.9 `
  --number-mode summary_subset
```

Metric xuất ra:

- ROUGE-1/2/L
- BLEU
- BERTScore F1
- Number Accuracy
- Length Compliance
- Average compression ratio
- `predictions.jsonl` để phân tích lỗi

## Hậu Xử Lý Số Liệu

Các chế độ chính:

- `repair_extra`: sửa số/đơn vị trong prediction bằng surface number từ source khi cùng giá trị số.
- `drop_extra_sentences`: xóa câu sinh ra số không có trong source.
- `repair_then_drop_extra_sentences`: sửa trước, sau đó xóa câu vẫn còn số lạ.
- `number_coverage`: demo mode chọn câu có số liệu từ nhiều đoạn của source để giảm tình trạng summary chỉ giống phần đầu bài.

## Inference CLI

```powershell
python scripts/summarize.py --model-dir outputs/bartpho-syllable-lora-cafef-stock --file article.txt
python scripts/summarize.py --baseline --file article.txt --enforce-numbers
```

## Ghi Chú GitHub

Repo chỉ chứa code, config, test, báo cáo dạng markdown, dataset final nhỏ và LoRA adapter gọn trong `checkpoints/`. Cache Hugging Face, raw crawl, full training outputs và các file annotation trung gian nên để ngoài GitHub hoặc đưa lên Hugging Face Hub/Google Drive.

## Khó Khăn
Qua thử nghiệm, mô hình tóm tắt encoder-decoder có xu hướng tạo ra bản tóm tắt mạch lạc nhưng không luôn bảo toàn đầy đủ số liệu tài chính. Một số lỗi phổ biến gồm bỏ sót số liệu ở cuối bài, sinh thêm số không thuộc required_numbers, hoặc đưa số liệu vào summary dưới dạng liệt kê thiếu tự nhiên. Do yêu cầu Number Accuracy là ràng buộc cứng, đồ án bổ sung tầng kiểm tra và sửa lỗi sau sinh gồm: trích xuất số liệu, kiểm tra missing/extra numbers, kiểm tra độ dài, sinh lại có điều kiện và chỉ chấp nhận summary khi cả Number Accuracy và Length Compliance đều đạt. Ngoài ra, hệ thống đề xuất biểu diễn số liệu bằng placeholder [NUM_i] để giảm lỗi định dạng và tăng khả năng bảo toàn số liệu khi fine-tune.
