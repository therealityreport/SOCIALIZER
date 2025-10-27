from __future__ import annotations

from app.services.cast_roster import get_cast_alias_lookup, resolve_aliases


def test_cast_alias_lookup_includes_britani_variations() -> None:
    get_cast_alias_lookup.cache_clear()
    lookup = get_cast_alias_lookup()

    key = "britani bateman"
    assert key in lookup
    aliases = {alias.lower() for alias in lookup[key]}
    assert "brittnay" in aliases
    assert "britney" in aliases


def test_resolve_aliases_supports_slug_lookup() -> None:
    aliases = {alias.lower() for alias in resolve_aliases("Britani Bateman", "britani-bateman")}
    assert "britain" in aliases
