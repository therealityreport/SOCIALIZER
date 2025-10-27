from __future__ import annotations

from fastapi import APIRouter, Depends

from ltsr_ml.inference.service import InferenceService
from ltsr_ml.schemas import InferencePayload, InferenceResponse

router = APIRouter(prefix="/predict", tags=["inference"])


def get_service() -> InferenceService:
    return InferenceService()


@router.post("", response_model=InferenceResponse)
async def predict(payload: InferencePayload, service: InferenceService = Depends(get_service)) -> InferenceResponse:
    return service.predict(payload.texts)
