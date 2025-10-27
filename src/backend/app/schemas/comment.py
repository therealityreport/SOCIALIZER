from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CommentMentionRead(BaseModel):
    """Metadata for a cast mention extracted from a comment."""

    cast_slug: str = Field(..., description="Slug identifier for the cast member.")
    cast_name: str = Field(..., description="Display name for the cast member.")
    sentiment_label: Optional[str] = Field(default=None, description="Sentiment label assigned to the mention.")
    sentiment_score: Optional[float] = Field(default=None, description="Sentiment score assigned to the mention.")
    quote: Optional[str] = Field(default=None, description="Excerpt of the text that triggered the mention.")


class CommentModelScore(BaseModel):
    """Per-model sentiment diagnostics."""

    name: str = Field(..., description="Model or service name that produced the sentiment.")
    sentiment_label: Optional[str] = Field(default=None, description="Label reported by the model.")
    sentiment_score: Optional[float] = Field(default=None, description="Score/probability reported by the model.")
    reasoning: Optional[str] = Field(default=None, description="Human-readable explanation of the model output.")


class CommentRead(BaseModel):
    """Public representation of a Reddit comment stored in the system."""

    id: int
    reddit_id: str
    body: str
    created_utc: datetime
    author_hash: Optional[str] = None
    score: int
    time_window: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_models: List[CommentModelScore] = Field(default_factory=list, description="Breakdown of sentiment outputs per model.")
    sentiment_combined_score: Optional[float] = Field(default=None, description="Aggregate score derived from all models (sum of confidences).")
    sentiment_final_source: Optional[str] = Field(default=None, description="Model that supplied the final sentiment selection.")
    is_sarcastic: bool
    sarcasm_confidence: Optional[float] = None
    is_toxic: bool
    toxicity_confidence: Optional[float] = None
    mentions: List[CommentMentionRead] = Field(default_factory=list)
    replies: List["CommentRead"] = Field(default_factory=list)


class CommentListResponse(BaseModel):
    """Paginated comment payload for a thread."""

    comments: List[CommentRead]
    total: int
    limit: int
    offset: int


CommentRead.model_rebuild()
