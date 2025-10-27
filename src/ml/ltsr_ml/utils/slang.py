from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

from importlib.abc import Traversable


@dataclass(frozen=True)
class LexiconEntry:
  term: str
  weight: float
  tags: tuple[str, ...]


@dataclass(frozen=True)
class LexiconMatch:
  term: str
  weight: float
  tags: tuple[str, ...]
  count: int


@dataclass(frozen=True)
class SlangAnalysisResult:
  score: float
  matches: list[LexiconMatch]


def _compile_pattern(term: str) -> re.Pattern[str]:
  if " " in term or "-" in term:
    return re.compile(re.escape(term), flags=re.IGNORECASE)
  return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=re.IGNORECASE)


class SlangLexicon:
  def __init__(self, entries: Iterable[LexiconEntry]) -> None:
    self.entries: list[LexiconEntry] = list(entries)
    self._patterns: list[re.Pattern[str]] = [_compile_pattern(entry.term) for entry in self.entries]

  @classmethod
  def from_file(cls, path: Path) -> SlangLexicon:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cls(_entries_from_payload(data))

  @classmethod
  def from_resource(cls, resource: Traversable) -> SlangLexicon:
    with resource.open("r", encoding="utf-8") as fp:
      data = json.load(fp)
    return cls(_entries_from_payload(data))

  def analyze(self, text: str | None) -> SlangAnalysisResult:
    if not text:
      return SlangAnalysisResult(score=0.0, matches=[])

    lowered = text.lower()
    matches: list[LexiconMatch] = []
    total = 0.0

    for entry, pattern in zip(self.entries, self._patterns):
      hits = pattern.findall(lowered)
      if not hits:
        continue
      count = len(hits)
      matches.append(LexiconMatch(term=entry.term, weight=entry.weight, tags=entry.tags, count=count))
      total += entry.weight * count

    return SlangAnalysisResult(score=total, matches=matches)


def _entries_from_payload(payload: Iterable[dict[str, object]]) -> Iterable[LexiconEntry]:
  for item in payload:
    term = str(item["term"]).strip()
    weight = float(item["weight"])
    tags_field = item.get("tags", [])
    if isinstance(tags_field, str):
      tags = (tags_field,)
    else:
      tags = tuple(str(tag) for tag in tags_field)  # type: ignore[arg-type]
    yield LexiconEntry(term=term, weight=weight, tags=tags)


def load_default_lexicon() -> SlangLexicon:
  resource = resources.files("ltsr_ml.assets").joinpath("slang_lexicon.json")
  return SlangLexicon.from_resource(resource)
