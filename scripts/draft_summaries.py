from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from visum.baseline import lead_summary
from visum.metrics import aggregate_audits, audit_sample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/annotation_sheet.csv")
    parser.add_argument("--output", default="data/processed/annotation_sheet_draft.csv")
    parser.add_argument("--stats-output", default="data/processed/draft_stats.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--mode",
        choices=["length_only", "append_missing_numbers"],
        default="length_only",
    )
    args = parser.parse_args()

    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if args.limit:
        rows_to_fill = rows[: args.limit]
        untouched_rows = rows[args.limit :]
    else:
        rows_to_fill = rows
        untouched_rows = []

    enforce_numbers = args.mode == "append_missing_numbers"
    audits = []
    for row in rows_to_fill:
        text = row.get("text", "")
        summary = lead_summary(text, enforce_numbers=enforce_numbers)
        row["summary"] = summary
        row["notes"] = (
            f"AUTO_DRAFT_{args.mode}: cần biên tập thủ công trước khi dùng làm dataset chuẩn."
        )
        audits.append(audit_sample(text, summary, sample_id=row.get("id", "")))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_fill + untouched_rows)

    stats = aggregate_audits(audits)
    stats["mode"] = args.mode
    stats["draft_rows"] = len(rows_to_fill)
    stats["output"] = str(out_path)
    with Path(args.stats_output).open("w", encoding="utf-8") as file:
        json.dump(stats, file, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

