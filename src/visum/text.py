from __future__ import annotations

import re
from typing import Iterable


WORD_RE = re.compile(
    r"\d+(?:[.,:/-]\d+)*|[A-Za-zÀ-ỹ]+(?:[-_][A-Za-zÀ-ỹ]+)*",
    flags=re.UNICODE,
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def word_tokens(text: str) -> list[str]:
    return WORD_RE.findall(normalize_whitespace(text))


def word_count(text: str) -> int:
    return len(word_tokens(text))


def compression_ratio(source: str, summary: str) -> float:
    source_words = word_count(source)
    if source_words == 0:
        return 0.0
    return word_count(summary) / source_words


def within_ratio(
    source: str,
    summary: str,
    lower: float = 0.20,
    upper: float = 0.25,
) -> bool:
    ratio = compression_ratio(source, summary)
    return lower <= ratio <= upper


def sentence_split(text: str) -> list[str]:
    text = normalize_whitespace(text)
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?;])\s+|(?<=\.)\s+(?=[A-ZÀ-Ỹ])", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def join_nonempty(items: Iterable[str], sep: str = " ") -> str:
    return normalize_whitespace(sep.join(item for item in items if item))

