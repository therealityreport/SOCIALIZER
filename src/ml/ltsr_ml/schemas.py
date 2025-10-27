from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, Field


class InferencePayload(BaseModel):
    """Request body for batch inference."""

    texts: Sequence[str] = Field(..., min_length=1, description="Reddit comment bodies to classify.")


class SentimentResult(BaseModel):
    label: str = Field(..., description="Predicted sentiment label.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the sentiment prediction.")


class BinaryResult(BaseModel):
    is_positive: bool = Field(..., description="Indicates whether the condition is met.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the prediction.")


class SlangMatch(BaseModel):
    term: str = Field(..., description="Matched slang term.")
    weight: float = Field(..., description="Sentiment weight applied for this term.")
    count: int = Field(default=1, ge=1, description="Number of times the term was detected in the comment.")
    tags: list[str] = Field(default_factory=list, description="Additional semantic tags associated with the slang term.")


class SlangInsights(BaseModel):
    score: float = Field(..., description="Aggregate sentiment modifier contributed by slang matches.")
    matches: list[SlangMatch] = Field(default_factory=list, description="Detailed slang matches detected in the comment.")


class CommentInference(BaseModel):
    sentiment: SentimentResult
    sarcasm: BinaryResult
    toxicity: BinaryResult
    slang: SlangInsights | None = Field(default=None, description="Detected slang metadata applied during scoring.")


class InferenceResponse(BaseModel):
    model_version: str
    results: list[CommentInference]
