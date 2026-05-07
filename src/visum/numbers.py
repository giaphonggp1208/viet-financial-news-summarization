from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable

from .text import normalize_whitespace


UNITS = [
    "đồng/cổ phiếu",
    "đồng/cp",
    "usd/ounce",
    "tấn/năm",
    "nghìn tỷ đồng",
    "ngàn tỷ đồng",
    "triệu cổ phiếu",
    "triệu doanh nghiệp",
    "triệu người",
    "triệu đồng",
    "triệu usd",
    "nghìn tỉ đồng",
    "ngàn tỉ đồng",
    "tỉ đồng",
    "tỷ đồng",
    "tỷ usd",
    "phần trăm",
    "cổ phiếu",
    "doanh nghiệp",
    "sinh viên",
    "học sinh",
    "nghìn tỷ",
    "ngàn tỷ",
    "nghìn",
    "ngàn",
    "triệu",
    "tỷ",
    "đồng",
    "vnd",
    "usd",
    "eur",
    "điểm",
    "người",
    "phiên",
    "tháng",
    "năm",
    "ngày",
    "lần",
    "ca",
    "cp",
    "km",
    "ha",
    "tấn",
    "m2",
    "%",
]

UNIT_PATTERN = "|".join(
    re.escape(unit).replace(r"\ ", r"\s+") for unit in sorted(UNITS, key=len, reverse=True)
)

DATE_RE = re.compile(
    r"""
    (?:
        \b[0-3]?\d\s*-\s*[0-3]?\d/[01]?\d(?:/\d{2,4})?\b
        |
        \b(?:ngày\s*)?[0-3]?\d[/-][01]?\d(?:[/-](?:\d{2}|\d{4}))?\b
        |
        \b(?:quý\s*[ivx]+|q[1-4])(?:\s*[/-]?\s*\d{4})?\b
        |
        \b(?:tháng\s*)[01]?\d(?:\s*[/-]\s*\d{4})?\b
    )
    """,
    flags=re.IGNORECASE | re.VERBOSE | re.UNICODE,
)

NUMBER_RE = re.compile(
    rf"""
    (?<![\wÀ-ỹ])
    [-+]?
    (?:
        \d{{1,3}}(?:[.,]\d{{3}})+(?:[,.]\d+)?
        |
        \d+(?:[,.]\d+)?
    )
    (?:\s*(?:{UNIT_PATTERN}))?
    (?![\wÀ-ỹ])
    """,
    flags=re.IGNORECASE | re.VERBOSE | re.UNICODE,
)


@dataclass(frozen=True)
class NumberMention:
    surface: str
    canonical: str
    start: int
    end: int
    kind: str


def _overlaps(span: tuple[int, int], spans: Iterable[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in spans)


def canonicalize_number(surface: str) -> str:
    value = normalize_whitespace(surface).lower()
    value = re.sub(r"^ngày\s+", "", value)
    value = re.sub(r"\btỉ\b", "tỷ", value)
    value = re.sub(r"\s+%", "%", value)
    value = re.sub(r"\s+/", "/", value)
    value = re.sub(r"/\s+", "/", value)
    value = re.sub(r"\s+", " ", value)
    return value


def extract_number_mentions(text: str) -> list[NumberMention]:
    text = text or ""
    candidates: list[NumberMention] = []

    for match in DATE_RE.finditer(text):
        surface = match.group(0)
        candidates.append(
            NumberMention(
                surface=surface,
                canonical=canonicalize_number(surface),
                start=match.start(),
                end=match.end(),
                kind="date",
            )
        )

    for match in NUMBER_RE.finditer(text):
        surface = match.group(0)
        candidates.append(
            NumberMention(
                surface=surface,
                canonical=canonicalize_number(surface),
                start=match.start(),
                end=match.end(),
                kind="number",
            )
        )

    candidates.sort(key=lambda item: (item.start, -(item.end - item.start)))
    selected: list[NumberMention] = []
    selected_spans: list[tuple[int, int]] = []
    for item in candidates:
        span = (item.start, item.end)
        if _overlaps(span, selected_spans):
            continue
        selected.append(item)
        selected_spans.append(span)
    return selected


def extract_numbers(text: str) -> list[str]:
    return [item.canonical for item in extract_number_mentions(text)]


def number_counter(text: str) -> Counter[str]:
    return Counter(extract_numbers(text))


def missing_numbers(source: str, summary: str) -> list[str]:
    source_counter = number_counter(source)
    summary_counter = number_counter(summary)
    missing: list[str] = []
    for value, count in source_counter.items():
        delta = count - summary_counter.get(value, 0)
        missing.extend([value] * max(delta, 0))
    return missing


def extra_numbers(source: str, summary: str) -> list[str]:
    source_counter = number_counter(source)
    summary_counter = number_counter(summary)
    extra: list[str] = []
    for value, count in summary_counter.items():
        delta = count - source_counter.get(value, 0)
        extra.extend([value] * max(delta, 0))
    return extra


def numbers_match(source: str, summary: str, mode: str = "exact") -> bool:
    source_counter = number_counter(source)
    summary_counter = number_counter(summary)
    if mode == "exact":
        return source_counter == summary_counter
    if mode == "all_original":
        return not missing_numbers(source, summary)
    if mode == "summary_subset":
        return not extra_numbers(source, summary)
    raise ValueError(f"Unknown number comparison mode: {mode}")
