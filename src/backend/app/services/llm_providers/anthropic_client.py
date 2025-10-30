"""Anthropic LLM Client"""
import json
import logging
import os
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseLLMClient, LLMAnalysisResult

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client for sentiment analysis"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """Initialize Anthropic client"""
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        endpoint = endpoint or os.getenv(
            "ANTHROPIC_ENDPOINT",
            "https://api.anthropic.com/v1/messages"
        )
        super().__init__(api_key, model, endpoint)

        # Pricing per 1M tokens (input/output)
        self.pricing = {
            "claude-3-5-sonnet-20241022": (3.00, 15.00),
            "claude-3-opus-20240229": (15.00, 75.00),
            "claude-3-haiku-20240307": (0.25, 1.25),
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
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1024,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Anthropic rate limit hit, retrying...")
                    raise
                else:
                    logger.error(f"Anthropic HTTP error: {e.response.status_code}")
                    raise
            except httpx.RequestError as e:
                logger.error(f"Anthropic request error: {e}")
                raise

    async def analyze(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> LLMAnalysisResult:
        """Analyze comment with Anthropic Claude"""
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
                logger.error(f"Anthropic analysis failed: {e}")
                # Return neutral fallback
                return LLMAnalysisResult(
                    primary_sentiment="NEUTRAL",
                    secondary_attitude=None,
                    emotions=[],
                    sarcasm_score=0.0,
                    sarcasm_label="not_sarcastic",
                    sarcasm_evidence=None,
                    confidence=0.0,
                    provider="anthropic",
                    model=self.model,
                    execution_time=tracker.execution_time,
                )

    def _parse_response(self, response: dict[str, Any]) -> LLMAnalysisResult:
        """Parse Anthropic response into structured result"""
        try:
            # Anthropic returns content as array of content blocks
            content = response["content"][0]["text"]

            # Extract JSON from the response (may be wrapped in markdown)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove trailing ```
            content = content.strip()

            data = json.loads(content)

            # Extract token usage
            usage = response.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens

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
                provider="anthropic",
                model=self.model,
                execution_time=0.0,  # Will be set by caller
                token_count=total_tokens,
                cost_estimate=cost,
            )
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Anthropic response: {e}")
            logger.error(f"Response: {response}")
            raise

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on token usage"""
        # Default pricing if model not in map
        input_price, output_price = self.pricing.get(self.model, (3.00, 15.00))

        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return input_cost + output_cost
