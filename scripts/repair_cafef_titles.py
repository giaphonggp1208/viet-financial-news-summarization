from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def title_from_text(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def repair_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    rows: list[dict] = []
    fixed = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            if not (row.get("title") or "").strip():
                row["title"] = title_from_text(row.get("text", ""))
                fixed += 1
            rows.append(row)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return fixed


def repair_csv(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    fixed = 0
    for row in rows:
        if not (row.get("title") or "").strip():
            row["title"] = title_from_text(row.get("text", ""))
            fixed += 1
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return fixed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw/cafef_chung_khoan.jsonl")
    parser.add_argument("--annotation", default="data/processed/annotation_sheet.csv")
    args = parser.parse_args()

    raw_fixed = repair_jsonl(Path(args.raw))
    annotation_fixed = repair_csv(Path(args.annotation))
    print(f"Fixed raw titles: {raw_fixed}")
    print(f"Fixed annotation titles: {annotation_fixed}")


if __name__ == "__main__":
    main()
