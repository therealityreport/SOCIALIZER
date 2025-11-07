#!/bin/bash

# Load environment variables
export $(grep -v '^#' .env | xargs)

echo "================================================================================"
echo "LLM API KEY TEST"
echo "================================================================================"
echo ""

# Test OpenAI
echo "--- TESTING OPENAI ---"
OPENAI_RESPONSE=$(curl -s -w "\n%{http_code}" https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say test"}],
    "max_tokens": 5
  }')

HTTP_CODE=$(echo "$OPENAI_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$OPENAI_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ OpenAI: SUCCESS"
    echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Response: {data['choices'][0]['message']['content']}\")" 2>/dev/null || echo "   (Response received)"
else
    echo "❌ OpenAI: FAILED (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Error: {data.get('error', {}).get('message', 'Unknown error')}\")" 2>/dev/null || echo "   $RESPONSE_BODY"
fi
echo ""

# Test Anthropic
echo "--- TESTING ANTHROPIC ---"
ANTHROPIC_RESPONSE=$(curl -s -w "\n%{http_code}" https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d "{
    \"model\": \"$ANTHROPIC_MODEL\",
    \"max_tokens\": 5,
    \"messages\": [{\"role\": \"user\", \"content\": \"Say test\"}]
  }")

HTTP_CODE=$(echo "$ANTHROPIC_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$ANTHROPIC_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Anthropic: SUCCESS"
    echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Response: {data['content'][0]['text']}\")" 2>/dev/null || echo "   (Response received)"
else
    echo "❌ Anthropic: FAILED (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Error: {data.get('error', {}).get('message', 'Unknown error')}\")" 2>/dev/null || echo "   $RESPONSE_BODY"
fi
echo ""

# Test Gemini
echo "--- TESTING GEMINI ---"
GEMINI_RESPONSE=$(curl -s -w "\n%{http_code}" "https://generativelanguage.googleapis.com/v1beta/models/$GEMINI_MODEL:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{"text": "Say test"}]
    }]
  }')

HTTP_CODE=$(echo "$GEMINI_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$GEMINI_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Gemini: SUCCESS"
    echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Response: {data['candidates'][0]['content']['parts'][0]['text'].strip()}\")" 2>/dev/null || echo "   (Response received)"
else
    echo "❌ Gemini: FAILED (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Error: {data.get('error', {}).get('message', 'Unknown error')}\")" 2>/dev/null || echo "   $RESPONSE_BODY"
fi
echo ""

echo "================================================================================"
echo "Test complete! Check results above."
echo "================================================================================"
