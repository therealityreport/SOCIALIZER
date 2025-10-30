# Reddit Mentions Backfill Job

This job applies LLM-driven sentiment analysis and signal extraction to all existing Reddit threads and comments.

## Features

### LLM-Driven Analysis
- **Primary Sentiment**: POSITIVE, NEUTRAL, NEGATIVE
- **Secondary Attitude**: Admiration/Support, Shady/Humor, Analytical, Annoyed, Hatred/Disgust, Sadness/Sympathy/Distress
- **Emotion Extraction**: Specific emotions (joy, amusement, disgust, etc.)
- **Sarcasm Detection**: Score, label, and evidence

### Computed Signals
- **Emoji Analysis**: Count, list, polarity
- **Media Detection**: GIF, image, video, domains
- **Text Patterns**: Hashtags, ALL-CAPS ratio, punctuation intensity, negations, questions
- **Engagement Metrics**: Upvotes, replies, awards, velocity, controversy

### Weighted Aggregation
- Uses formula: `weight = upvotes_new * confidence`
- Respects `WEIGHT_CAP` (default 200)
- Supports linear, logarithmic, and sqrt weighting modes

## Prerequisites

1. **Database Migration**: Run the migration first
   ```bash
   cd src/backend
   alembic upgrade head
   ```

2. **Environment Variables**: Configure LLM settings
   ```bash
   # Required
   export LLM_MODEL="gpt-4"
   export LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"
   export OPENAI_API_KEY="sk-..."

   # Optional (with defaults)
   export CONFIDENCE_THRESHOLD=0.75
   export SARCASM_THRESHOLD=0.5
   export WEIGHTING_MODE=linear
   export WEIGHT_CAP=200
   ```

3. **Dependencies**: Install required packages
   ```bash
   pip install emoji httpx tenacity
   ```

## Usage

### Dry Run (No Database Writes)
Test the backfill without modifying data:
```bash
python jobs/backfill_reddit_mentions.py --dry-run
```

### Process All Threads
Run full backfill on all Reddit threads:
```bash
python jobs/backfill_reddit_mentions.py
```

### Process Single Thread
Backfill a specific thread for testing:
```bash
python jobs/backfill_reddit_mentions.py --thread-id 123
```

### Custom Batch Size
Adjust batch size for processing:
```bash
python jobs/backfill_reddit_mentions.py --batch-size 50
```

## Idempotency

The job is idempotent and safe to re-run:
- Uses `ON CONFLICT` to update existing mentions
- Cache prevents duplicate LLM calls
- Can resume from any point
- Safe to run multiple times on same data

## Monitoring

### Progress Logs
The job outputs progress every 100 comments:
```
Processing thread 5: RHONY S14E08 Discussion
Found 1523 comments
Processed 100 comments...
Processed 200 comments...
...
Thread 5 completed in 245.32s
```

### Final Report
At completion, a detailed report is printed:
```
================================================================================
BACKFILL JOB COMPLETE
================================================================================
Threads processed:    10
Comments processed:   15230
Mentions created:     8945
Mentions updated:     0
LLM calls:            15230
LLM errors:           23
Cache hits:           0
Total duration:       1234.56s
Avg per thread:       123.46s
================================================================================
```

## QA Validation

### CSV Reports
For each thread, a QA CSV is generated in `qa_reports/`:
- `qa_top_weighted_mentions_thread_{id}.csv`
- Contains top 50 highest-weighted mentions
- Fields: comment_id, cast_id, text, sentiment, sarcasm, upvotes, weight, confidence

### Spot Checks
1. Review QA CSVs for accuracy
2. Check sentiment labels match comment tone
3. Verify sarcasm detection on known sarcastic comments
4. Confirm upvote weighting prioritizes community consensus

## Performance

### Expected Throughput
- **LLM calls**: ~10-20 per second (rate limited)
- **Comments**: ~50-100 per minute
- **Thread (1500 comments)**: ~15-30 minutes

### Optimization Tips
1. Increase batch size for faster I/O (up to 500)
2. Run during off-peak hours
3. Use caching to avoid duplicate LLM calls
4. Consider parallel processing for multiple threads

## Error Handling

### LLM Failures
- Retries up to 5 times with exponential backoff
- On final failure, logs error and continues
- Failed comments are skipped (not marked as processed)

### Rate Limiting
- Automatic backoff on 429 errors
- Minimum 0.1s between requests
- Can be adjusted in `llm_service.py`

### Transient Errors
- Network errors trigger automatic retry
- Database errors are logged and re-raised
- State is preserved for resumption

## Cost Estimation

### LLM Costs
Assuming GPT-4 pricing (~$0.03/1K tokens):
- **Per comment**: ~500 tokens = $0.015
- **Per thread (1500 comments)**: ~$22.50
- **10 threads**: ~$225

To minimize costs:
1. Use smaller models for non-critical analysis
2. Batch similar comments together
3. Cache aggressively
4. Run dry-run first to validate

## Validation Criteria

### Acceptance Criteria
✅ 100% of existing Reddit comments processed or marked with clear failure reason
✅ ≥90% of comments that include a cast alias yield a mention
✅ Aggregates populated for every discussion with transcript
✅ Dashboards reflect new metrics without code changes beyond view refresh

### Manual Checks
1. Sample 50 mentions from QA CSV
2. Verify sentiment accuracy (~80%)
3. Check sarcasm detection precision (~70%)
4. Confirm weight calculation: `weight = upvotes * confidence`
5. Validate aggregates match manual calculation

## Troubleshooting

### "No module named 'emoji'"
```bash
pip install emoji
```

### "LLM endpoint unreachable"
Check `LLM_ENDPOINT` and `OPENAI_API_KEY` environment variables

### "Rate limit exceeded"
- Reduce request rate in `llm_service.py`
- Wait and retry
- Check API key quota

### "Database lock error"
- Reduce batch size
- Ensure no other processes are writing to mentions table
- Check database connection pool size

## Next Steps

After successful backfill:
1. Review QA reports in `qa_reports/`
2. Run aggregation job to compute weighted statistics
3. Refresh materialized views (if used)
4. Verify dashboard displays new metrics
5. Monitor LLM accuracy and adjust thresholds as needed

## Support

For issues or questions:
- Check logs in console output
- Review QA CSV files for data quality
- Examine failed mentions in database
- Adjust LLM parameters in environment variables
