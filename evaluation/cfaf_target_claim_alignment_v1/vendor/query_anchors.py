"""Selected pure functions from InfoBank main 8079f29dc3a97273f51b55b2a22f9ff896a2e758. See reuse manifest."""
from __future__ import annotations
import re
from typing import Sequence
def _keyword_tokens(value: str) -> tuple[str, ...]:
    """Return stable lexical tokens used only against an allowed vocabulary."""

    return tuple(re.findall(r"[^\W_]+", str(value).casefold(), flags=re.UNICODE))


def deterministic_allowed_keyword_matches(
    text: str,
    available_keywords: Sequence[str] | None,
    *,
    limit: int = 5,
) -> list[str]:
    """Select explicit question/keyword overlaps without expanding governance.

    The caller supplies the already permitted vocabulary. A keyword matches
    only when all of its lexical tokens occur in the question; contiguous
    phrase matches rank first, followed by more specific (multi-token) values
    and a stable lexical tie-break. No synonym inference is attempted here --
    that remains the provider's optional contribution.
    """

    if limit <= 0 or not available_keywords:
        return []
    question_tokens = _keyword_tokens(text)
    if not question_tokens:
        return []
    question_token_set = set(question_tokens)
    canonical_by_key: dict[str, str] = {}
    for value in sorted((str(item).strip() for item in available_keywords), key=lambda item: (item.casefold(), item)):
        if value:
            canonical_by_key.setdefault(value.casefold(), value)

    ranked: list[tuple[int, int, str, str]] = []
    for key, canonical in canonical_by_key.items():
        tokens = _keyword_tokens(canonical)
        if not tokens or not set(tokens).issubset(question_token_set):
            continue
        phrase_match = any(
            question_tokens[index:index + len(tokens)] == tokens
            for index in range(len(question_tokens) - len(tokens) + 1)
        )
        ranked.append((0 if phrase_match else 1, -len(tokens), key, canonical))
    return [item[3] for item in sorted(ranked)[:limit]]

