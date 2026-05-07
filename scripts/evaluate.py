from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from rouge_score import rouge_scorer, scoring
from tqdm import tqdm

from visum.inference import generate_summary, load_seq2seq
from visum.metrics import aggregate_audits, audit_sample


def read_jsonl(path: Path) -> list[dict]:
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


def compute_overlap_metrics(predictions: list[str], references: list[str]) -> dict:
    metrics: dict = {}
    try:
        rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
        aggregator = scoring.BootstrapAggregator()
        for pred, ref in zip(predictions, references):
            aggregator.add_scores(rouge.score(ref, pred))
        metrics.update(
            {
                key: round(value.mid.fmeasure * 100, 4)
                for key, value in aggregator.aggregate().items()
            }
        )
    except Exception as exc:  # pragma: no cover - depends on optional packages/network cache
        metrics["rouge_error"] = str(exc)

    try:
        import sacrebleu

        bleu = sacrebleu.corpus_bleu(predictions, [references])
        metrics["BLEU"] = round(float(bleu.score), 4)
    except Exception as exc:  # pragma: no cover
        metrics["bleu_error"] = str(exc)

    try:
        from bert_score import score

        _, _, f1 = score(predictions, references, lang="vi", verbose=False)
        metrics["BERTScore_F1"] = round(float(f1.mean().item()) * 100, 4)
    except Exception as exc:  # pragma: no cover
        metrics["bertscore_error"] = str(exc)

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--test-file", default="data/processed/test.jsonl")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--num-beams", type=int, default=4)
    parser.add_argument("--length-penalty", type=float, default=1.0)
    parser.add_argument("--min-ratio", type=float, default=0.20)
    parser.add_argument("--max-ratio", type=float, default=0.25)
    parser.add_argument("--number-mode", choices=["exact", "all_original", "summary_subset"], default="exact")
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

    rows = read_jsonl(Path(args.test_file))
    if args.max_samples:
        rows = rows[: args.max_samples]

    tokenizer, model = load_seq2seq(args.model_dir)
    predictions: list[str] = []
    references: list[str] = []
    audits = []
    output_rows: list[dict] = []

    for row in tqdm(rows, desc="Generating"):
        result = generate_summary(
            row["source"],
            args.model_dir,
            tokenizer=tokenizer,
            model=model,
            prefix=args.prefix,
            min_ratio=args.min_ratio,
            max_ratio=args.max_ratio,
            num_beams=args.num_beams,
            length_penalty=args.length_penalty,
            enforce_numbers=args.enforce_numbers,
            number_postprocess=args.number_postprocess,
        )
        pred = result["summary"]
        predictions.append(pred)
        references.append(row["summary"])
        audit = audit_sample(row["source"], pred, sample_id=row.get("id", ""), number_mode=args.number_mode)
        audits.append(audit)
        output_rows.append(
            {
                "id": row.get("id", ""),
                "url": row.get("url", ""),
                "source": row["source"],
                "reference": row["summary"],
                "prediction": pred,
                "audit": audit.to_dict(),
            }
        )

    metrics = compute_overlap_metrics(predictions, references)
    metrics.update(aggregate_audits(audits))
    metrics["prediction_word_mean"] = float(np.mean([audit.summary_words for audit in audits])) if audits else 0.0
    metrics["reference_word_mean"] = float(np.mean([len(ref.split()) for ref in references])) if references else 0.0

    output_dir = Path(args.output_dir or Path(args.model_dir) / "eval")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "predictions.jsonl", output_rows)
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
