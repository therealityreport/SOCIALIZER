import pathlib
import sys

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
ML_PATH = ROOT / "src" / "ml"
if str(ML_PATH) not in sys.path:
    sys.path.insert(0, str(ML_PATH))

from ltsr_ml.inference.server import app

client = TestClient(app)


def test_health_endpoint_reports_status():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_version" in body


@pytest.mark.parametrize(
    "text, expected_label",
    [
        ("I love how this episode turned out", "positive"),
        ("This was the worst storyline ever", "negative"),
        ("Not sure what to think about the reveal", "neutral"),
    ],
)
def test_predict_endpoint_returns_placeholder_scores(text, expected_label):
    response = client.post("/predict", json={"texts": [text]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"]
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["sentiment"]["label"] == expected_label
    assert 0.0 <= result["sentiment"]["confidence"] <= 1.0
    assert 0.0 <= result["sarcasm"]["confidence"] <= 1.0
    assert 0.0 <= result["toxicity"]["confidence"] <= 1.0
