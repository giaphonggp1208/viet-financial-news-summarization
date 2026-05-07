from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse

from visum.metrics import aggregate_audits, audit_sample


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                count += 1
    return count


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def domain_of(url: str) -> str:
    return urlparse(url or "").netloc.lower()


def cafe_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if domain_of(row.get("url", "")).endswith("cafef.vn")]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw/cafef_chung_khoan_all.jsonl")
    parser.add_argument("--annotation", default="data/processed/annotation_sheet.csv")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument(
        "--number-mode",
        choices=["exact", "all_original", "summary_subset"],
        default="summary_subset",
    )
    args = parser.parse_args()

    raw_path = Path(args.raw)
    annotation_path = Path(args.annotation)
    processed_dir = Path(args.processed_dir)

    raw_rows = read_jsonl(raw_path)
    annotation_rows = read_csv(annotation_path)
    annotated_rows = [
        row
        for row in annotation_rows
        if (row.get("summary") or "").strip()
    ]

    audits = []
    for row in annotated_rows:
        source = (row.get("text") or row.get("source") or "").strip()
        summary = (row.get("summary") or "").strip()
        if source and summary:
            audits.append(audit_sample(source, summary, sample_id=row.get("id", ""), number_mode=args.number_mode))

    stats = {
        "raw_file": str(raw_path),
        "raw_articles_total": len(raw_rows),
        "raw_articles_cafef": len(cafe_rows(raw_rows)),
        "annotation_file": str(annotation_path),
        "annotation_rows_total": len(annotation_rows),
        "annotation_rows_cafef": len(cafe_rows(annotation_rows)),
        "annotated_pairs_with_summary": len(annotated_rows),
        "train_rows": count_jsonl(processed_dir / "train.jsonl"),
        "val_rows": count_jsonl(processed_dir / "val.jsonl"),
        "test_rows": count_jsonl(processed_dir / "test.jsonl"),
        "validation_error_rows": count_jsonl(processed_dir / "validation_errors.jsonl"),
        "annotated_quality": aggregate_audits(audits),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
