from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Set

from app.services.show_names import normalize_show_name


@dataclass(frozen=True)
class CastRosterEntry:
    """Canonical cast metadata sourced from data/cast_rosters."""

    canonical_name: str
    show: str
    season: str
    slug: str | None
    aliases: Set[str]


EXTRA_ALIAS_VARIANTS: Dict[str, Set[str]] = {
    "britani bateman": {"Brittnay", "Britney", "Britain"},
}


def _project_root() -> Path:
    resolved = Path(__file__).resolve()
    parents = resolved.parents
    for depth in (4, 3, 2):
        try:
            candidate = parents[depth]
        except IndexError:
            continue
        if (candidate / "data").exists():
            return candidate
    logger = logging.getLogger(__name__)
    logger.warning("Falling back to current directory when resolving project root for cast roster.")
    return resolved.parent


def _roster_root() -> Path:
    return _project_root() / "data" / "cast_rosters"


def _slugify(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def _normalize_key(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    return collapsed.casefold()


def _read_aliases(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    aliases: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        alias = line.strip()
        if alias:
            aliases.add(alias)
    return aliases


def _load_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid metadata JSON at {path}: {exc}") from exc


def _iter_cast_roster_entries(root: Path) -> Iterable[CastRosterEntry]:
    if not root.exists():
        return []

    entries: list[CastRosterEntry] = []
    for show_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        show_slug = show_dir.name
        for season_dir in sorted(p for p in show_dir.iterdir() if p.is_dir()):
            season = season_dir.name
            for cast_dir in sorted(p for p in season_dir.iterdir() if p.is_dir()):
                canonical = cast_dir.name.strip()
                if not canonical:
                    continue

                metadata = _load_metadata(cast_dir / "metadata.json")
                aliases = _read_aliases(cast_dir / "aliases.txt")
                aliases.add(canonical)

                entry = CastRosterEntry(
                    canonical_name=canonical,
                    show=normalize_show_name(str(metadata.get("show") or show_slug.replace("-", " ").title())),
                    season=str(metadata.get("season") or season),
                    slug=str(metadata.get("slug") or _slugify(canonical)),
                    aliases=aliases,
                )
                entries.append(entry)
    return entries


@lru_cache(maxsize=1)
def get_cast_roster_entries() -> tuple[CastRosterEntry, ...]:
    return tuple(_iter_cast_roster_entries(_roster_root()))


@lru_cache(maxsize=1)
def get_cast_alias_lookup() -> Dict[str, Set[str]]:
    lookup: Dict[str, Set[str]] = {}
    for entry in get_cast_roster_entries():
        aliases = set(entry.aliases)
        if entry.slug:
            aliases.add(entry.slug)
            aliases.add(entry.slug.replace("-", " "))

        normalized_name = _normalize_key(entry.canonical_name)
        extra_aliases = EXTRA_ALIAS_VARIANTS.get(normalized_name)
        if extra_aliases:
            aliases.update(extra_aliases)

        keys = {normalized_name}
        if entry.slug:
            keys.add(_normalize_key(entry.slug))

        for key in keys:
            current = lookup.setdefault(key, set())
            current.update(aliases)
    return lookup


def resolve_aliases(canonical_name: str, slug: str | None = None) -> Set[str]:
    """Return aliases defined in the cast roster for the provided canonical name or slug."""

    aliases: Set[str] = set()
    key = _normalize_key(canonical_name)
    roster = get_cast_alias_lookup()
    if key in roster:
        aliases.update(roster[key])
    if slug:
        slug_key = _normalize_key(slug)
        if slug_key in roster:
            aliases.update(roster[slug_key])
    return aliases
