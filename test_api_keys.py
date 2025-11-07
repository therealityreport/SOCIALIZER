"""Simple API Key Test Script

Tests OpenAI, Anthropic, and Gemini API keys without requiring full app dependencies.
"""
import asyncio
import os
import json
from pathlib import Path

# Load .env manually
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value


async def test_openai():
    """Test OpenAI API key"""
    try:
        import httpx

        api_key = os.getenv('OPENAI_API_KEY')
        model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

        if not api_key or api_key.startswith('your-'):
            return False, "API key not set in .env", None

        print(f"Testing OpenAI with model: {model}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                'model': model,
                'messages': [
                    {'role': 'user', 'content': 'Say "test successful" in 2 words'}
                ],
            }

            # Newer models (e.g., gpt-4.1/gpt-5 family) renamed the max token field.
            if any(tag in model for tag in ('gpt-5', 'gpt-4.1')):
                payload['max_completion_tokens'] = 50
            else:
                payload['max_tokens'] = 10

            response = await client.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                raw_content = data['choices'][0]['message'].get('content', '')
                if isinstance(raw_content, str):
                    message = raw_content.strip()
                elif isinstance(raw_content, list):
                    parts = []
                    for part in raw_content:
                        if isinstance(part, dict):
                            parts.append(part.get('text') or part.get('content') or '')
                        else:
                            parts.append(str(part))
                    message = " ".join(filter(None, parts)).strip()
                else:
                    message = str(raw_content).strip()
                if not message:
                    finish_reason = data['choices'][0].get('finish_reason')
                    message = f"(no text returned; finish_reason={finish_reason})"
                usage = data.get('usage') or {}
                tokens = usage.get('total_tokens') or (
                    usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                )
                return True, f"Response: {message}", {"tokens": tokens, "model": model}
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}", None

    except Exception as e:
        return False, str(e), None


async def test_anthropic():
    """Test Anthropic API key"""
    try:
        import httpx

        api_key = os.getenv('ANTHROPIC_API_KEY')
        model = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')

        if not api_key or api_key.startswith('your-'):
            return False, "API key not set in .env", None

        print(f"Testing Anthropic with model: {model}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'max_tokens': 10,
                    'messages': [
                        {'role': 'user', 'content': 'Say "test successful" in 2 words'}
                    ]
                }
            )

            if response.status_code == 200:
                data = response.json()
                message = data['content'][0]['text']
                tokens = data['usage']['input_tokens'] + data['usage']['output_tokens']
                return True, f"Response: {message}", {"tokens": tokens, "model": model}
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}", None

    except Exception as e:
        return False, str(e), None


async def test_gemini():
    """Test Gemini API key"""
    try:
        import httpx

        api_key = os.getenv('GEMINI_API_KEY')
        model = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')

        if not api_key or api_key.startswith('your-'):
            return False, "API key not set in .env", None

        print(f"Testing Gemini with model: {model}")

        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={'Content-Type': 'application/json'},
                json={
                    'contents': [{
                        'parts': [{'text': 'Say "test successful" in 2 words'}]
                    }]
                }
            )

            if response.status_code == 200:
                data = response.json()
                message = data['candidates'][0]['content']['parts'][0]['text']
                tokens = data.get('usageMetadata', {}).get('totalTokenCount', 0)
                return True, f"Response: {message.strip()}", {"tokens": tokens, "model": model}
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}", None

    except Exception as e:
        return False, str(e), None


async def main():
    """Run all tests"""
    print("=" * 80)
    print("LLM API KEY TEST")
    print("=" * 80)
    print()

    # Check env vars
    print("Environment Variables:")
    print(f"  OPENAI_API_KEY: {'✓' if os.getenv('OPENAI_API_KEY', '').startswith('sk-') else '✗'}")
    print(f"  ANTHROPIC_API_KEY: {'✓' if os.getenv('ANTHROPIC_API_KEY', '').startswith('sk-ant-') else '✗'}")
    print(f"  GEMINI_API_KEY: {'✓' if os.getenv('GEMINI_API_KEY', '').startswith('AIzaSy') else '✗'}")
    print()

    results = {}

    # Test OpenAI
    print("-" * 80)
    print("TESTING OPENAI...")
    success, message, data = await test_openai()
    results['OpenAI'] = success
    if success:
        print(f"✅ OpenAI: SUCCESS")
        print(f"   {message}")
        if data:
            print(f"   Model: {data['model']}, Tokens: {data['tokens']}")
    else:
        print(f"❌ OpenAI: FAILED")
        print(f"   Error: {message}")
    print()

    # Test Anthropic
    print("-" * 80)
    print("TESTING ANTHROPIC...")
    success, message, data = await test_anthropic()
    results['Anthropic'] = success
    if success:
        print(f"✅ Anthropic: SUCCESS")
        print(f"   {message}")
        if data:
            print(f"   Model: {data['model']}, Tokens: {data['tokens']}")
    else:
        print(f"❌ Anthropic: FAILED")
        print(f"   Error: {message}")
    print()

    # Test Gemini
    print("-" * 80)
    print("TESTING GEMINI...")
    success, message, data = await test_gemini()
    results['Gemini'] = success
    if success:
        print(f"✅ Gemini: SUCCESS")
        print(f"   {message}")
        if data:
            print(f"   Model: {data['model']}, Tokens: {data['tokens']}")
    else:
        print(f"❌ Gemini: FAILED")
        print(f"   Error: {message}")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(results.values())
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()

    for provider, success in results.items():
        print(f"  {provider:12s} {'✅ PASS' if success else '❌ FAIL'}")

    print()
    if passed == total:
        print("🎉 All API keys are working!")
        print()
        print("You can now:")
        print("  - Run benchmarks to compare providers")
        print("  - Use the automated provider selection")
        print("  - Monitor costs and drift")
    else:
        print("⚠️  Some API keys need attention.")
        print()
        print("To fix:")
        print("  1. Update your .env file with valid API keys")
        print("  2. Remove any quotes around the keys")
        print("  3. Make sure there are no extra spaces")
        print("  4. Verify the keys have proper permissions")

    return 0 if passed == total else 1


if __name__ == '__main__':
    try:
        import httpx
    except ImportError:
        print("Error: httpx not installed. Install with: pip install httpx")
        exit(1)

    exit_code = asyncio.run(main())
    exit(exit_code)
