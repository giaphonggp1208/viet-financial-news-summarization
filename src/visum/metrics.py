from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean

from .numbers import extra_numbers, missing_numbers, numbers_match
from .text import compression_ratio, word_count, within_ratio


@dataclass
class SampleAudit:
    id: str
    source_words: int
    summary_words: int
    compression_ratio: float
    length_ok: bool
    number_ok: bool
    missing_numbers: list[str]
    extra_numbers: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def audit_sample(
    source: str,
    summary: str,
    sample_id: str = "",
    lower: float = 0.20,
    upper: float = 0.25,
    number_mode: str = "exact",
) -> SampleAudit:
    return SampleAudit(
        id=sample_id,
        source_words=word_count(source),
        summary_words=word_count(summary),
        compression_ratio=round(compression_ratio(source, summary), 4),
        length_ok=within_ratio(source, summary, lower=lower, upper=upper),
        number_ok=numbers_match(source, summary, mode=number_mode),
        missing_numbers=missing_numbers(source, summary),
        extra_numbers=extra_numbers(source, summary),
    )


def aggregate_audits(audits: list[SampleAudit]) -> dict:
    if not audits:
        return {
            "number_accuracy": 0.0,
            "length_compliance": 0.0,
            "avg_compression_ratio": 0.0,
            "n_samples": 0,
        }
    return {
        "number_accuracy": mean(1.0 if item.number_ok else 0.0 for item in audits),
        "length_compliance": mean(1.0 if item.length_ok else 0.0 for item in audits),
        "avg_compression_ratio": mean(item.compression_ratio for item in audits),
        "n_samples": len(audits),
    }

