from __future__ import annotations

from .numbers import missing_numbers
from .text import join_nonempty, sentence_split, word_count


def lead_summary(
    text: str,
    min_ratio: float = 0.20,
    max_ratio: float = 0.25,
    enforce_numbers: bool = True,
) -> str:
    sentences = sentence_split(text)
    if not sentences:
        return ""

    target_min = max(1, int(word_count(text) * min_ratio))
    target_max = max(target_min, int(word_count(text) * max_ratio))
    chosen: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = word_count(sentence)
        if chosen and current_words + sentence_words > target_max:
            break
        chosen.append(sentence)
        current_words += sentence_words
        if current_words >= target_min:
            break

    summary = join_nonempty(chosen)
    if enforce_numbers:
        missing = missing_numbers(text, summary)
        if missing:
            summary = join_nonempty(
                [summary, "Số liệu cần giữ nguyên: " + ", ".join(missing) + "."]
            )
    return summary

