"""Google Gemini LLM Client"""
import json
import logging
import os
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseLLMClient, LLMAnalysisResult

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """Google Gemini API client for sentiment analysis"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """Initialize Gemini client"""
        api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        endpoint = endpoint or os.getenv(
            "GEMINI_ENDPOINT",
            "https://generativelanguage.googleapis.com/v1beta/models"
        )
        super().__init__(api_key, model, endpoint)

        # Pricing per 1M tokens (input/output) - as of Dec 2024
        self.pricing = {
            "gemini-1.5-pro": (1.25, 5.00),
            "gemini-1.5-flash": (0.075, 0.30),
            "gemini-1.0-pro": (0.50, 1.50),
        }

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    async def _call_api(self, prompt: str, system_prompt: str) -> dict[str, Any]:
        """Make API call with retry logic"""
        # Gemini endpoint format
        url = f"{self.endpoint}/{self.model}:generateContent?key={self.api_key}"

        # Combine system and user prompts for Gemini
        combined_prompt = f"{system_prompt}\n\n{prompt}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [
                            {
                                "parts": [
                                    {"text": combined_prompt}
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.3,
                            "topK": 40,
                            "topP": 0.95,
                            "maxOutputTokens": 1024,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Gemini rate limit hit, retrying...")
                    raise
                else:
                    logger.error(f"Gemini HTTP error: {e.response.status_code}")
                    logger.error(f"Response: {e.response.text}")
                    raise
            except httpx.RequestError as e:
                logger.error(f"Gemini request error: {e}")
                raise

    async def analyze(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> LLMAnalysisResult:
        """Analyze comment with Google Gemini"""
        if context is None:
            context = {}

        prompt = self._build_prompt(text, context)
        system_prompt = self._get_system_prompt()

        with self._track_execution() as tracker:
            try:
                response = await self._call_api(prompt, system_prompt)
                result = self._parse_response(response)
                result.execution_time = tracker.execution_time
                return result
            except Exception as e:
                logger.error(f"Gemini analysis failed: {e}")
                # Return neutral fallback
                return LLMAnalysisResult(
                    primary_sentiment="NEUTRAL",
                    secondary_attitude=None,
                    emotions=[],
                    sarcasm_score=0.0,
                    sarcasm_label="not_sarcastic",
                    sarcasm_evidence=None,
                    confidence=0.0,
                    provider="gemini",
                    model=self.model,
                    execution_time=tracker.execution_time,
                )

    def _parse_response(self, response: dict[str, Any]) -> LLMAnalysisResult:
        """Parse Gemini response into structured result"""
        try:
            # Gemini returns candidates with parts
            content = response["candidates"][0]["content"]["parts"][0]["text"]

            # Parse JSON
            data = json.loads(content)

            # Extract token usage if available
            usage_metadata = response.get("usageMetadata", {})
            input_tokens = usage_metadata.get("promptTokenCount", 0)
            output_tokens = usage_metadata.get("candidatesTokenCount", 0)
            total_tokens = usage_metadata.get("totalTokenCount", input_tokens + output_tokens)

            # Estimate cost
            cost = self._estimate_cost(input_tokens, output_tokens)

            return LLMAnalysisResult(
                primary_sentiment=data.get("primary_sentiment", "NEUTRAL"),
                secondary_attitude=data.get("secondary_attitude"),
                emotions=data.get("emotions", []),
                sarcasm_score=float(data.get("sarcasm_score", 0.0)),
                sarcasm_label=data.get("sarcasm_label", "not_sarcastic"),
                sarcasm_evidence=data.get("sarcasm_evidence"),
                confidence=float(data.get("confidence", 0.5)),
                provider="gemini",
                model=self.model,
                execution_time=0.0,  # Will be set by caller
                token_count=total_tokens,
                cost_estimate=cost,
            )
        except (KeyError, json.JSONDecodeError, ValueError, IndexError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Response: {response}")
            raise

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on token usage"""
        # Default pricing if model not in map
        input_price, output_price = self.pricing.get(self.model, (1.25, 5.00))

        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return input_cost + output_cost
