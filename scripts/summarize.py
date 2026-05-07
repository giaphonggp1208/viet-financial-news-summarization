from __future__ import annotations

import argparse
from pathlib import Path

from visum.baseline import lead_summary
from visum.coverage import number_guided_summary
from visum.inference import generate_summary
from visum.postprocess import (
    append_missing_numbers,
    drop_extra_number_sentences,
    number_audit_text,
    repair_extra_numbers_by_source,
    repair_then_drop_extra_number_sentences,
)


def apply_postprocess(source: str, summary: str, mode: str) -> str:
    if mode == "none":
        return summary
    if mode == "append_missing":
        return append_missing_numbers(source, summary)
    if mode == "repair_extra":
        return repair_extra_numbers_by_source(source, summary)
    if mode == "drop_extra_sentences":
        return drop_extra_number_sentences(source, summary)
    if mode == "repair_then_drop_extra_sentences":
        return repair_then_drop_extra_number_sentences(source, summary)
    if mode == "number_coverage":
        return number_guided_summary(source, summary)
    raise ValueError(f"Unknown postprocess mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--file", default="")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--enforce-numbers", action="store_true")
    parser.add_argument(
        "--number-postprocess",
        choices=[
            "none",
            "append_missing",
            "repair_extra",
            "drop_extra_sentences",
            "repair_then_drop_extra_sentences",
            "number_coverage",
        ],
        default="none",
    )
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.text
    if not text.strip():
        raise SystemExit("Provide --text or --file.")

    if args.baseline or not args.model_dir:
        summary = lead_summary(text, enforce_numbers=args.enforce_numbers)
        summary = apply_postprocess(text, summary, args.number_postprocess)
        print(summary)
        print("\n--- Number audit ---")
        print(number_audit_text(text, summary))
        return

    result = generate_summary(
        text,
        args.model_dir,
        prefix=args.prefix,
        enforce_numbers=args.enforce_numbers,
        number_postprocess=args.number_postprocess,
    )
    print(result["summary"])
    print("\n--- Audit ---")
    print(result["audit"])


if __name__ == "__main__":
    main()
