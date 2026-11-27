"""
Soft identity for questions.

Two questions are "the same" when their normalized text matches. This lets
organizers reuse questions freely (no templates) while reports and tags still
group all uses together.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_question_text(text: str | None) -> str:
    value = unicodedata.normalize("NFKC", text or "").casefold()
    value = _PUNCT.sub(" ", value)
    return _WS.sub(" ", value).strip()


def question_key_for(text: str | None) -> str:
    normalized = normalize_question_text(text)
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:40]
