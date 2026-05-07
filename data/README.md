# Dữ liệu

Miền chọn mặc định của project: tin tức chứng khoán Việt Nam trên CafeF, trọng tâm là chuyên mục `Thị trường chứng khoán`. Miền này giàu số liệu như VN-Index, HNX-Index, tỷ đồng, đồng/cp, phần trăm cổ tức, ngày giao dịch, khối lượng cổ phiếu, doanh thu và lợi nhuận.

## Định dạng cặp dữ liệu

Mỗi dòng JSONL cần có tối thiểu:

```json
{"id":"...","url":"...","source":"văn bản gốc","summary":"bản tóm tắt thủ công"}
```

Ràng buộc khi biên tập:

- Tóm tắt dài 20-25% số từ của văn bản gốc.
- Tất cả số liệu trong `source` phải xuất hiện nguyên dạng trong `summary`.
- Không thêm số liệu không có trong `source`.
- Test set phải được chuẩn bị thủ công và không trùng train/val.

Lưu ý: nếu vẫn chia 80/10/10 và muốn test có ít nhất 100 mẫu, nhóm nên chuẩn bị tối thiểu 1000 cặp hợp lệ.

## Crawl CafeF

```powershell
python scripts/collect_cafef.py --category-url https://cafef.vn/thi-truong-chung-khoan.chn --pages 5 --max-articles 500
python scripts/collect_from_rss.py --feed https://cafef.vn/thi-truong-chung-khoan.rss --limit-per-feed 500 --output data/raw/cafef_chung_khoan_rss.jsonl
python scripts/merge_jsonl.py --input data/raw/cafef_chung_khoan.jsonl --input data/raw/cafef_chung_khoan_rss.jsonl --output data/raw/cafef_chung_khoan_all.jsonl
python scripts/make_annotation_sheet.py --input data/raw/cafef_chung_khoan_all.jsonl --output data/processed/annotation_sheet.csv --allowed-domain cafef.vn --min-numbers 5
python scripts/data_status.py
```

Nếu trang phân trang của CafeF thay đổi, cập nhật `--page-url-template`.
