from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

import gradio as gr
import trafilatura

ROOT = Path(__file__).resolve().parents[1]
HF_CACHE = ROOT / ".hf_cache"
os.environ.setdefault("HF_HOME", str(HF_CACHE))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_CACHE / "transformers"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from visum.baseline import lead_summary
from visum.coverage import number_guided_summary
from visum.inference import generate_summary
from visum.metrics import audit_sample
from visum.numbers import extract_numbers
from visum.postprocess import (
    append_missing_numbers,
    drop_extra_number_sentences,
    repair_extra_numbers_by_source,
    repair_then_drop_extra_number_sentences,
)
from visum.text import normalize_whitespace, word_count


BARTPHO_DIR = ROOT / "outputs" / "bartpho-syllable-lora-cafef-stock"
VIT5_DIR = ROOT / "outputs" / "vit5-base-lora-cafef-stock"
TEST_FILE = ROOT / "data" / "processed_cafef_stock_1160" / "test.jsonl"

MODEL_PRESETS = {
    "BARTpho-syllable LoRA": {
        "path": str(BARTPHO_DIR),
        "prefix": "",
        "postprocess": "number_coverage",
    },
    "ViT5-base LoRA": {
        "path": str(VIT5_DIR),
        "prefix": "summarize: ",
        "postprocess": "repair_extra",
    },
    "Baseline extractive": {
        "path": "",
        "prefix": "",
        "postprocess": "none",
    },
    "Custom path": {
        "path": "",
        "prefix": "",
        "postprocess": "repair_extra",
    },
}

POSTPROCESS_LABELS = {
    "none": "Không hậu xử lý",
    "repair_extra": "Sửa số/đơn vị theo source",
    "drop_extra_sentences": "Xóa câu có số lạ",
    "repair_then_drop_extra_sentences": "Sửa rồi xóa câu còn số lạ",
    "append_missing": "Chèn danh sách số còn thiếu",
    "number_coverage": "Gom số liệu từ toàn bài",
}

NUMBER_MODE_LABELS = {
    "summary_subset": "Summary không được có số lạ",
    "exact": "Tập số phải khớp chính xác",
    "all_original": "Summary phải chứa mọi số trong source",
}

CSS = """
:root {
  --app-bg: #f7f8fb;
  --app-ink: #111827;
  --app-muted: #5b6475;
  --app-line: #d9dee8;
  --app-accent: #1663d8;
  --app-good: #137c43;
  --app-warn: #a15c00;
  --app-bad: #b42318;
}

.gradio-container {
  max-width: 1280px !important;
  margin: 0 auto !important;
  background: var(--app-bg) !important;
  color: var(--app-ink) !important;
}

.app-title h1 {
  font-size: 30px !important;
  line-height: 1.18 !important;
  margin-bottom: 8px !important;
}

.app-title p {
  color: var(--app-muted);
  max-width: 920px;
  font-size: 15px;
  line-height: 1.55;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.stat {
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: #ffffff;
  padding: 12px 14px;
}

.stat b {
  display: block;
  font-size: 12px;
  color: var(--app-muted);
  font-weight: 650;
  margin-bottom: 5px;
}

.stat span {
  font-size: 22px;
  font-weight: 760;
  color: var(--app-ink);
}

.ok { color: var(--app-good) !important; }
.warn { color: var(--app-warn) !important; }
.bad { color: var(--app-bad) !important; }

@media (max-width: 760px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .app-title h1 {
    font-size: 24px !important;
  }
}
"""


def load_examples(limit: int = 5) -> list[dict]:
    if not TEST_FILE.exists():
        return []

    examples: list[dict] = []
    with TEST_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            title = normalize_whitespace(row.get("title") or row.get("url") or row.get("id", "Sample"))
            examples.append(
                {
                    "label": f"{len(examples) + 1}. {title[:95]}",
                    "title": title,
                    "url": row.get("url", ""),
                    "source": row.get("source", ""),
                    "reference": row.get("summary", ""),
                }
            )
            if len(examples) >= limit:
                break
    return examples


