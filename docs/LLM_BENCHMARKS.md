# LLM Provider Benchmarking & Evaluation Loop

Automated system for evaluating, selecting, and monitoring LLM providers for Reddit sentiment analysis.

## Overview

SOCIALIZER uses a **Provider Evaluation Loop** to continuously optimize LLM selection based on accuracy, cost, latency, and agreement metrics. The system automatically benchmarks providers, selects the best performer, monitors for quality drift, and triggers re-evaluation when needed.

## Architecture

```
┌─────────────────┐
│   Benchmark     │  ← Run quarterly or on-demand
│   All Providers │     Test OpenAI, Anthropic, Gemini
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Provider      │  ← Nightly automated selection
│   Selection     │     Choose highest provider_score
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Active       │  ← Stored in config/active_provider.json
│   Provider      │     ENV: PROVIDER_PREFERRED
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Production     │  ← All new analysis uses active provider
│   Analysis      │     Fallback to secondary if >5% failure
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Drift QA      │  ← Weekly: re-analyze 5% with secondary
│   Monitoring    │     Alert when agreement < 0.8
└────────┬────────┘
         │
         ▼ (if drift detected)
┌─────────────────┐
│   Benchmark     │  ← Re-run evaluation
│   Trigger       │
└─────────────────┘
```

## Components

### 1. Benchmark Execution

**Location:** `jobs/backfill_reddit_mentions.py --benchmark-mode`

**Purpose:** Compare multiple LLM providers on same dataset

**Frequency:**
- Quarterly (scheduled)
- On-demand when needed
- When model versions update
- After quality drift detection

**Output:**
- `qa_reports/benchmark_summary.csv` - Provider metrics
- `qa_reports/benchmark_llm_thread_{id}.csv` - Per-thread comparisons

**Metrics Collected:**
- Mean confidence ± std deviation
- Mean latency ± std deviation
- Total tokens and cost
- Cost per 1K tokens
- Agreement score (sentiment + sarcasm)
- Composite provider score

### 2. Automated Provider Selection

**Location:** `jobs/select_best_llm.py` (to be implemented in BE-LLM-005)

**Purpose:** Automatically choose optimal provider based on benchmark results

**Schedule:** Nightly at 3 AM UTC

**Selection Logic:**
```python
# Read latest benchmark results
summary = read_csv("qa_reports/benchmark_summary.csv")

# Find max provider score
max_score = summary["provider_score"].max()

# Select providers within 85% of max
threshold = 0.85 * max_score
candidates = summary[summary["provider_score"] >= threshold]

# Choose lowest cost among high performers
best_provider = candidates.sort_values("cost_per_1k_tokens").iloc[0]

# Update configuration
update_config("config/active_provider.json", best_provider["provider"])
set_env("PROVIDER_PREFERRED", best_provider["provider"])
log_provider_change(best_provider)
```

**Output:**
- Updates `config/active_provider.json`
- Logs change to `logs/provider_selection.log`
- Sends notification if provider changes

### 3. Production Integration

**Location:** All analysis jobs (backfill, streaming, etc.)

**Purpose:** Route all analysis to active provider with fallback

**Implementation:**
```python
# Read active provider
provider = read_provider_config()

# Initialize with fallback
try:
    llm_service = get_llm_service(provider)
except Exception:
    # Fallback to second-best
    llm_service = get_llm_service(get_fallback_provider())

# Track failure rate
if failure_rate > 0.05:
    alert_and_switch_provider()
```

**Fallback Cascade:**
1. Primary: `PROVIDER_PREFERRED` (from config)
2. Secondary: Second-highest provider_score
3. Tertiary: OpenAI gpt-4o-mini (lowest cost baseline)

### 4. Quality Drift Monitoring

**Location:** `jobs/check_llm_drift.py` (to be implemented in BE-LLM-008)

**Purpose:** Detect when active provider quality degrades

**Schedule:** Weekly on Sunday at midnight UTC

**Process:**
1. Sample 5% of recent comments analyzed by active provider
2. Re-analyze with secondary provider
3. Calculate agreement score
4. Flag if agreement < 0.8
5. Generate `qa_reports/drift_summary.csv`

