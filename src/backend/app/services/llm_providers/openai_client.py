"""OpenAI LLM Client"""
import json
import logging
import os
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseLLMClient, LLMAnalysisResult

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client for sentiment analysis"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """Initialize OpenAI client"""
        api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        endpoint = endpoint or os.getenv(
            "OPENAI_ENDPOINT",
            "https://api.openai.com/v1/chat/completions"
        )
        super().__init__(api_key, model, endpoint)

        # Pricing per 1M tokens (input/output)
        self.pricing = {
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-4": (30.00, 60.00),
        }

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    async def _call_api(self, prompt: str, system_prompt: str) -> dict[str, Any]:
        """Make API call with retry logic"""
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
                            {"role": "system", "content": system_prompt},
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
                    logger.warning("OpenAI rate limit hit, retrying...")
                    raise
                else:
                    logger.error(f"OpenAI HTTP error: {e.response.status_code}")
                    raise
            except httpx.RequestError as e:
                logger.error(f"OpenAI request error: {e}")
                raise

    async def analyze(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> LLMAnalysisResult:
        """Analyze comment with OpenAI"""
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
                logger.error(f"OpenAI analysis failed: {e}")
                # Return neutral fallback
                return LLMAnalysisResult(
                    primary_sentiment="NEUTRAL",
                    secondary_attitude=None,
                    emotions=[],
                    sarcasm_score=0.0,
                    sarcasm_label="not_sarcastic",
                    sarcasm_evidence=None,
                    confidence=0.0,
                    provider="openai",
                    model=self.model,
                    execution_time=tracker.execution_time,
                )

    def _parse_response(self, response: dict[str, Any]) -> LLMAnalysisResult:
        """Parse OpenAI response into structured result"""
        try:
            content = response["choices"][0]["message"]["content"]
            data = json.loads(content)

            # Extract token usage
            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            # Estimate cost
            cost = self._estimate_cost(
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0)
            )

            return LLMAnalysisResult(
                primary_sentiment=data.get("primary_sentiment", "NEUTRAL"),
                secondary_attitude=data.get("secondary_attitude"),
                emotions=data.get("emotions", []),
                sarcasm_score=float(data.get("sarcasm_score", 0.0)),
                sarcasm_label=data.get("sarcasm_label", "not_sarcastic"),
                sarcasm_evidence=data.get("sarcasm_evidence"),
                confidence=float(data.get("confidence", 0.5)),
                provider="openai",
                model=self.model,
                execution_time=0.0,  # Will be set by caller
                token_count=total_tokens,
                cost_estimate=cost,
            )
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            raise

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on token usage"""
        # Default pricing if model not in map
        input_price, output_price = self.pricing.get(self.model, (2.50, 10.00))

        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return input_cost + output_cost
