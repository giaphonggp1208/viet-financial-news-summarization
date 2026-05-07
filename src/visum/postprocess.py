from __future__ import annotations

from collections import Counter
import re

from .numbers import extra_numbers, extract_number_mentions, missing_numbers, number_counter
from .text import join_nonempty, sentence_split


NUMERIC_KEY_RE = re.compile(r"[-+]?\d+(?:[.,:/-]\d+)*")


def number_audit_text(source: str, summary: str) -> str:
    missing = missing_numbers(source, summary)
    extra = extra_numbers(source, summary)
    if not missing and not extra:
        return "OK: số liệu trong tóm tắt khớp với văn bản gốc."

    lines: list[str] = []
    if missing:
        lines.append("Thiếu trong tóm tắt: " + ", ".join(missing))
    if extra:
        lines.append("Số lạ trong tóm tắt: " + ", ".join(extra))
    return "\n".join(lines)


def append_missing_numbers(source: str, summary: str) -> str:
    missing = missing_numbers(source, summary)
    if not missing:
        return summary
    return join_nonempty(
        [summary, "Các số liệu bắt buộc còn thiếu: " + ", ".join(missing) + "."]
    )


def _number_key(canonical: str) -> str:
    match = NUMERIC_KEY_RE.search(canonical)
    if not match:
        return canonical
    return match.group(0)


def repair_extra_numbers_by_source(source: str, summary: str) -> str:
    """Replace generated number mentions with matching source mentions when only units differ."""
    source_mentions = extract_number_mentions(source)
    source_counter = number_counter(source)
    source_by_key: dict[str, list] = {}
    for mention in source_mentions:
        source_by_key.setdefault(_number_key(mention.canonical), []).append(mention)

    used: Counter[str] = Counter()
    replacements: list[tuple[int, int, str]] = []
    for mention in extract_number_mentions(summary):
        if used[mention.canonical] < source_counter.get(mention.canonical, 0):
            used[mention.canonical] += 1
            continue

        replacement = None
        for candidate in source_by_key.get(_number_key(mention.canonical), []):
            if used[candidate.canonical] < source_counter.get(candidate.canonical, 0):
                replacement = candidate.surface
                used[candidate.canonical] += 1
                break

        if replacement:
            replacements.append((mention.start, mention.end, replacement))
        else:
            used[mention.canonical] += 1

    repaired = summary
    for start, end, replacement in reversed(replacements):
        repaired = repaired[:start] + replacement + repaired[end:]
    return repaired


def drop_extra_number_sentences(source: str, summary: str) -> str:
    """Drop generated sentences that introduce numbers absent from the source."""
    allowed = number_counter(source)
    kept: list[str] = []

    for sentence in sentence_split(summary):
        sentence_numbers = number_counter(sentence)
        has_extra = any(count > allowed.get(value, 0) for value, count in sentence_numbers.items())
        if has_extra:
            continue

        kept.append(sentence)
        for value, count in sentence_numbers.items():
            allowed[value] -= count

    return join_nonempty(kept)


def repair_then_drop_extra_number_sentences(source: str, summary: str) -> str:
    repaired = repair_extra_numbers_by_source(source, summary)
    return drop_extra_number_sentences(source, repaired)
