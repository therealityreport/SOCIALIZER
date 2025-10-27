from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.entity_linking import CastCatalogEntry, EntityLinker


class FakeNLP:
    def __init__(self, ents: list[SimpleNamespace]) -> None:
        self._ents = ents

    def __call__(self, text: str) -> SimpleNamespace:
        return SimpleNamespace(ents=self._ents)


def _make_catalog() -> list[CastCatalogEntry]:
    return [
        CastCatalogEntry(cast_member_id=1, canonical_name="Lisa Barlow", aliases={"Lisa"}),
        CastCatalogEntry(cast_member_id=2, canonical_name="Meredith Marks", aliases={"Meredith"}),
    ]


def test_entity_linker_matches_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.entity_linking.get_spacy_model", lambda: FakeNLP([]))
    linker = EntityLinker(_make_catalog())

    matches = linker.find_mentions("Lisa absolutely owned tonight's episode.")

    assert len(matches) == 1
    match = matches[0]
    assert match.cast_member_id == 1
    assert match.method == "exact"
    assert match.quote.lower() == "lisa"
    assert match.confidence == pytest.approx(0.95)


def test_entity_linker_performs_fuzzy_linking(monkeypatch: pytest.MonkeyPatch) -> None:
    ents = [SimpleNamespace(text="Meredyth Marks", label_="PERSON")]
    monkeypatch.setattr("app.services.entity_linking.get_spacy_model", lambda: FakeNLP(ents))
    linker = EntityLinker(_make_catalog())

    matches = linker.find_mentions("I think Meredyth Marks brought the drama.")

    assert len(matches) == 1
    match = matches[0]
    assert match.cast_member_id == 2
    assert match.method == "fuzzy"
    assert match.quote == "Meredyth Marks"
    assert match.confidence >= 0.85
