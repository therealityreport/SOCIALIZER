from __future__ import annotations

from fastapi import FastAPI

from ltsr_ml.config import get_settings
from ltsr_ml.inference.router import router as inference_router
from ltsr_ml.utils.logging import configure_logging

configure_logging()

settings = get_settings()
app = FastAPI(
    title="SOCIALIZER ML Inference",
    version=settings.model_version,
    summary="Prediction service for Reddit comment sentiment, sarcasm, and toxicity.",
)

app.include_router(inference_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "model_version": settings.model_version}
