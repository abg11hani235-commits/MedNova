"""Deterministic citation and claim verifier (app/rag/verify.py).

Pure deterministic code, no LLM.
Rules:
1. chunk_id must belong to the specified patient.
2. quote must be a substring of the ORIGINAL chunk text (after whitespace normalization).
3. every number in the claim text must appear in the quote or the cited chunk.
If no claims survive, returns REFUSAL_TEXT with answerable=False.
"""

from __future__ import annotations

import re
from typing import Any

from app.constants import REFUSAL_TEXT


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace by collapsing multiple spaces, tabs, and newlines."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_numbers(text: str) -> list[str]:
    """Extract all integer and floating-point numbers from text."""
    if not text:
        return []
    # Matches numbers like 7.4, 59, 134, 82, 2025
    return re.findall(r"\b\d+(?:\.\d+)?\b", text)


def verify_claims(
    patient_id: str,
    claims: list[dict[str, Any]],
    chunks_by_id: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    """Verify generated claims against original chunk texts.

    Returns:
    - surviving_claims: list of validated claims
    - citations: list of unique citation dicts {"chunk_id": ..., "quote": ...}
    - valid: True if at least one claim survived verification, False otherwise
    """
    surviving_claims = []
    seen_citations = set()
    citations = []

    for claim in claims:
        chunk_id = claim.get("chunk_id", "")
        quote = claim.get("quote", "")
        claim_text = claim.get("text", "")

        # 1. Patient isolation and chunk existence
        chunk = chunks_by_id.get(chunk_id)
        if not chunk or getattr(chunk, "patient_id", None) != patient_id:
            continue

        # 2. Quote must be a non-empty substring of original chunk text
        orig_text = getattr(chunk, "text", "")
        norm_orig = normalize_whitespace(orig_text)
        norm_quote = normalize_whitespace(quote)

        if not norm_quote or norm_quote not in norm_orig:
            continue

        # 3. Every number in claim text must appear in quote or chunk text
        claim_numbers = extract_numbers(claim_text)
        quote_or_chunk = f"{quote} {orig_text}"
        numbers_valid = True
        for num in claim_numbers:
            # Check if num appears in quote or chunk
            pattern = r"(?:\b|_)" + re.escape(num) + r"(?:\b|_)"
            if not re.search(pattern, quote_or_chunk):
                numbers_valid = False
                break

        if not numbers_valid:
            continue

        # Claim passed all verification checks
        surviving_claims.append(claim)
        cit_key = (chunk_id, quote)
        if cit_key not in seen_citations:
            seen_citations.add(cit_key)
            citations.append({"chunk_id": chunk_id, "quote": quote})

    valid = len(surviving_claims) > 0
    return surviving_claims, citations, valid


def apply_verifier(
    patient_id: str,
    model_response: dict[str, Any],
    chunks_by_id: dict[str, Any],
) -> dict[str, Any]:
    """Apply the verifier to a raw LLM response.

    If answerable is False or no claims survive, reverts to REFUSAL_TEXT.
    """
    raw_answerable = model_response.get("answerable", False)
    raw_answer = model_response.get("answer", "")
    claims = model_response.get("claims", [])

    if not raw_answerable:
        return {
            "answer": REFUSAL_TEXT,
            "answerable": False,
            "claims": [],
            "citations": [],
        }

    surviving_claims, citations, valid = verify_claims(patient_id, claims, chunks_by_id)

    if not valid:
        return {
            "answer": REFUSAL_TEXT,
            "answerable": False,
            "claims": [],
            "citations": [],
        }

    return {
        "answer": raw_answer,
        "answerable": True,
        "claims": surviving_claims,
        "citations": citations,
    }
