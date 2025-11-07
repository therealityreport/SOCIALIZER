"""Test LLM Provider API Keys

Simple script to verify OpenAI, Anthropic, and Gemini API keys are configured correctly.
"""
import asyncio
import logging
import os
import sys

from app.services.llm_providers import OpenAIClient, AnthropicClient, GeminiClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_provider(provider_name: str, client, test_text: str):
    """
    Test a single LLM provider

    Args:
        provider_name: Name of the provider
        client: LLM client instance
        test_text: Test text for analysis

    Returns:
        Tuple of (success: bool, message: str, result: dict or None)
    """
    try:
        logger.info(f"Testing {provider_name}...")

        result = await client.analyze(
            text=test_text,
            context={"test": True}
        )

        logger.info(f"✅ {provider_name} SUCCESS")
        logger.info(f"   Model: {result.model}")
        logger.info(f"   Sentiment: {result.primary_sentiment}")
        logger.info(f"   Confidence: {result.confidence:.3f}")
        logger.info(f"   Latency: {result.execution_time:.2f}s")
        logger.info(f"   Tokens: {result.token_count}")
        logger.info(f"   Cost: ${result.cost_estimate:.6f}" if result.cost_estimate else "   Cost: N/A")

        return (True, "Connected successfully", {
            "model": result.model,
            "sentiment": result.primary_sentiment,
            "confidence": result.confidence,
            "latency": result.execution_time,
            "tokens": result.token_count,
            "cost": result.cost_estimate,
        })

    except Exception as e:
        logger.error(f"❌ {provider_name} FAILED: {str(e)}")
        return (False, str(e), None)


async def main():
    """Run tests for all providers"""
    print("=" * 80)
    print("LLM PROVIDER API KEY TEST")
    print("=" * 80)
    print()

    # Test text
    test_text = "I absolutely loved this episode! The drama was incredible and Lisa was amazing."

    # Check environment variables
    print("Checking environment variables...")
    print(f"  OPENAI_API_KEY: {'✓ Set' if os.getenv('OPENAI_API_KEY') else '✗ Not set'}")
    print(f"  OPENAI_MODEL: {os.getenv('OPENAI_MODEL', 'gpt-4o-mini (default)')}")
    print(f"  ANTHROPIC_API_KEY: {'✓ Set' if os.getenv('ANTHROPIC_API_KEY') else '✗ Not set'}")
    print(f"  ANTHROPIC_MODEL: {os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022 (default)')}")
    print(f"  GEMINI_API_KEY: {'✓ Set' if os.getenv('GEMINI_API_KEY') else '✗ Not set'}")
    print(f"  GEMINI_MODEL: {os.getenv('GEMINI_MODEL', 'gemini-1.5-pro (default)')}")
    print()

    # Initialize clients
    results = {}

    # Test OpenAI
    print("-" * 80)
    try:
        openai_client = OpenAIClient()
        results['openai'] = await test_provider("OpenAI", openai_client, test_text)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        results['openai'] = (False, f"Initialization failed: {e}", None)
    print()

    # Test Anthropic
    print("-" * 80)
    try:
        anthropic_client = AnthropicClient()
        results['anthropic'] = await test_provider("Anthropic", anthropic_client, test_text)
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")
        results['anthropic'] = (False, f"Initialization failed: {e}", None)
    print()

    # Test Gemini
    print("-" * 80)
    try:
        gemini_client = GeminiClient()
        results['gemini'] = await test_provider("Gemini", gemini_client, test_text)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        results['gemini'] = (False, f"Initialization failed: {e}", None)
    print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    all_passed = True
    for provider, (success, message, result) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{provider.upper():12s} {status}")
        if not success:
            print(f"             Error: {message}")
            all_passed = False

    print()

    if all_passed:
        print("🎉 All providers connected successfully!")
        print()
        print("Next steps:")
        print("  1. Run a benchmark: python jobs/backfill_reddit_mentions.py --benchmark-mode --sample-rate 0.1")
        print("  2. Check provider selection: cat config/active_provider.json")
        print("  3. Monitor costs: python jobs/check_provider_costs.py")
        return 0
    else:
        print("⚠️  Some providers failed. Check your API keys in .env")
        print()
        print("How to fix:")
        print("  1. Verify API keys are correct (no extra spaces/quotes)")
        print("  2. Check API key has proper permissions")
        print("  3. Verify model names match provider's API")
        print("  4. Check network connectivity")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
