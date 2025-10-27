from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest
import torch

from app.core.config import Settings
from app.services import sentiment_pipeline
from app.services.entity_linking import CastCatalogEntry, MentionCandidate
from app.services.sentiment_pipeline import (
    NormalizedSentiment,
    PrimaryPrediction,
    SentimentAnalysisResult,
    SentimentPipeline,
    analyze_text,
)


@pytest.fixture()
def mocked_transformers(monkeypatch: pytest.MonkeyPatch) -> Callable[[], dict[str, str]]:
    calls: dict[str, str] = {}

    class DummyTokenizer:
        def __call__(self, texts, **_kwargs):
            batch = len(texts)
            input_ids = torch.ones((batch, 3), dtype=torch.long)
            attention_mask = torch.ones((batch, 3), dtype=torch.long)
            return {"input_ids": input_ids, "attention_mask": attention_mask}

    class DummyModel:
        config = SimpleNamespace(id2label={"0": "negative", "1": "neutral", "2": "positive"})

        def eval(self):
            return self

        def to(self, _device):
            return self

        def __call__(self, **_kwargs):
            batch = _kwargs["input_ids"].shape[0]
            logits = torch.tensor([[0.2, 0.3, 0.5]], dtype=torch.float32).repeat(batch, 1)
            return SimpleNamespace(logits=logits)

    def capture_tokenizer(model_name: str, **_kwargs):
        calls["tokenizer"] = model_name
        return DummyTokenizer()

    def capture_model(model_name: str, **_kwargs):
        calls["model"] = model_name
        return DummyModel()

    monkeypatch.setattr(sentiment_pipeline.AutoTokenizer, "from_pretrained", capture_tokenizer)
    monkeypatch.setattr(sentiment_pipeline.AutoModelForSequenceClassification, "from_pretrained", capture_model)
    monkeypatch.setattr(
        sentiment_pipeline,
        "HfApi",
        lambda: SimpleNamespace(model_info=lambda _model_id: SimpleNamespace(sha="test-rev")),
    )
    monkeypatch.setattr(sentiment_pipeline, "_PIPELINE", None)

    return lambda: calls