**Alert Triggers:**
- Agreement < 0.8 (high drift)
- Confidence drop > 10% from baseline
- Error rate > 5%
- Latency increase > 50%

**Actions on Drift:**
- Send Slack/email alert
- Log drift metrics
- Schedule re-benchmark
- (Optional) Auto-switch to secondary provider

### 5. Cost Monitoring

**Location:** `services/benchmark_evaluator.py` + DB tracking

**Purpose:** Track LLM API costs and prevent overruns

**Implementation:**
```python
# Log costs to database
INSERT INTO provider_costs (
    provider,
    date,
    tokens_consumed,
    cost_usd,
    comments_analyzed
) VALUES (?, ?, ?, ?, ?)

# Check monthly spend
monthly_total = query(
    "SELECT SUM(cost_usd) FROM provider_costs "
    "WHERE provider = ? AND date >= date_trunc('month', now())"
)

# Alert if exceeding threshold
if monthly_total > COST_ALERT_THRESHOLD:
    send_alert(f"LLM cost ${monthly_total} exceeds ${COST_ALERT_THRESHOLD}")
```

**Alert Channels:**
- Email to `ALERT_EMAIL`
- Slack webhook to `SLACK_WEBHOOK_URL`
- Dashboard notification

## Configuration

### Environment Variables

