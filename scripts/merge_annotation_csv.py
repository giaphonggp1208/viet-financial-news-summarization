from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dedupe-key", default="url", choices=["url", "id"])
    parser.add_argument("--stats-output", default="")
    args = parser.parse_args()

    merged: list[dict] = []
    seen: set[str] = set()
    duplicates = 0
    fieldnames: list[str] = []

    for input_path in [Path(item) for item in args.inputs]:
        rows = read_csv(input_path)
        for row in rows:
            key = str(row.get(args.dedupe_key, "")).strip()
            if key and key in seen:
                duplicates += 1
                continue
            if key:
                seen.add(key)
            for field in row:
                if field not in fieldnames:
                    fieldnames.append(field)
            merged.append(row)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    stats = {
        "inputs": args.inputs,
        "output": args.output,
        "rows": len(merged),
        "duplicates_skipped": duplicates,
        "dedupe_key": args.dedupe_key,
    }
    if args.stats_output:
        Path(args.stats_output).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
