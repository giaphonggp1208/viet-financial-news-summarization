from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from .coverage import number_guided_summary
from .metrics import audit_sample
from .postprocess import (
    append_missing_numbers,
    drop_extra_number_sentences,
    repair_extra_numbers_by_source,
    repair_then_drop_extra_number_sentences,
)
from .text import word_count


@lru_cache(maxsize=2)
def load_seq2seq(model_dir: str) -> tuple[Any, Any]:
    model_path = Path(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    if (model_path / "adapter_config.json").exists():
        from peft import PeftConfig, PeftModel

        peft_config = PeftConfig.from_pretrained(model_dir)
        base_model = AutoModelForSeq2SeqLM.from_pretrained(peft_config.base_model_name_or_path)
        model = PeftModel.from_pretrained(base_model, model_dir)
    else:
        model = AutoModelForSeq2SeqLM.from_pretrained(model_dir)
    model.eval()
    return tokenizer, model


def dynamic_length_bounds(
    source_text: str,
    tokenizer: Any,
    min_ratio: float = 0.20,
    max_ratio: float = 0.25,
    max_source_length: int = 1024,
) -> tuple[int, int]:
    token_count = len(
        tokenizer(
            source_text,
            truncation=True,
            max_length=max_source_length,
            add_special_tokens=True,
        )["input_ids"]
    )
    min_length = max(8, int(token_count * min_ratio))
    max_length = max(min_length + 1, int(token_count * max_ratio))
    return min_length, max_length


def generate_summary(
    source_text: str,
    model_dir: str | Path,
    *,
    tokenizer: Any | None = None,
    model: Any | None = None,
    prefix: str = "",
    min_ratio: float = 0.20,
    max_ratio: float = 0.25,
    max_source_length: int = 1024,
    num_beams: int = 4,
    length_penalty: float = 1.0,
    no_repeat_ngram_size: int = 3,
    enforce_numbers: bool = False,
    number_postprocess: str = "none",
) -> dict:
    if tokenizer is None or model is None:
        tokenizer, model = load_seq2seq(str(model_dir))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    source_for_model = f"{prefix}{source_text}" if prefix else source_text
    min_length, max_length = dynamic_length_bounds(
        source_for_model,
        tokenizer,
        min_ratio=min_ratio,
        max_ratio=max_ratio,
        max_source_length=max_source_length,
    )

    inputs = tokenizer(
        source_for_model,
        return_tensors="pt",
        truncation=True,
        max_length=max_source_length,
    ).to(device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            num_beams=num_beams,
            min_length=min_length,
            max_length=max_length,
            length_penalty=length_penalty,
            no_repeat_ngram_size=no_repeat_ngram_size,
            early_stopping=True,
        )

    summary = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
    if enforce_numbers:
        summary = append_missing_numbers(source_text, summary)
    if number_postprocess == "append_missing":
        summary = append_missing_numbers(source_text, summary)
    elif number_postprocess == "number_coverage":
        summary = number_guided_summary(
            source_text,
            summary,
            min_ratio=min_ratio,
            max_ratio=max_ratio,
        )
    elif number_postprocess == "repair_extra":
        summary = repair_extra_numbers_by_source(source_text, summary)
    elif number_postprocess == "drop_extra_sentences":
        summary = drop_extra_number_sentences(source_text, summary)
    elif number_postprocess == "repair_then_drop_extra_sentences":
        summary = repair_then_drop_extra_number_sentences(source_text, summary)
    elif number_postprocess != "none":
        raise ValueError(f"Unknown number_postprocess: {number_postprocess}")

    audit = audit_sample(source_text, summary)
    return {
        "summary": summary,
        "audit": audit.to_dict(),
        "source_words": word_count(source_text),
        "summary_words": word_count(summary),
    }
