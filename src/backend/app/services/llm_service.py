"""LLM Service for Sentiment Analysis

Handles LLM-driven analysis for:
- Primary sentiment (POSITIVE/NEUTRAL/NEGATIVE)
- Secondary attitude (Admiration/Support, Shady/Humor, etc.)
- Emotion extraction
- Sarcasm detection with evidence

Includes retry logic, caching, and rate limiting.
"""
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMAnalysisResult:
    """Container for LLM analysis results"""

    primary_sentiment: str  # POSITIVE, NEUTRAL, NEGATIVE
    secondary_attitude: Optional[str]  # Admiration/Support, Shady/Humor, etc.
    emotions: list[dict[str, Any]]  # [{"label": "joy", "score": 0.87}, ...]
    sarcasm_score: float  # 0.0-1.0
    sarcasm_label: str  # "sarcastic" or "not_sarcastic"
    sarcasm_evidence: Optional[str]  # Text snippet supporting detection
    confidence: float  # Overall confidence 0.0-1.0
    method: str  # "llm"

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
            "method": self.method,
        }


class LLMService:
    """Service for LLM-based sentiment analysis with caching and retry"""

    def __init__(self):
        """Initialize LLM service"""
        self.model = os.getenv("LLM_MODEL", "gpt-4")
        self.endpoint = os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
        self.sarcasm_threshold = float(os.getenv("SARCASM_THRESHOLD", "0.5"))

        # Simple in-memory cache (content_hash -> result)
        # In production, use Redis
        self._cache: dict[str, LLMAnalysisResult] = {}

        # Rate limiting state
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 10 req/sec max

    def _get_cache_key(self, text: str, context: dict[str, Any]) -> str:
        """Generate cache key from text and context"""
        content = f"{text}|{json.dumps(context, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[LLMAnalysisResult]:
        """Check if result is cached"""
        return self._cache.get(cache_key)

    def _store_cache(self, cache_key: str, result: LLMAnalysisResult) -> None:
        """Store result in cache"""
        self._cache[cache_key] = result

    def _rate_limit(self) -> None:
        """Apply rate limiting"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    async def _call_llm(
        self,
        text: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Make LLM API call with retry logic

        Args:
            text: Comment text to analyze
            context: Episode context (synopsis, cast roster, etc.)

        Returns:
            LLM response dict

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            httpx.RequestError: On connection errors
        """
        # Rate limit requests
        self._rate_limit()

        # Build prompt
        prompt = self._build_prompt(text, context)

        # Make API call
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self._get_system_prompt()},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Rate limit hit, retrying...")
                    raise  # Let tenacity retry
                else:
                    logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                    raise
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise

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

Be precise and nuanced in your analysis. Reality TV fans often express complex emotions mixing humor, criticism, and support."""

    def _parse_llm_response(self, response: dict[str, Any]) -> LLMAnalysisResult:
        """Parse LLM response into structured result"""
        try:
            content = response["choices"][0]["message"]["content"]
            data = json.loads(content)

            return LLMAnalysisResult(
                primary_sentiment=data.get("primary_sentiment", "NEUTRAL"),
                secondary_attitude=data.get("secondary_attitude"),
                emotions=data.get("emotions", []),
                sarcasm_score=float(data.get("sarcasm_score", 0.0)),
                sarcasm_label=data.get("sarcasm_label", "not_sarcastic"),
                sarcasm_evidence=data.get("sarcasm_evidence"),
                confidence=float(data.get("confidence", 0.5)),
                method="llm",
            )
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response: {response}")
            # Return neutral fallback
            return LLMAnalysisResult(
                primary_sentiment="NEUTRAL",
                secondary_attitude=None,
                emotions=[],
                sarcasm_score=0.0,
                sarcasm_label="not_sarcastic",
                sarcasm_evidence=None,
                confidence=0.0,
                method="llm_error",
            )

    async def analyze(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> LLMAnalysisResult:
        """
        Analyze comment with LLM

        Args:
            text: Comment text
            context: Episode and cast context

        Returns:
            LLMAnalysisResult with all analysis fields
        """
        if context is None:
            context = {}

        # Check cache
        cache_key = self._get_cache_key(text, context)
        cached = self._check_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for text: {text[:50]}...")
            return cached

        # Call LLM
        try:
            response = await self._call_llm(text, context)
            result = self._parse_llm_response(response)

            # Store in cache
            self._store_cache(cache_key, result)

            logger.info(f"LLM analysis complete: sentiment={result.primary_sentiment}, confidence={result.confidence}")
            return result

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # Return neutral fallback
            return LLMAnalysisResult(
                primary_sentiment="NEUTRAL",
                secondary_attitude=None,
                emotions=[],
                sarcasm_score=0.0,
                sarcasm_label="not_sarcastic",
                sarcasm_evidence=None,
                confidence=0.0,
                method="llm_error",
            )

    async def analyze_batch(
        self,
        texts: list[str],
        context: Optional[dict[str, Any]] = None,
    ) -> list[LLMAnalysisResult]:
        """
        Analyze multiple comments

        Args:
            texts: List of comment texts
            context: Shared episode context

        Returns:
            List of LLMAnalysisResult
        """
        results = []
        for text in texts:
            result = await self.analyze(text, context)
            results.append(result)
        return results


# Global singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service singleton"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