```bash
# Active provider (set by automation)
PROVIDER_PREFERRED=openai

# Benchmarking
LLM_PROVIDERS=openai,anthropic,gemini
LLM_EVAL_MODE=parallel
LLM_BENCHMARK_SAMPLES=0.25

# Automation schedule
BENCHMARK_CRON_SCHEDULE="0 3 * * 0"  # Sunday 3 AM UTC
DRIFT_CHECK_SCHEDULE="0 0 * * 0"     # Sunday midnight UTC
PROVIDER_SELECT_SCHEDULE="0 3 * * *" # Daily 3 AM UTC

# Drift detection
DRIFT_SAMPLE_RATE=0.05               # 5% of comments
DRIFT_AGREEMENT_THRESHOLD=0.8        # Alert if < 0.8

# Cost controls
COST_ALERT_THRESHOLD=500             # $500/month
ALERT_EMAIL=ops@therealityreport.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### Active Provider Config

**Location:** `config/active_provider.json`

```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "selected_at": "2025-11-30T03:00:00Z",
  "provider_score": 0.8945,
  "mean_confidence": 0.9120,
  "cost_per_1k_tokens": 0.01671,
  "reason": "highest_score",
  "fallback_provider": "openai",
  "fallback_model": "gpt-4o-mini"
}
```

## Dashboard Integration

### LLM Performance Panel

**Location:** Analytics UI → LLM Performance

**Metrics Displayed:**
1. **Active Provider Card**
   - Current provider and model
   - Time since selection
   - Current provider score
   - Month-to-date cost

2. **Provider Comparison Chart**
   - Time-series: confidence, latency, cost over time
   - Per-provider trend lines
   - Selection change markers

3. **Quality Metrics Table**
   | Provider | Confidence | Latency | Cost/1K | Agreement | Score |
   |----------|-----------|---------|---------|-----------|-------|
   | Anthropic | 0.912 | 1.73s | $0.0167 | 0.876 | 0.895 |
   | OpenAI | 0.889 | 1.21s | $0.0030 | 0.862 | 0.882 |
   | Gemini | 0.865 | 0.99s | $0.0075 | 0.840 | 0.857 |

4. **Drift Monitor**
   - Weekly agreement scores
   - Alert indicators
   - Last drift check timestamp

5. **Cost Tracker**
   - Monthly spend by provider
   - Running total vs threshold
   - Projected monthly cost

## Re-Benchmark Triggers

### Scheduled Benchmarks

**Quarterly Schedule:**
- January 1st (Q1)
- April 1st (Q2)
- July 1st (Q3)
- October 1st (Q4)

**Rationale:** Quarterly cadence captures model updates while minimizing cost

### Event-Triggered Benchmarks

**Automatic Triggers:**
1. **Drift Detection:** Agreement < 0.8 for 2 consecutive weeks
2. **Error Rate:** Active provider failures > 5%
3. **Cost Spike:** Weekly cost > 2× baseline
4. **Model Update:** Provider announces new model version

**Manual Triggers:**
- Product team requests comparison
- New provider becomes available
- Investigating quality issues

## Operational Procedures

### Adding a New Provider

1. Implement client in `app/services/llm_providers/{provider}_client.py`
2. Add pricing to client's `__init__`
3. Register in `LLMServiceManager.client_map`
4. Update `LLM_PROVIDERS` env var
5. Run benchmark: `--llm-providers openai,anthropic,gemini,new_provider`
6. Review results in `qa_reports/benchmark_summary.csv`
7. If score competitive, add to rotation

### Responding to Drift Alerts

1. **Review Drift Report:**
   ```bash
   cat qa_reports/drift_summary.csv
   ```

2. **Check Recent Changes:**
   - Provider model updates?
   - Data quality changes?
   - Prompt modifications?

3. **Validate with Spot Check:**
   - Manually review disagreement samples
   - Confirm accuracy regression

4. **Take Action:**
   - **Minor Drift (<0.75):** Schedule re-benchmark
   - **Major Drift (<0.7):** Switch to secondary provider immediately
   - **Critical Drift (<0.6):** Pause analysis, investigate

### Cost Overrun Response

1. **Review Cost Breakdown:**
   ```sql
   SELECT provider, SUM(tokens_consumed), SUM(cost_usd)
   FROM provider_costs
   WHERE date >= date_trunc('month', now())
   GROUP BY provider;
   ```

2. **Identify Root Cause:**
   - Unexpected traffic surge?
   - Inefficient prompts?
   - Token usage increase?

3. **Mitigation Options:**
   - Switch to lower-cost provider
   - Reduce sample rate
   - Optimize prompt length
   - Implement caching
   - Pause non-critical analysis

## Best Practices

### Benchmarking

- **Sample Size:** Use 25-50% of data for reliable metrics
- **Diversity:** Test across multiple episodes and franchises
- **Consistency:** Use same sample set for all providers
- **Timing:** Run during off-peak hours to avoid rate limits
- **Documentation:** Log benchmark parameters and date

### Provider Selection

- **Balance:** Don't always choose highest score if cost difference is large
- **Stability:** Avoid switching providers too frequently (< monthly)
- **Fallback:** Always maintain working secondary provider
- **Testing:** Test new provider on small sample before full switch

### Drift Monitoring

- **Baseline:** Establish baseline agreement scores after benchmark
- **Threshold:** Set agreement threshold at 80% of baseline
- **Frequency:** Weekly checks sufficient for most use cases
- **Action Plan:** Define clear escalation path for different drift levels

### Cost Management

- **Budget:** Set realistic monthly cost thresholds
- **Tracking:** Log every API call with token usage
- **Alerts:** Configure alerts at 75% and 90% of threshold
- **Optimization:** Regular prompt engineering to reduce token usage

## Troubleshooting

### Provider Selection Not Running

```bash
# Check cron schedule
echo $BENCHMARK_CRON_SCHEDULE

# Verify job exists
ls -la jobs/select_best_llm.py

# Check logs
tail -f logs/provider_selection.log

# Manual run
python jobs/select_best_llm.py --force
```

### Drift Check Failing

```bash
# Verify sample rate
echo $DRIFT_SAMPLE_RATE

# Check recent comments
SELECT COUNT(*) FROM mentions
WHERE created_at > now() - interval '7 days'
AND provider_preferred IS NOT NULL;

# Manual drift check
python jobs/check_llm_drift.py --sample-rate 0.05
```

### Cost Alert Threshold

```bash
# Check current spend
SELECT SUM(cost_usd) FROM provider_costs
WHERE date >= date_trunc('month', now());

# Adjust threshold
export COST_ALERT_THRESHOLD=1000

