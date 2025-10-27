from __future__ import annotations

import re

# Canonical long form show titles keyed by normalized variants
_CANONICAL_SHOWS: dict[str, str] = {
    "therealhousewivesofsaltlakecity": "The Real Housewives of Salt Lake City",
    "rhoslc": "The Real Housewives of Salt Lake City",
}


def _normalize_key(value: str) -> str:
    collapsed = re.sub(r"\\s+", " ", value.strip().lower())
    return re.sub(r"[^a-z0-9]+", "", collapsed)


def normalize_show_name(value: str | None) -> str:
    if not value:
        return ""

    key = _normalize_key(value)
    if key in _CANONICAL_SHOWS:
        return _CANONICAL_SHOWS[key]

    # Attempt to remove redundant whitespace for otherwise-canonical names
    collapsed = re.sub(r"\\s+", " ", value.strip())
    return collapsed


def shows_match(lhs: str | None, rhs: str | None) -> bool:
    return _normalize_key(lhs or "") == _normalize_key(rhs or "")


def register_show_alias(alias: str, canonical: str) -> None:
    key = _normalize_key(alias)
    _CANONICAL_SHOWS[key] = canonical
    # Ensure the canonical form also normalizes to itself
    canonical_key = _normalize_key(canonical)
    _CANONICAL_SHOWS[canonical_key] = canonical
