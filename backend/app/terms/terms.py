"""Medical terminology layer for diabetes domain.

Provides concept detection, query expansion, and Arabic text normalization.
Synonyms are only used on the query side and in routing, never to rewrite chunk text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TERMS_PATH = Path(__file__).resolve().parent / "diabetes_terms.json"

# Arabic diacritics (tashkeel) and tatweel
TASHKEEL_REGEX = re.compile(r"[\u064B-\u065F\u0670]")
TATWEEL_CHAR = "\u0640"


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text by removing tashkeel, tatweel, and unifying letter variants."""
    if not text:
        return ""
    # Remove diacritics and tatweel
    s = TASHKEEL_REGEX.sub("", text)
    s = s.replace(TATWEEL_CHAR, "")

    # Unify alef forms: أ, إ, آ, ٱ -> ا
    s = re.sub(r"[إأآٱ]", "ا", s)
    # Unify ya forms: ى -> ي
    s = re.sub(r"ى", "ي", s)
    # Unify taa marbuta: ة -> ه
    s = re.sub(r"ة", "ه", s)

    return s


def _load_terms() -> list[dict[str, Any]]:
    if not TERMS_PATH.exists():
        return []
    with open(TERMS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("concepts", [])


CONCEPTS: list[dict[str, Any]] = _load_terms()


def detect_concepts(text: str) -> list[dict[str, Any]]:
    """Detect diabetes concepts mentioned in text (case-insensitive and Arabic-normalized)."""
    if not text:
        return []

    norm_text = normalize_arabic(text).lower()
    matched = []

    # Check concepts
    for concept in CONCEPTS:
        canonical = concept.get("canonical_name", "")
        if canonical and canonical.lower() in norm_text:
            matched.append((len(canonical), concept))
            continue

        found = False
        for syn in concept.get("synonyms", []):
            pattern = r"\b" + re.escape(syn.lower()) + r"\b"
            if re.search(pattern, norm_text):
                matched.append((len(syn), concept))
                found = True
                break

        if found:
            continue

        for item in concept.get("arabic_synonyms", []):
            arabic_term = item.get("term", "")
            norm_arabic = normalize_arabic(arabic_term).lower()
            if norm_arabic and norm_arabic in norm_text:
                matched.append((len(norm_arabic), concept))
                found = True
                break

    # Sort matched by matched term length descending (e.g. UACR before Cr)
    matched.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in matched]


def expand_query(text: str) -> str:
    """Expand a query by appending canonical names and key synonyms of detected concepts."""
    if not text:
        return ""

    detected = detect_concepts(text)
    if not detected:
        return text

    additions = []
    text_lower = text.lower()

    for concept in detected:
        canonical = concept.get("canonical_name", "")
        if canonical and canonical.lower() not in text_lower:
            additions.append(canonical)

        for syn in concept.get("synonyms", []):
            if syn.lower() not in text_lower and syn not in additions:
                additions.append(syn)

    if not additions:
        return text

    return f"{text} ({', '.join(additions)})"
