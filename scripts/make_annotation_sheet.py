from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse

from visum.numbers import extract_numbers
from visum.text import word_count


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def matches_allowed_domain(row: dict, allowed_domain: str) -> bool:
    if not allowed_domain:
        return True
    url = row.get("url", "")
    netloc = urlparse(url).netloc.lower()
    allowed = allowed_domain.lower()
    return netloc == allowed or netloc.endswith("." + allowed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/articles.jsonl")
    parser.add_argument("--output", default="data/processed/annotation_sheet.csv")
    parser.add_argument("--allowed-domain", default="cafef.vn")
    parser.add_argument("--min-numbers", type=int, default=5)
    parser.add_argument("--min-words", type=int, default=250)
    args = parser.parse_args()

    rows = []
    skipped_domain = 0
    skipped_quality = 0
    for row in read_jsonl(Path(args.input)):
        if not matches_allowed_domain(row, args.allowed_domain):
            skipped_domain += 1
            continue
        text = row.get("text") or row.get("source") or ""
        if word_count(text) < args.min_words or len(extract_numbers(text)) < args.min_numbers:
            skipped_quality += 1
            continue
        rows.append(row)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "id",
        "url",
        "source",
        "title",
        "published_at",
        "original_word_count",
        "numbers_original",
        "text",
        "summary",
        "notes",
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            text = row.get("text") or row.get("source") or ""
            writer.writerow(
                {
                    "id": row.get("id", ""),
                    "url": row.get("url", ""),
                    "source": row.get("source", ""),
                    "title": row.get("title", ""),
                    "published_at": row.get("published_at", ""),
                    "original_word_count": word_count(text),
                    "numbers_original": "; ".join(extract_numbers(text)),
                    "text": text,
                    "summary": "",
                    "notes": "",
                }
            )

    print(f"Saved {len(rows)} rows to annotation sheet: {out_path}")
    print(f"Skipped by domain: {skipped_domain}")
    print(f"Skipped by min words/numbers: {skipped_quality}")


if __name__ == "__main__":
    main()
