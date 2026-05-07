from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--key", default="url")
    args = parser.parse_args()

    merged: list[dict] = []
    seen: set[str] = set()
    for input_path in args.input:
        for row in read_jsonl(Path(input_path)):
            key = row.get(args.key) or row.get("id")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(row)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        for row in merged:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Merged {len(merged)} rows to {out_path}")


if __name__ == "__main__":
    main()
