from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from visum.metrics import aggregate_audits, audit_sample


def read_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/annotation_sheet.csv")
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lower-ratio", type=float, default=0.20)
    parser.add_argument("--upper-ratio", type=float, default=0.25)
    parser.add_argument("--number-mode", choices=["exact", "all_original", "summary_subset"], default="exact")
    parser.add_argument("--allow-invalid", action="store_true")
    parser.add_argument("--min-train", type=int, default=500)
    parser.add_argument("--min-test", type=int, default=100)
    args = parser.parse_args()

    raw_rows = read_rows(Path(args.input))
    valid_rows: list[dict] = []
    error_rows: list[dict] = []

    for index, row in enumerate(raw_rows):
        source = (row.get("text") or row.get("source") or "").strip()
        summary = (row.get("summary") or "").strip()
        sample_id = row.get("id") or f"row-{index:05d}"
        if not source or not summary:
            continue

        audit = audit_sample(
            source,
            summary,
            sample_id=sample_id,
            lower=args.lower_ratio,
            upper=args.upper_ratio,
            number_mode=args.number_mode,
        )
        prepared = {
            "id": sample_id,
            "url": row.get("url", ""),
            "title": row.get("title", ""),
            "source": source,
            "summary": summary,
            "audit": audit.to_dict(),
        }
        if audit.length_ok and audit.number_ok:
            valid_rows.append(prepared)
        else:
            error_rows.append(prepared)
            if args.allow_invalid:
                valid_rows.append(prepared)

    random.Random(args.seed).shuffle(valid_rows)
    n_total = len(valid_rows)
    n_train = int(n_total * 0.8)
    n_val = int(n_total * 0.1)
    train_rows = valid_rows[:n_train]
    val_rows = valid_rows[n_train : n_train + n_val]
    test_rows = valid_rows[n_train + n_val :]

    out_dir = Path(args.output_dir)
    write_jsonl(out_dir / "train.jsonl", train_rows)
    write_jsonl(out_dir / "val.jsonl", val_rows)
    write_jsonl(out_dir / "test.jsonl", test_rows)
    write_jsonl(out_dir / "validation_errors.jsonl", error_rows)

    stats = {
        "valid_total": n_total,
        "invalid_total": len(error_rows),
        "train": len(train_rows),
        "val": len(val_rows),
        "test": len(test_rows),
        "quality": aggregate_audits(
            [
                audit_sample(
                    row["source"],
                    row["summary"],
                    row["id"],
                    lower=args.lower_ratio,
                    upper=args.upper_ratio,
                    number_mode=args.number_mode,
                )
                for row in valid_rows
            ]
        ),
        "warnings": [],
    }
    if len(train_rows) < args.min_train:
        stats["warnings"].append(f"Train set has {len(train_rows)} samples; required >= {args.min_train}.")
    if len(test_rows) < args.min_test:
        stats["warnings"].append(f"Test set has {len(test_rows)} samples; required >= {args.min_test}.")

    with (out_dir / "dataset_stats.json").open("w", encoding="utf-8") as file:
        json.dump(stats, file, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
