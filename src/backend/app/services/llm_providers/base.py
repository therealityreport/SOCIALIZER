"""Base LLM Client Interface"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMAnalysisResult:
    """Unified result structure for all LLM providers"""

    primary_sentiment: str  # POSITIVE, NEUTRAL, NEGATIVE
    secondary_attitude: Optional[str]  # Admiration/Support, Shady/Humor, etc.
    emotions: list[dict[str, Any]]  # [{"label": "joy", "score": 0.87}, ...]
    sarcasm_score: float  # 0.0-1.0
    sarcasm_label: str  # "sarcastic" or "not_sarcastic"
    sarcasm_evidence: Optional[str]  # Text snippet supporting detection
    confidence: float  # Overall confidence 0.0-1.0
    provider: str  # "openai", "anthropic", "gemini"
    model: str  # Specific model used
    execution_time: float  # Seconds
    token_count: Optional[int] = None  # Tokens used (if available)
    cost_estimate: Optional[float] = None  # Estimated cost in USD

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "primary_sentiment": self.primary_sentiment,
            "secondary_attitude": self.secondary_attitude,
            "emotions": self.emotions,
            "sarcasm_score": self.sarcasm_score,
            "sarcasm_label": self.sarcasm_label,
            "sarcasm_evidence": self.sarcasm_evidence,
            "confidence": self.confidence,
            "provider": self.provider,
            "model": self.model,
            "execution_time": self.execution_time,
            "token_count": self.token_count,
            "cost_estimate": self.cost_estimate,
        }


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, api_key: str, model: str, endpoint: Optional[str] = None):
        """
        Initialize LLM client

        Args:
            api_key: API key for the provider
            model: Model name to use
            endpoint: Optional custom endpoint URL
        """
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.provider_name = self.__class__.__name__.replace("Client", "").lower()

    @abstractmethod
    async def analyze(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> LLMAnalysisResult:
        """
        Analyze comment text with LLM

        Args:
            text: Comment text to analyze
            context: Episode context (synopsis, cast roster, etc.)

        Returns:
            LLMAnalysisResult with all analysis fields
        """
        pass

    def _build_prompt(self, text: str, context: dict[str, Any]) -> str:
        """Build analysis prompt with context"""
        cast_names = ", ".join(context.get("cast_roster", []))
        episode_synopsis = context.get("synopsis", "")[:500]  # Truncate to 500 chars

        return f"""Analyze the following comment from a reality TV episode discussion.

**Episode Context:**
{episode_synopsis}

**Cast Members:**
{cast_names}

**Comment:**
{text}

Provide a JSON response with the following structure:
{{
  "primary_sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
  "secondary_attitude": "Admiration/Support" | "Shady/Humor" | "Analytical" | "Annoyed" | "Hatred/Disgust" | "Sadness/Sympathy/Distress" | null,
  "emotions": [{{"label": "joy", "score": 0.87}}, ...],
  "sarcasm_score": 0.0-1.0,
  "sarcasm_label": "sarcastic" | "not_sarcastic",
  "sarcasm_evidence": "text snippet showing sarcasm" | null,
  "confidence": 0.0-1.0
}}"""

    def _get_system_prompt(self) -> str:
        """Get system prompt for LLM"""
        return """You are an expert at analyzing sentiment and tone in reality TV discussions. You understand sarcasm, shade, humor, and the complex social dynamics of reality TV fandom.

Your task is to analyze comments and provide detailed sentiment analysis including:
1. Primary sentiment (overall positive/neutral/negative)
2. Secondary attitude (the specific emotional tone)
3. Specific emotions detected
4. Sarcasm detection with evidence

Be precise and nuanced in your analysis. Reality TV fans often express complex emotions mixing humor, criticism, and support.

IMPORTANT: You MUST respond with valid JSON only. Do not include any explanatory text before or after the JSON."""

    def _track_execution(self):
        """Context manager to track execution time"""
        class ExecutionTracker:
            def __init__(self):
                self.start_time = None
                self.execution_time = 0.0

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.execution_time = time.time() - self.start_time

        return ExecutionTracker()
