"""
Name normalization and fuzzy matching utilities.
Used to cross-reference Salesforce contact names against API response names.
"""
import re
from typing import Optional
from rapidfuzz import fuzz


def normalize_name(name: str) -> str:
    """
    Lowercase, strip punctuation, handle last-name-first formats.
    Examples:
      "SMITH, JOHN R."  -> "john r smith"
      "Dr. Jane O'Brien-Clark" -> "jane obrien clark"
    """
    if not name:
        return ""
    # Handle "LAST, FIRST" format (common in FEC data)
    if ',' in name:
        parts = name.split(',', 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    name = name.lower()
    name = re.sub(r'\b(dr|mr|mrs|ms|prof|rev|jr|sr|ii|iii|iv)\b\.?', '', name)
    name = re.sub(r"[^a-z\s]", ' ', name)
    name = ' '.join(name.split())
    return name


def build_name_variants(first: str, last: str, middle: Optional[str] = None) -> list[str]:
    """Build a list of normalized name strings to try when matching against API responses."""
    variants = []
    first = (first or '').strip()
    last = (last or '').strip()
    middle = (middle or '').strip()

    if first and last:
        variants.append(normalize_name(f"{first} {last}"))
        variants.append(normalize_name(f"{last} {first}"))
        if middle:
            mi = middle[0]
            variants.append(normalize_name(f"{first} {mi} {last}"))
            variants.append(normalize_name(f"{first} {middle} {last}"))

    return list(dict.fromkeys(v for v in variants if v))


def fuzzy_match(candidate: str, target_variants: list[str], threshold: int = 85) -> tuple[Optional[str], int]:
    """
    Match a candidate string against target name variants using token_sort_ratio
    (order-insensitive). Returns (best_match, score) or (None, 0).
    """
    if not candidate or not target_variants:
        return None, 0

    candidate_norm = normalize_name(candidate)
    best_match = None
    best_score = 0

    for target in target_variants:
        score = fuzz.token_sort_ratio(candidate_norm, target)
        if score > best_score:
            best_score = score
            best_match = target

    if best_score >= threshold:
        return best_match, best_score
    return None, 0


def is_match(candidate: str, target_variants: list[str], threshold: int = 85) -> bool:
    """Convenience boolean wrapper around fuzzy_match."""
    _, score = fuzzy_match(candidate, target_variants, threshold)
    return score >= threshold


def names_share_state(contact_state: Optional[str], result_state: Optional[str]) -> bool:
    """
    Returns True if states match or either is unknown.
    Used as a secondary filter for common surnames in FEC data.
    """
    if not contact_state or not result_state:
        return True
    return contact_state.upper().strip() == result_state.upper().strip()