# Test alert
python -c "from app.services.cost_monitor import test_alert; test_alert()"
```

## Metrics Definitions

### Provider Score

Composite score balancing multiple factors:
```
provider_score =
    0.4 × mean_confidence +
    0.3 × mean_agreement +
    0.2 × (1 - normalized_latency) +
    0.1 × (1 - normalized_cost)
```

**Range:** 0.0 (worst) to 1.0 (perfect)

**Interpretation:**
- 0.90+: Excellent (top tier)
- 0.85-0.89: Very good
- 0.80-0.84: Good
- 0.75-0.79: Acceptable
- <0.75: Below threshold

### Agreement Score

Measures consistency across providers:
```
agreement_score =
    0.7 × sentiment_agreement +
    0.3 × sarcasm_agreement

sentiment_agreement = (count matching) / (total comparisons)
sarcasm_agreement = 1 - min(variance, 1.0)
```

**Range:** 0.0 (complete disagreement) to 1.0 (perfect agreement)

**Interpretation:**
- 0.90+: High agreement (clear sentiment)
- 0.80-0.89: Good agreement
- 0.70-0.79: Moderate agreement (possible nuance)
- <0.70: Low agreement (ambiguous or complex)

### Cost Efficiency

Normalized cost per 1K tokens:
```
cost_efficiency = 1 - (provider_cost / max_provider_cost)
```

**Range:** 0.0 (most expensive) to 1.0 (cheapest)

## Future Enhancements

### Planned Features (Beyond Phase 2)

1. **A/B Testing Framework**
   - Split traffic 90/10 between active and test provider
   - Measure real-world accuracy on production data
   - Gradual rollout of provider changes

2. **Model-Specific Routing**
   - Route sarcasm-heavy comments to best sarcasm detector
   - Route straightforward comments to cheapest provider
   - Dynamic routing based on comment characteristics

3. **Ensemble Predictions**
   - Combine multiple provider results
   - Weighted voting based on historical accuracy
   - Higher confidence from consensus

4. **Real-Time Cost Optimization**
   - Adjust provider mix based on remaining monthly budget
   - Auto-throttle expensive providers near threshold
   - Dynamic sample rate adjustment

5. **Provider SLA Monitoring**
   - Track uptime and reliability
   - Measure P95/P99 latencies
   - Auto-failover on SLA breaches

## Appendix

### Provider Pricing (as of Dec 2024)

| Provider | Model | Input/1M | Output/1M |
|----------|-------|----------|-----------|
| OpenAI | gpt-4o | $2.50 | $10.00 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 |
| Anthropic | claude-3-5-sonnet | $3.00 | $15.00 |
| Anthropic | claude-3-opus | $15.00 | $75.00 |
| Anthropic | claude-3-haiku | $0.25 | $1.25 |
| Gemini | gemini-1.5-pro | $1.25 | $5.00 |
| Gemini | gemini-1.5-flash | $0.075 | $0.30 |

### Cron Schedule Examples

```bash
# Every Sunday at 3 AM
0 3 * * 0

# Daily at 3 AM
0 3 * * *

# First of every month at midnight
0 0 1 * *

# Every 6 hours
0 */6 * * *

# Weekdays at 9 AM
0 9 * * 1-5
```

### SQL Queries

**Monthly cost by provider:**
```sql
SELECT
    provider,
    date_trunc('month', date) as month,
    SUM(tokens_consumed) as total_tokens,
    SUM(cost_usd) as total_cost,
    AVG(cost_usd / NULLIF(comments_analyzed, 0)) as cost_per_comment
FROM provider_costs
GROUP BY provider, date_trunc('month', date)
ORDER BY month DESC, provider;
```

**Provider selection history:**
```sql
SELECT
    provider,
    selected_at,
    provider_score,
    mean_confidence,
    cost_per_1k_tokens,
    reason
FROM provider_selection_log
ORDER BY selected_at DESC
LIMIT 20;
```

**Drift alerts:**
```sql
SELECT
    check_date,
    primary_provider,
    secondary_provider,
    agreement_score,
    samples_checked,
    status
FROM drift_checks
WHERE agreement_score < 0.8
ORDER BY check_date DESC;
```
