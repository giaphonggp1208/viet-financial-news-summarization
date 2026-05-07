from __future__ import annotations

from math import floor

from .numbers import extract_number_mentions, extract_numbers
from .text import join_nonempty, sentence_split, word_count


FINANCE_KEYWORDS = [
    "doanh thu",
    "lợi nhuận",
    "lãi",
    "lỗ",
    "tăng",
    "giảm",
    "cổ tức",
    "vốn",
    "tài sản",
    "dư nợ",
    "nợ xấu",
    "thanh khoản",
    "vn-index",
    "huy động",
    "kế hoạch",
    "mục tiêu",
    "giá",
    "tỷ lệ",
]


def _ordered_unique_numbers(text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for mention in extract_number_mentions(text):
        if mention.canonical in seen:
            continue
        seen.add(mention.canonical)
        values.append(mention.surface)
    return values


def _sentence_score(sentence: str, index: int, total: int, covered_numbers: set[str]) -> float:
    lower = sentence.lower()
    numbers = extract_numbers(sentence)
    new_numbers = [value for value in numbers if value not in covered_numbers]
    keyword_hits = sum(1 for keyword in FINANCE_KEYWORDS if keyword in lower)
    position = index / max(total - 1, 1)

    score = 1.0
    score += 4.0 * len(set(new_numbers))
    score += 1.3 * keyword_hits
    if index <= 1:
        score += 1.8
    if position >= 0.35 and numbers:
        score += 2.2
    if word_count(sentence) > 80:
        score *= 0.65
    return score


def _can_add(current: list[str], sentence: str, source_words: int, max_ratio: float) -> bool:
    max_words = max(1, floor(source_words * max_ratio))
    return word_count(join_nonempty([*current, sentence])) <= max_words


def _add_best_sentence(
    selected: list[int],
    sentences: list[str],
    source_words: int,
    max_ratio: float,
    covered_numbers: set[str],
    *,
    require_new_number: bool,
) -> bool:
    current = [sentences[index] for index in sorted(selected)]
    best_index = -1
    best_density = -1.0

    for index, sentence in enumerate(sentences):
        if index in selected:
            continue
        numbers = set(extract_numbers(sentence))
        if require_new_number and not (numbers - covered_numbers):
            continue
        if not _can_add(current, sentence, source_words, max_ratio):
            continue

        score = _sentence_score(sentence, index, len(sentences), covered_numbers)
        density = score / max(word_count(sentence), 1)
        if density > best_density:
            best_index = index
            best_density = density

    if best_index < 0:
        return False

    selected.append(best_index)
    covered_numbers.update(extract_numbers(sentences[best_index]))
    return True


def _append_number_tail(source: str, summary: str, source_words: int, max_ratio: float) -> str:
    max_words = max(1, floor(source_words * max_ratio))
    used = set(extract_numbers(summary))
    tail_numbers: list[str] = []

    for number in _ordered_unique_numbers(source):
        canonical = extract_numbers(number)
        key = canonical[0] if canonical else number.lower()
        if key in used:
            continue
        candidate_numbers = [*tail_numbers, number]
        candidate_tail = "Số liệu khác: " + "; ".join(candidate_numbers) + "."
        candidate = join_nonempty([summary, candidate_tail])
        if word_count(candidate) > max_words:
            break
        tail_numbers.append(number)
        used.add(key)

    if not tail_numbers:
        return summary
    return join_nonempty([summary, "Số liệu khác: " + "; ".join(tail_numbers) + "."])


def number_guided_summary(
    source: str,
    draft_summary: str = "",
    *,
    min_ratio: float = 0.20,
    max_ratio: float = 0.25,
) -> str:
    """Build a source-grounded summary that covers number-bearing sentences across the article."""
    sentences = [sentence for sentence in sentence_split(source) if word_count(sentence) >= 4]
    if not sentences:
        return draft_summary.strip()

    source_words = word_count(source)
    min_words = max(1, int(source_words * min_ratio))
    selected: list[int] = []
    covered_numbers: set[str] = set()

    # Seed with a concise opening sentence and a high-value numeric sentence from later in the article.
    for index in range(min(2, len(sentences))):
        if _can_add([sentences[i] for i in selected], sentences[index], source_words, max_ratio):
            selected.append(index)
            covered_numbers.update(extract_numbers(sentences[index]))
            break

    later_candidates = [
        index
        for index, sentence in enumerate(sentences)
        if index not in selected and index / max(len(sentences) - 1, 1) >= 0.35 and extract_numbers(sentence)
    ]
    if later_candidates:
        best_later = max(
            later_candidates,
            key=lambda idx: _sentence_score(sentences[idx], idx, len(sentences), covered_numbers)
            / max(word_count(sentences[idx]), 1),
        )
        if _can_add([sentences[i] for i in selected], sentences[best_later], source_words, max_ratio):
            selected.append(best_later)
            covered_numbers.update(extract_numbers(sentences[best_later]))

    while word_count(join_nonempty(sentences[index] for index in sorted(selected))) < min_words:
        if _add_best_sentence(
            selected,
            sentences,
            source_words,
            max_ratio,
            covered_numbers,
            require_new_number=True,
        ):
            continue
        if not _add_best_sentence(
            selected,
            sentences,
            source_words,
            max_ratio,
            covered_numbers,
            require_new_number=False,
        ):
            break

    # Use remaining room for compact exact number mentions from later parts of the source.
    summary = join_nonempty(sentences[index] for index in sorted(selected))
    summary = _append_number_tail(source, summary, source_words, max_ratio)

    # If the selected source sentences are still too short, keep the model draft as a fallback.
    if word_count(summary) < min_words and draft_summary:
        candidate = join_nonempty([summary, draft_summary])
        if word_count(candidate) <= floor(source_words * max_ratio):
            summary = candidate

    return summary
