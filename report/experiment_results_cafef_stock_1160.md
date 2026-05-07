# Ket qua fine-tuning CafeF chung khoan

Ngay chay: 2026-05-04  
Mien du lieu: tin thi truong chung khoan CafeF  
Tap du lieu: `data/processed_cafef_stock_1160`

## Du lieu

- Tong cap hop le: 1,160
- Train/val/test: 928/116/116
- Chat luong tap tham chieu:
  - Number Accuracy: 1.0
  - Length Compliance: 1.0
  - Avg compression ratio: 0.2199

Luu y: phan lon summary hien tai la ban draft/weakly-supervised tao tu batch sau, can review thu cong them truoc khi cong bo nhu bo du lieu gan nhan thu cong hoan chinh.

## Cau hinh chung

- LoRA rank: 16
- LoRA alpha: 32
- LoRA dropout: 0.05
- Epochs: 3
- Learning rate: 1e-4
- Batch size/GPU: 1
- Gradient accumulation: 8
- Max source length: 512
- Max target length: 256
- FP16: true
- Generation: beam=2, no_repeat_ngram_size=3

## Mo hinh 1: ViT5-base LoRA

- Base model: `VietAI/vit5-base`
- Output: `outputs/vit5-base-lora-cafef-stock`
- Prefix: `summarize: `
- Length penalty: 1.0
- Gradient checkpointing: true
- LoRA target modules: `q`, `v`
- Trainable params: 1,769,472 / 227,720,448 (0.7770%)

Ket qua validation tot nhat theo ROUGE-L:

- Epoch 2: ROUGE-1 45.0040, ROUGE-2 24.1202, ROUGE-L 32.4111

Ket qua test:

| Metric | Gia tri |
| --- | ---: |
| ROUGE-1 | 53.2466 |
| ROUGE-2 | 33.1903 |
| ROUGE-L | 31.4790 |
| BLEU | 15.1873 |
| BERTScore F1 | 76.0073 |
| Number Accuracy (`summary_subset`) | 0.0431 |
| Length Compliance | 0.0690 |
| Avg compression ratio | 0.1164 |
| Prediction word mean | 83.0 |

Nhan xet: ViT5 sinh ngan hon muc tieu 20-25%, dan den Length Compliance thap. Kha nang giu so theo che do `summary_subset` cung chua dat.

## Mo hinh 2: BARTpho-syllable LoRA

- Base model: `vinai/bartpho-syllable`
- Output: `outputs/bartpho-syllable-lora-cafef-stock`
- Prefix: none
- Length penalty: 0.9
- Gradient checkpointing: false
- LoRA target modules: `q_proj`, `v_proj`
- Trainable params: 2,359,296 / 398,174,208 (0.5925%)

Ket qua validation tot nhat theo ROUGE-L:

- Epoch 3: ROUGE-1 67.3326, ROUGE-2 44.8930, ROUGE-L 43.0946

Ket qua test:

| Metric | Gia tri |
| --- | ---: |
| ROUGE-1 | 68.9716 |
| ROUGE-2 | 41.2940 |
| ROUGE-L | 39.0084 |
| BLEU | 22.6948 |
| BERTScore F1 | 72.7825 |
| Number Accuracy (`summary_subset`) | 0.5517 |
| Length Compliance | 0.6207 |
| Avg compression ratio | 0.2174 |
| Prediction word mean | 163.81 |

Nhan xet: BARTpho la baseline tot hon trong lan chay nay, dat ty le nen gan muc tieu 20-25% va giu so tot hon ViT5.

## Audit so lieu

Neu dung che do `exact` hoac `all_original`, Number Accuracy cua ca hai mo hinh bang 0.0 vi summary 20-25% khong the chua toan bo so lieu trong bai goc dai. Che do phu hop hon cho thuc nghiem hien tai la `summary_subset`: moi so xuat hien trong summary phai khop voi so co trong bai goc, khong duoc them/hallucinate so moi.

## Ket luan tam thoi

- Chon BARTpho-syllable LoRA lam mo hinh chinh cho demo.
- Can lam them post-processing/constrained decoding de tang Number Accuracy.
- Can review thu cong them cac summary draft neu nop theo dung yeu cau "tu xay dung/thu cong".

## Thu nghiem post-processing giu so lieu

Da thu 2 cach hau xu ly tren prediction test cua BARTpho:

1. `repair_extra`: neu model sinh so co cung phan gia tri voi so trong source nhung thieu/sai don vi, thay bang surface number tu source.
2. `repair_then_drop_extra_sentences`: sua nhu tren, sau do xoa cac cau van con so khong xuat hien trong source.

| Bien the | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU | BERTScore F1 | Number Accuracy | Length Compliance | Avg ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BARTpho goc | 68.9716 | 41.2940 | 39.0084 | 22.6948 | 72.7825 | 0.5517 | 0.6207 | 0.2174 |
| BARTpho + repair_extra | 69.0970 | 41.5538 | 39.2158 | 22.8255 | 72.8044 | 0.6810 | 0.6293 | 0.2179 |
| BARTpho + repair_then_drop | 64.7609 | 37.7474 | 36.1815 | 18.8187 | 71.0898 | 1.0000 | 0.4655 | 0.1895 |

Nhan xet: `repair_extra` la lua chon can bang hon vi tang Number Accuracy tu 55.17% len 68.10% ma khong lam giam ROUGE/Length Compliance. `repair_then_drop` dat Number Accuracy 100% nhung hy sinh noi dung va do dai, phu hop nhu che do "strict/safe" trong demo hon la che do mac dinh.