EXAMPLES = load_examples()


def fetch_article_from_url(url: str) -> tuple[str, str]:
    url = (url or "").strip()
    if not url:
        return "", ""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise gr.Error("URL phải bắt đầu bằng http:// hoặc https://.")

    html_text = trafilatura.fetch_url(url)
    if not html_text:
        raise gr.Error("Không tải được URL. Hãy paste trực tiếp nội dung bài báo vào ô văn bản.")

    extracted = trafilatura.extract(
        html_text,
        output_format="json",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        url=url,
    )
    if not extracted:
        raise gr.Error("Không trích xuất được nội dung bài viết. Hãy paste trực tiếp nội dung.")

    payload = json.loads(extracted)
    title = normalize_whitespace(payload.get("title") or "")
    text = normalize_whitespace(payload.get("text") or "")
    if word_count(text) < 80:
        raise gr.Error("Nội dung trích xuất quá ngắn để tóm tắt ổn định.")

    return title, text


def apply_number_postprocess(
    source: str,
    summary: str,
    mode: str,
    min_ratio: float = 0.20,
    max_ratio: float = 0.25,
) -> str:
    if mode == "none":
        return summary
    if mode == "repair_extra":
        return repair_extra_numbers_by_source(source, summary)
    if mode == "drop_extra_sentences":
        return drop_extra_number_sentences(source, summary)
    if mode == "repair_then_drop_extra_sentences":
        return repair_then_drop_extra_number_sentences(source, summary)
    if mode == "append_missing":
        return append_missing_numbers(source, summary)
    if mode == "number_coverage":
        return number_guided_summary(source, summary, min_ratio=min_ratio, max_ratio=max_ratio)
    raise gr.Error(f"Chế độ hậu xử lý không hợp lệ: {mode}")


def metric_html(audit: dict, model_label: str, postprocess_label: str) -> str:
    number_class = "ok" if audit["number_ok"] else "bad"
    length_class = "ok" if audit["length_ok"] else "warn"
    escaped_model = html.escape(model_label)
    escaped_postprocess = html.escape(postprocess_label)
    return f"""
    <div class="stat-grid">
      <div class="stat"><b>Model</b><span>{escaped_model}</span></div>
      <div class="stat"><b>Compression</b><span class="{length_class}">{audit["compression_ratio"]:.2%}</span></div>
      <div class="stat"><b>Length 20-25%</b><span class="{length_class}">{"OK" if audit["length_ok"] else "FAIL"}</span></div>
      <div class="stat"><b>Number Check</b><span class="{number_class}">{"OK" if audit["number_ok"] else "FAIL"}</span></div>
    </div>
    <p style="margin:10px 0 0;color:#5b6475;font-size:13px">
      Source: {audit["source_words"]} từ · Summary: {audit["summary_words"]} từ · Hậu xử lý: {escaped_postprocess}
    </p>
    """


def number_rows(source: str, summary: str, audit: dict) -> list[list[str]]:
    rows: list[list[str]] = []
    source_numbers = extract_numbers(source)
    summary_numbers = extract_numbers(summary)
    rows.append(["Source numbers", str(len(source_numbers)), ", ".join(source_numbers[:40])])
    rows.append(["Summary numbers", str(len(summary_numbers)), ", ".join(summary_numbers[:40])])

    missing = audit.get("missing_numbers", [])
    extra = audit.get("extra_numbers", [])
    if extra:
        rows.append(["Số lạ trong summary", str(len(extra)), ", ".join(extra[:40])])
    if missing:
        rows.append(["Số thiếu nếu so exact", str(len(missing)), ", ".join(missing[:40])])
    if not missing and not extra:
        rows.append(["Audit", "OK", "Không phát hiện số thiếu hoặc số lạ."])
    return rows


