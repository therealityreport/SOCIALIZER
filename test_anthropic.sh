#!/bin/bash
export $(grep -v '^#' .env | xargs 2>/dev/null)

echo "Testing Anthropic API..."
echo "API Key: ${ANTHROPIC_API_KEY:0:20}..."
echo "Model: $ANTHROPIC_MODEL"
echo ""

curl -s https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-opus-20240229",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "Say test"}]
  }' | python3 -m json.tool 2>&1
