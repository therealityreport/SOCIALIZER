# Multi-LLM Provider Benchmarking

Compare multiple LLM providers (OpenAI, Anthropic, Gemini) for sentiment analysis accuracy, cost, and latency.

## Overview

The benchmarking system allows you to test and compare multiple LLM APIs on the same Reddit comments to determine which provider performs best for reality TV sentiment analysis.

### Features

- **Multi-Provider Analysis**: Test OpenAI, Anthropic, and Gemini simultaneously
- **Parallel or Sequential Evaluation**: Choose execution mode
- **Sampling**: Benchmark a configurable fraction of comments (e.g., 25%)
- **Automatic Provider Selection**: Choose best result based on confidence
- **Comprehensive Metrics**: Confidence, latency, cost, and agreement scoring
- **Detailed Reports**: Per-thread and global comparison CSVs

## Configuration

### Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_ENDPOINT="https://api.openai.com/v1/chat/completions"

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-3-5-sonnet-20241022"
export ANTHROPIC_ENDPOINT="https://api.anthropic.com/v1/messages"

# Gemini
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-1.5-pro"
export GEMINI_ENDPOINT="https://generativelanguage.googleapis.com/v1beta/models"

# Control Settings
export LLM_PROVIDERS="openai,anthropic,gemini"
export LLM_EVAL_MODE="parallel"  # or "sequential"
export LLM_BENCHMARK_SAMPLES="0.25"  # 25% of comments
```

## Usage

### Basic Benchmark

Run benchmark on all threads with default 25% sampling:

```bash
python jobs/backfill_reddit_mentions.py \
  --benchmark-mode \
  --llm-providers openai,anthropic,gemini
```

### Single Thread Benchmark

Test a specific thread:

```bash
python jobs/backfill_reddit_mentions.py \
  --benchmark-mode \
  --llm-providers openai,anthropic,gemini \
  --thread-id 5 \
  --sample-rate 0.5  # 50% of comments
```

### Dry Run Benchmark

Test without database writes:

```bash
python jobs/backfill_reddit_mentions.py \
  --dry-run \
  --benchmark-mode \
  --llm-providers openai,anthropic,gemini \
  --thread-id 5
```

### Two-Provider Comparison

Compare just OpenAI and Anthropic:

```bash
python jobs/backfill_reddit_mentions.py \
  --benchmark-mode \
  --llm-providers openai,anthropic \
  --sample-rate 0.1  # 10% sampling for faster results
```

## Output Reports

### Per-Thread Benchmark CSV

Location: `qa_reports/benchmark_llm_thread_{id}.csv`

Columns:
- `comment_id`: Reddit comment ID
- `cast_member`: Cast member mentioned
- `text`: Comment text (first 200 chars)
- `{provider}_sentiment`: Sentiment label per provider
- `{provider}_confidence`: Confidence score per provider
- `{provider}_sarcasm`: Sarcasm score per provider
- `agreement_score`: Cross-provider agreement (0.0-1.0)
- `best_provider`: Provider with highest confidence

### Global Summary CSV

Location: `qa_reports/benchmark_summary.csv`

Columns:
- `provider`: Provider name
- `call_count`: Total API calls made
- `mean_confidence`: Average confidence score
- `std_confidence`: Confidence standard deviation
- `mean_latency`: Average response time (seconds)
- `std_latency`: Latency standard deviation
- `total_tokens`: Total tokens consumed
- `total_cost`: Estimated total cost (USD)
- `cost_per_1k_tokens`: Cost per 1K tokens
- `mean_agreement`: Average agreement with other providers
- `provider_score`: Composite quality score (0.0-1.0)

### Console Summary

At completion, a summary is printed:

```
================================================================================
LLM PROVIDER BENCHMARK SUMMARY
================================================================================

ANTHROPIC:
  Calls:              375
  Mean Confidence:    0.9120 ± 0.0643
  Mean Latency:       1.7342s ± 0.3421s
  Total Tokens:       487,230
  Total Cost:         $8.142300
  Cost per 1K tokens: $0.016710
  Mean Agreement:     0.8763
  PROVIDER SCORE:     0.8945

OPENAI:
  Calls:              375
  Mean Confidence:    0.8892 ± 0.0712
  Mean Latency:       1.2134s ± 0.2876s
  Total Tokens:       502,130
  Total Cost:         $1.506390
  Cost per 1K tokens: $0.003000
  Mean Agreement:     0.8621
  PROVIDER SCORE:     0.8823

GEMINI:
  Calls:              375
  Mean Confidence:    0.8654 ± 0.0891
  Mean Latency:       0.9876s ± 0.1987s
  Total Tokens:       478,920
  Total Cost:         $3.591900
  Cost per 1K tokens: $0.007500
  Mean Agreement:     0.8401
  PROVIDER SCORE:     0.8567

================================================================================
```

## Metrics Explained

### Provider Score

Composite score calculated as:
```
provider_score =
  0.4 * mean_confidence +
  0.3 * mean_agreement +
  0.2 * (1 - normalized_latency) +
  0.1 * (1 - normalized_cost)