def resolve_model(model_choice: str, custom_model_dir: str) -> tuple[str, str, str]:
    preset = MODEL_PRESETS.get(model_choice, MODEL_PRESETS["Baseline extractive"])
    model_dir = (custom_model_dir or "").strip() if model_choice == "Custom path" else preset["path"]
    prefix = preset["prefix"]
    return model_dir, prefix, preset["postprocess"]


def summarize_article(
    url: str,
    text: str,
    model_choice: str,
    custom_model_dir: str,
    postprocess_mode: str,
    number_mode: str,
    min_ratio: float,
    max_ratio: float,
    num_beams: int,
    length_penalty: float,
) -> tuple[str, str, str, list[list[str]], str]:
    source_title = ""
    source_text = (text or "").strip()
    if (url or "").strip():
        source_title, source_text = fetch_article_from_url(url)

    source_text = normalize_whitespace(source_text)
    if not source_text:
        raise gr.Error("Bạn cần nhập URL hoặc paste văn bản gốc.")
    if word_count(source_text) < 80:
        raise gr.Error("Văn bản quá ngắn. Demo nên dùng bài khoảng 80 từ trở lên.")

    if min_ratio <= 0 or max_ratio <= 0 or min_ratio >= max_ratio:
        raise gr.Error("Khoảng độ dài không hợp lệ. Min ratio phải nhỏ hơn max ratio.")

    model_dir, prefix, preset_postprocess = resolve_model(model_choice, custom_model_dir)
    selected_postprocess = postprocess_mode or preset_postprocess

    if model_choice == "Baseline extractive" or not model_dir:
        raw_summary = lead_summary(source_text, min_ratio=min_ratio, max_ratio=max_ratio, enforce_numbers=False)
    else:
        model_path = Path(model_dir)
        if not model_path.exists():
            raise gr.Error(f"Không tìm thấy checkpoint: {model_dir}")
        try:
            result = generate_summary(
                source_text,
                model_dir,
                prefix=prefix,
                min_ratio=min_ratio,
                max_ratio=max_ratio,
                num_beams=int(num_beams),
                length_penalty=float(length_penalty),
                number_postprocess="none",
            )
        except OSError as exc:
            raise gr.Error(
                "Không load được model. Hãy kiểm tra checkpoint/base model và dung lượng cache "
                f"ở {HF_CACHE}. Chi tiết: {exc}"
            ) from exc
        raw_summary = result["summary"]

    summary = apply_number_postprocess(
        source_text,
        raw_summary,
        selected_postprocess,
        min_ratio=min_ratio,
        max_ratio=max_ratio,
    )
    audit = audit_sample(source_text, summary, sample_id="", number_mode=number_mode).to_dict()
    postprocess_label = POSTPROCESS_LABELS.get(selected_postprocess, selected_postprocess)

    title_line = f"{source_title}\n\n" if source_title else ""
    source_preview = title_line + source_text
    metrics = metric_html(audit, model_choice, postprocess_label)
    numbers = number_rows(source_text, summary, audit)
    audit_note = (
        f"Chế độ so số: {NUMBER_MODE_LABELS.get(number_mode, number_mode)}\n"
        f"Raw summary words: {word_count(raw_summary)}\n"
        f"Final summary words: {audit['summary_words']}\n"
        f"Raw khác final: {'Có' if raw_summary != summary else 'Không'}"
    )
    return source_preview, summary, metrics, numbers, audit_note


def load_example(choice: str) -> tuple[str, str, str]:
    for item in EXAMPLES:
        if item["label"] == choice:
            return item["url"], item["source"], item["reference"]
    return "", "", ""


def default_model_choice() -> str:
    if BARTPHO_DIR.exists():
        return "BARTpho-syllable LoRA"
    if VIT5_DIR.exists():
        return "ViT5-base LoRA"
    return "Baseline extractive"