def test_sentiment_pipeline_loads_primary_model(mocked_transformers: Callable[[], dict[str, str]]) -> None:
    calls = mocked_transformers()
    settings = Settings(primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest")

    SentimentPipeline(settings)

    assert calls["tokenizer"] == settings.primary_model
    assert calls["model"] == settings.primary_model


def test_sentiment_pipeline_falls_back_to_azure(mocked_transformers: Callable[[], dict[str, str]]) -> None:
    mocked_transformers()
    settings = Settings(
        primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        fallback_service="Azure Text Analytics Opinion Mining",
        confidence_threshold=0.75,
    )

    pipeline = SentimentPipeline(settings)

    def low_confidence_predictions(texts):
        return [
            PrimaryPrediction(
                label="neutral",
                score=0.4,
                margin=0.05,
                probabilities={"negative": 0.3, "neutral": 0.4, "positive": 0.3},
            )
            for _ in texts
        ]

    pipeline._score_primary = low_confidence_predictions  # type: ignore[method-assign]

    class FakeScores:
        positive = 0.1
        neutral = 0.82
        negative = 0.08

    class FakeDocument:
        is_error = False
        sentiment = "neutral"
        confidence_scores = FakeScores()
        sentences = []

    class FakeAzureClient:
        def analyze_sentiment(self, documents, show_opinion_mining: bool = False):
            assert show_opinion_mining is True
            assert len(documents) == 1
            return [FakeDocument()]

    pipeline._azure_client = FakeAzureClient()

    result = pipeline.analyze_comment("Low confidence signal triggers fallback.")
    assert isinstance(result, SentimentAnalysisResult)
    assert result.final.source_model == settings.fallback_service
    assert result.final.sentiment_label == "neutral"
    assert pytest.approx(result.final.sentiment_score, rel=1e-5) == 0.82
    assert len(result.models) == 2
    assert result.models[0].name == settings.primary_model
    assert result.models[-1].name == settings.fallback_service
    expected_sum = 0.4 + 0.82  # primary mock score + fallback score
    assert pytest.approx(result.combined_score, rel=1e-5) == expected_sum


def test_sentiment_pipeline_attributes_cast_mentions(mocked_transformers: Callable[[], dict[str, str]]) -> None:
    mocked_transformers()
    settings = Settings(
        primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        fallback_service="Azure Text Analytics Opinion Mining",
        confidence_threshold=0.75,
    )

    pipeline = SentimentPipeline(settings)

    def positive_predictions(texts):
        return [
            PrimaryPrediction(
                label="positive",
                score=0.92,
                margin=0.25,
                probabilities={"negative": 0.02, "neutral": 0.06, "positive": 0.92},
            )
            for _ in texts
        ]

    pipeline._score_primary = positive_predictions  # type: ignore[method-assign]
    pipeline._parse_comment_for_heuristics = lambda _text: None  # type: ignore[method-assign]

    catalog_entry = CastCatalogEntry(cast_member_id=1, canonical_name="Jane Doe", aliases={"jane"})
    catalog_lookup = {catalog_entry.cast_member_id: catalog_entry}
    candidate = MentionCandidate(cast_member_id=1, confidence=0.95, method="exact", quote="Jane")

    results = pipeline.analyze_mentions(
        comment_text="Jane Doe was fantastic in this scene!",
        candidates=[candidate],
        contexts=["Jane Doe was fantastic in this scene!"],
        catalog=catalog_lookup,
    )

    assert len(results) == 1
    result = results[0]
    assert result.cast_member_id == 1
    assert result.cast_member == "Jane Doe"
    assert result.sentiment_label == "positive"
    assert pytest.approx(result.sentiment_score, rel=1e-5) == 0.92
    assert result.source_model == settings.primary_model
    assert result.reasoning is not None


def test_sentiment_pipeline_opinion_mining_for_multi_target(mocked_transformers: Callable[[], dict[str, str]]) -> None:
    mocked_transformers()
    settings = Settings(
        primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        fallback_service="Azure Text Analytics Opinion Mining",
        confidence_threshold=0.2,
    )

    pipeline = SentimentPipeline(settings)

    def multi_predictions(texts):
        return [
            PrimaryPrediction(
                label="positive",
                score=0.6,
                margin=0.05,
                probabilities={"negative": 0.2, "neutral": 0.2, "positive": 0.6},
            )
            for _ in texts
        ]

    pipeline._score_primary = multi_predictions  # type: ignore[method-assign]
    pipeline._parse_comment_for_heuristics = lambda _text: None  # type: ignore[method-assign]

    class FakeConfidence:
        def __init__(self, positive: float, neutral: float, negative: float) -> None:
            self.positive = positive
            self.neutral = neutral
            self.negative = negative

    class FakeTarget:
        def __init__(self, text: str, sentiment: str, scores: FakeConfidence) -> None:
            self.text = text
            self.sentiment = sentiment
            self.confidence_scores = scores

    class FakeOpinion:
        def __init__(self, target: FakeTarget) -> None:
            self.target = target

    class FakeSentence:
        def __init__(self, opinions) -> None:
            self.opinions = opinions

    jane_scores = FakeConfidence(positive=0.05, neutral=0.10, negative=0.85)
    john_scores = FakeConfidence(positive=0.88, neutral=0.08, negative=0.04)
    fake_document = SimpleNamespace(
        is_error=False,
        sentences=[
            FakeSentence(
                [
                    FakeOpinion(FakeTarget("Jane", "negative", jane_scores)),
                    FakeOpinion(FakeTarget("John", "positive", john_scores)),
                ]
            )
        ],
    )

    class FakeAzureClient:
        def analyze_sentiment(self, documents, show_opinion_mining: bool = False):
            assert show_opinion_mining is True
            assert len(documents) == 1
            return [fake_document]

    pipeline._azure_client = FakeAzureClient()

    catalog_jane = CastCatalogEntry(cast_member_id=1, canonical_name="Jane Doe", aliases={"jane"})
    catalog_john = CastCatalogEntry(cast_member_id=2, canonical_name="John Smith", aliases={"john"})
    catalog_lookup = {
        catalog_jane.cast_member_id: catalog_jane,
        catalog_john.cast_member_id: catalog_john,
    }
    candidates = [
        MentionCandidate(cast_member_id=1, confidence=0.93, method="exact", quote="Jane"),
        MentionCandidate(cast_member_id=2, confidence=0.91, method="exact", quote="John"),
    ]
    comment_text = "Jane was dragged while John saved the day."
    contexts = [comment_text, comment_text]

    results = pipeline.analyze_mentions(
        comment_text=comment_text,
        candidates=candidates,
        contexts=contexts,
        catalog=catalog_lookup,
    )

    assert len(results) == 2
    jane_result, john_result = results
    assert jane_result.cast_member_id == 1
    assert jane_result.source_model == settings.fallback_service
    assert jane_result.sentiment_label == "negative"
    assert pytest.approx(jane_result.sentiment_score, rel=1e-5) == 0.85

    assert john_result.cast_member_id == 2
    assert john_result.source_model == settings.fallback_service
    assert john_result.sentiment_label == "positive"
    assert pytest.approx(john_result.sentiment_score, rel=1e-5) == 0.88


def test_sentiment_pipeline_heuristics_when_opinion_missing(mocked_transformers: Callable[[], dict[str, str]]) -> None:
    mocked_transformers()
    settings = Settings(
        primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        fallback_service="Azure Text Analytics Opinion Mining",
        confidence_threshold=0.9,
    )

    pipeline = SentimentPipeline(settings)

    def fake_score(texts):
        results = []
        for text in texts:
            lowered = text.lower()
            if "love" in lowered and "terrible" in lowered:
                results.append(
                    PrimaryPrediction(
                        label="neutral",
                        score=0.4,
                        margin=0.05,
                        probabilities={"negative": 0.3, "neutral": 0.4, "positive": 0.3},
                    )
                )
            elif "terrible" in lowered or "worst" in lowered:
                results.append(
                    PrimaryPrediction(
                        label="negative",
                        score=0.9,
                        margin=0.4,
                        probabilities={"negative": 0.9, "neutral": 0.08, "positive": 0.02},
                    )
                )
            elif "love" in lowered or "fantastic" in lowered:
                results.append(
                    PrimaryPrediction(
                        label="positive",
                        score=0.9,
                        margin=0.4,
                        probabilities={"negative": 0.02, "neutral": 0.08, "positive": 0.9},
                    )
                )
            else:
                results.append(
                    PrimaryPrediction(
                        label="neutral",
                        score=0.5,
                        margin=0.2,
                        probabilities={"negative": 0.25, "neutral": 0.5, "positive": 0.25},
                    )
                )
        return results

    pipeline._score_primary = fake_score  # type: ignore[method-assign]
    pipeline._azure_client = None

    class FakeSentence:
        def __init__(self, text: str) -> None:
            self.text = text

        def __iter__(self):
            return iter(())

    class FakeDoc:
        def __init__(self, sentence_text: str) -> None:
            self._sentences = [FakeSentence(sentence_text)]

        @property
        def sents(self):
            return self._sentences

    pipeline._parse_comment_for_heuristics = lambda text: FakeDoc(text)  # type: ignore[method-assign]

    catalog_jane = CastCatalogEntry(cast_member_id=1, canonical_name="Jane Doe", aliases={"jane"})
    catalog_john = CastCatalogEntry(cast_member_id=2, canonical_name="John Smith", aliases={"john"})
    catalog_lookup = {
        catalog_jane.cast_member_id: catalog_jane,
        catalog_john.cast_member_id: catalog_john,
    }
    candidates = [
        MentionCandidate(cast_member_id=1, confidence=0.9, method="exact", quote="Jane"),
        MentionCandidate(cast_member_id=2, confidence=0.88, method="exact", quote="John"),
    ]
    comment_text = "I love Jane but John is terrible."
    contexts = [comment_text, comment_text]

    results = pipeline.analyze_mentions(
        comment_text=comment_text,
        candidates=candidates,
        contexts=contexts,
        catalog=catalog_lookup,
    )

    assert len(results) == 2
    jane_result, john_result = results
    assert jane_result.cast_member_id == 1
    assert jane_result.source_model.endswith("+heuristic")
    assert jane_result.sentiment_label == "positive"
    assert pytest.approx(jane_result.sentiment_score, rel=1e-5) == 0.9

    assert john_result.cast_member_id == 2
    assert john_result.source_model.endswith("+heuristic")
    assert john_result.sentiment_label == "negative"
    assert pytest.approx(john_result.sentiment_score, rel=1e-5) == 0.9


def test_per_target_split(mocked_transformers: Callable[[], dict[str, str]]) -> None:
    mocked_transformers()
    settings = Settings(
        primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        fallback_service="Azure Text Analytics Opinion Mining",
        confidence_threshold=0.2,
    )

    pipeline = SentimentPipeline(settings)

    def targeted_predictions(texts):
        base = [
            PrimaryPrediction(
                label="positive",
                score=0.91,
                margin=0.35,
                probabilities={"negative": 0.02, "neutral": 0.07, "positive": 0.91},
            ),
            PrimaryPrediction(
                label="negative",
                score=0.9,
                margin=0.34,
                probabilities={"negative": 0.9, "neutral": 0.07, "positive": 0.03},
            ),
        ]
        return base[: len(texts)]

    pipeline._score_primary = targeted_predictions  # type: ignore[method-assign]
    pipeline._fetch_azure_document = lambda _docs: None  # type: ignore[method-assign]
    sentiment_pipeline._PIPELINE = pipeline

    try:
        output = analyze_text("Lisa was great, Whitney was annoying.", targets=["Lisa", "Whitney"])
    finally:
        sentiment_pipeline._PIPELINE = None

    assert output["text"] == "Lisa was great, Whitney was annoying."
    assert output["model"]["id"] == settings.primary_model
    assert output["model"]["rev"] == "test-rev"
    assert output["model"]["source"] == "hf"
    assert output["fallback_used"] is False

    lisa = output["targets"]["Lisa"]
    whitney = output["targets"]["Whitney"]

    assert lisa["label"] == "positive"
    assert lisa["source"] == "primary"
    assert lisa["margin"] == pytest.approx(0.35, rel=1e-5)
    assert lisa["score"] == pytest.approx(0.91, rel=1e-5)
    assert lisa["probs"] == {"neg": 0.02, "neu": 0.07, "pos": 0.91}

    assert whitney["label"] == "negative"
    assert whitney["source"] == "primary"
    assert whitney["margin"] == pytest.approx(0.34, rel=1e-5)
    assert whitney["score"] == pytest.approx(0.9, rel=1e-5)
    assert whitney["probs"] == {"neg": 0.9, "neu": 0.07, "pos": 0.03}


def test_analyze_text_contract_with_auto_targets(mocked_transformers: Callable[[], dict[str, str]], monkeypatch) -> None:
    mocked_transformers()
    settings = Settings(
        primary_model="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        fallback_enabled=False,
    )
    pipeline = SentimentPipeline(settings)
    monkeypatch.setattr(sentiment_pipeline, "_PIPELINE", pipeline)
    try:
        output = analyze_text("Lisa was great, Whitney was annoying.")
    finally:
        sentiment_pipeline._PIPELINE = None

    assert output["text"] == "Lisa was great, Whitney was annoying."
    assert output["model"] == {"id": settings.primary_model, "rev": "test-rev", "source": "hf"}
    assert sorted(output["targets"].keys()) == ["Lisa Barlow", "Whitney Rose"]
    lisa = output["targets"]["Lisa Barlow"]
    whitney = output["targets"]["Whitney Rose"]
    for target in (lisa, whitney):
        assert set(target.keys()) == {"label", "score", "probs", "margin", "source"}
        assert isinstance(target["score"], float)
        assert isinstance(target["margin"], float)
        assert set(target["probs"].keys()) == {"neg", "neu", "pos"}
        assert target["source"] == "primary"
    assert output["fallback_used"] is False


def test_sentiment_alias_configuration() -> None:
    alias_path = Path("config/sentiment/aliases.json")
    assert alias_path.exists()
    data = json.loads(alias_path.read_text(encoding="utf-8"))
    targets = data.get("targets", [])
    assert isinstance(targets, list) and targets

    for entry in targets:
        assert entry.get("slug"), "slug is required for each alias entry"
        assert entry.get("name"), "name is required for each alias entry"
        aliases = entry.get("aliases") or []
        assert aliases, f"aliases missing for {entry['slug']}"
        assert entry["name"] in aliases, f"canonical name missing from aliases for {entry['slug']}"

    lookup = {entry["slug"]: entry for entry in targets}
    lisa_aliases = {alias.lower() for alias in lookup["lisa-barlow"]["aliases"]}
    whitney_aliases = {alias.lower() for alias in lookup["whitney-rose"]["aliases"]}

    assert {"lisa", "@lisabarlow", "lisah"}.issubset(lisa_aliases)
    assert {"whitney", "@whitney", "whittney"}.issubset(whitney_aliases)