```

Higher is better. Balances accuracy, consistency, speed, and cost.

### Agreement Score

Measures consensus across providers:
- **Sentiment Agreement** (70%): How often providers agree on positive/neutral/negative
- **Sarcasm Agreement** (30%): Variance in sarcasm scores (lower variance = higher agreement)

### Cost Estimation

Based on current pricing (as of Dec 2024):

| Provider | Input (per 1M tokens) | Output (per 1M tokens) |
|----------|----------------------|------------------------|
| GPT-4o-mini | $0.15 | $0.60 |
| Claude 3.5 Sonnet | $3.00 | $15.00 |
| Gemini 1.5 Pro | $1.25 | $5.00 |

Actual costs depend on token usage and may vary.

## Data Storage

### mentions.llm_results (JSONB)

Stores all provider results:

```json
{
  "openai": {
    "primary_sentiment": "POSITIVE",
    "secondary_attitude": "Admiration/Support",
    "emotions": [{"label": "joy", "score": 0.87}],
    "sarcasm_score": 0.32,
    "confidence": 0.91,
    "execution_time": 1.23,
    "token_count": 512,
    "cost_estimate": 0.0012
  },
  "anthropic": {...},
  "gemini": {...}
}
```

### mentions.provider_preferred

Stores the name of the provider whose result was used as the primary sentiment:

```sql
SELECT provider_preferred, COUNT(*)
FROM mentions
WHERE provider_preferred IS NOT NULL
GROUP BY provider_preferred;

provider_preferred | count
-------------------|-------
anthropic          | 2,145
openai             | 1,823
gemini             | 967
```

## Interpreting Results

### High Confidence, High Agreement

**Example**: All providers show ~0.9 confidence and 0.85+ agreement
- ✅ Strong signal: Comment sentiment is clear
- ✅ All providers suitable
- 💡 Choose lowest cost provider (usually OpenAI gpt-4o-mini)

### High Confidence, Low Agreement

**Example**: Providers confident but disagree on sentiment
- ⚠️ Complex comment with mixed sentiment
- ⚠️ Possible sarcasm or contextual nuance
- 💡 Review manually, consider Anthropic (best at nuance)

### Low Confidence Across All

**Example**: All providers show <0.6 confidence
- ⚠️ Ambiguous comment
- 💡 Flag for manual review
- 💡 May need more context or transcript data

### Cost-Performance Trade-off

**Example**: Anthropic scores 5% higher but costs 10x more
- 💡 Use Anthropic for high-stakes analysis (PR monitoring)
- 💡 Use OpenAI gpt-4o-mini for bulk processing
- 💡 Consider Gemini for middle ground

## Best Practices

### Sample Size

- **Development/Testing**: 10-25% (`--sample-rate 0.1`)
- **Validation**: 25-50% (`--sample-rate 0.25`)
- **Production Comparison**: 100% on small dataset

### Provider Selection

Start with all three, then:
1. Review provider_score in summary
2. Check agreement patterns
3. Spot-check disagreements in thread CSVs
4. Choose based on your priorities:
   - **Accuracy**: Highest provider_score
   - **Cost**: OpenAI gpt-4o-mini
   - **Balanced**: Gemini 1.5 Pro

### Re-running

The job is idempotent. You can re-run with different providers:

```bash
# First run: Compare all three
python jobs/backfill_reddit_mentions.py --benchmark-mode --llm-providers openai,anthropic,gemini --thread-id 5

# Second run: Just test Gemini vs existing
python jobs/backfill_reddit_mentions.py --benchmark-mode --llm-providers gemini --thread-id 5 --sample-rate 1.0
```

## Troubleshooting

### "Provider X returned error"

Check API key and model availability:
```bash
# Test OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Test Anthropic
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":1024,"messages":[{"role":"user","content":"test"}]}'
```

### Rate Limiting

Each provider has different rate limits. The job includes retry logic, but if you hit limits:
- Reduce `--sample-rate`
- Use `LLM_EVAL_MODE=sequential` instead of `parallel`
- Add delays in `llm_providers/base.py`

### Cost Overruns

Monitor costs in real-time:
```bash
# Check summary after small run
python jobs/backfill_reddit_mentions.py --benchmark-mode --thread-id 5 --sample-rate 0.1

# Review qa_reports/benchmark_summary.csv
cat qa_reports/benchmark_summary.csv
```

Estimate before full run:
```
cost_estimate = (total_comments * sample_rate * providers * avg_tokens) / 1M * price_per_1M
```

Example:
- 10,000 comments × 0.25 sample × 3 providers × 500 tokens / 1M = 3.75M tokens
- At ~$5/1M blended = ~$18.75

## Next Steps

After benchmarking:
1. Review `qa_reports/benchmark_summary.csv`
2. Identify best-performing provider
3. Update `.env` to use optimal provider:
   ```bash
   export LLM_PROVIDERS="anthropic"  # or openai, or gemini
   ```
4. Run full backfill with chosen provider
5. Monitor accuracy on production data
6. Re-benchmark quarterly as models improve

## Support

For questions or issues:
- Check provider API status pages
- Review logs for detailed error messages
- Examine `qa_reports/` for data quality issues
- Compare results manually on known-good examples