def build_demo(default_model_dir: str = ""):
    default_choice = "Custom path" if default_model_dir else default_model_choice()
    custom_default = default_model_dir

    with gr.Blocks(title="CafeF Number-Safe Summarizer") as demo:
        gr.Markdown(
            """
            # CafeF Number-Safe Summarizer
            Demo tóm tắt tin chứng khoán tiếng Việt với kiểm tra số liệu và ràng buộc độ dài 20-25%.
            Nhập URL CafeF hoặc paste nội dung bài viết, chọn model, rồi xem bản tóm tắt kèm audit số liệu.
            """,
            elem_classes=["app-title"],
        )

        with gr.Row():
            with gr.Column(scale=7):
                url = gr.Textbox(
                    label="URL bài báo",
                    placeholder="https://cafef.vn/...",
                    lines=1,
                )
                text = gr.Textbox(
                    label="Văn bản gốc",
                    placeholder="Paste nội dung bài viết tại đây nếu không dùng URL.",
                    lines=14,
                )
                if EXAMPLES:
                    with gr.Row():
                        example_choice = gr.Dropdown(
                            choices=[item["label"] for item in EXAMPLES],
                            label="Mẫu test có sẵn",
                            value=EXAMPLES[0]["label"],
                        )
                        load_btn = gr.Button("Tải mẫu", variant="secondary")
                reference = gr.Textbox(label="Reference summary của mẫu", lines=4, interactive=False)

            with gr.Column(scale=5):
                model_choice = gr.Dropdown(
                    choices=list(MODEL_PRESETS.keys()),
                    value=default_choice,
                    label="Model",
                )
                custom_model_dir = gr.Textbox(
                    value=custom_default,
                    label="Custom checkpoint path",
                    placeholder="outputs/bartpho-syllable-lora-cafef-stock",
                )
                postprocess_mode = gr.Dropdown(
                    choices=list(POSTPROCESS_LABELS.keys()),
                    value=MODEL_PRESETS.get(default_choice, MODEL_PRESETS["Baseline extractive"])["postprocess"],
                    label="Hậu xử lý số liệu",
                    info="repair_extra là lựa chọn cân bằng nhất trong thử nghiệm.",
                )
                number_mode = gr.Dropdown(
                    choices=list(NUMBER_MODE_LABELS.keys()),
                    value="summary_subset",
                    label="Chế độ audit số liệu",
                )
                with gr.Accordion("Cấu hình generation", open=False):
                    min_ratio = gr.Slider(0.05, 0.40, value=0.20, step=0.01, label="Min length ratio")
                    max_ratio = gr.Slider(0.10, 0.60, value=0.25, step=0.01, label="Max length ratio")
                    num_beams = gr.Slider(1, 6, value=2, step=1, label="Beam size")
                    length_penalty = gr.Slider(0.4, 2.0, value=0.9, step=0.05, label="Length penalty")

                run_btn = gr.Button("Tóm tắt và audit", variant="primary")

        gr.Markdown("## Kết quả")
        metrics = gr.HTML()
        with gr.Row():
            source_preview = gr.Textbox(label="Nội dung đã dùng", lines=10, interactive=False)
            summary = gr.Textbox(label="Bản tóm tắt", lines=10)
        numbers = gr.Dataframe(
            headers=["Nhóm", "Số lượng", "Giá trị"],
            datatype=["str", "str", "str"],
            label="Audit số liệu",
            interactive=False,
            wrap=True,
        )
        audit_note = gr.Textbox(label="Ghi chú xử lý", lines=4, interactive=False)

        run_btn.click(
            summarize_article,
            inputs=[
                url,
                text,
                model_choice,
                custom_model_dir,
                postprocess_mode,
                number_mode,
                min_ratio,
                max_ratio,
                num_beams,
                length_penalty,
            ],
            outputs=[source_preview, summary, metrics, numbers, audit_note],
        )

        if EXAMPLES:
            load_btn.click(
                load_example,
                inputs=[example_choice],
                outputs=[url, text, reference],
            )

    return demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", type=int, default=7860)
    parser.add_argument("--share", action="store_true")
    args = parser.parse_args()

    demo = build_demo(args.model_dir)
    demo.launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
        css=CSS,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
