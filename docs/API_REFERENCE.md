# SOCIALIZER API Reference

This document summarizes the primary REST endpoints exposed by the SOCIALIZER backend for the MVP release. All paths below are prefixed with `/api/v1` unless noted otherwise.

## Threads

### POST `/threads`
- **Purpose:** Register a Reddit live thread for analysis.
- **Request Body:**
  ```json
  {
    "reddit_id": "abc123",
    "subreddit": "bravo",
    "title": "Episode Premiere",
    "url": "https://www.reddit.com/r/bravo/comments/abc123/episode_premiere",
    "air_time_utc": "2024-01-01T01:00:00Z",
    "created_utc": "2024-01-01T00:00:00Z",
    "status": "scheduled",
    "total_comments": 0,
    "synopsis": null
  }
  ```
- **Responses:**
  - `201 Created` with full `ThreadRead` payload (includes database id and timestamps).
  - `400 Bad Request` if the Reddit id already exists.

### GET `/threads`
- **Purpose:** List threads ordered by newest first.
- **Query Params:** `skip` (default `0`), `limit` (default `50`, max `200`).
- **Response:** Array of `ThreadRead` items.

### GET `/threads/{id}`
- **Purpose:** Fetch a specific thread by internal id.
- **Response:** `ThreadRead` or `404` if the thread does not exist.

### DELETE `/threads/{id}`
- **Purpose:** Remove a thread and associated aggregates/comments.
- **Response:** `204 No Content` or `404` if missing.

## Cast Analytics

### GET `/threads/{id}/cast`
- **Purpose:** Return per-cast analytics for a thread (overall & time-window metrics).
- **Response:**
  ```json
  {
    "thread": { "id": 1, "reddit_id": "abc123", ... },
    "cast": [
      {
        "cast_slug": "jane-doe",
        "share_of_voice": 0.42,
        "overall": { "mention_count": 40, "net_sentiment": 0.2, ... },
        "time_windows": { "live": { ... }, "day_of": { ... } },
        "sentiment_shifts": {"day_of_vs_live": -0.1}
      }
    ],
    "total_mentions": 40
  }
  ```

### GET `/threads/{id}/cast/{cast_slug}`
- **Purpose:** Retrieve analytics for a single cast member within a thread.
- **Response:** `CastAnalytics` payload or `404` if not found.

### GET `/episode-discussions/{id}/mentions`
- **Purpose:** Retrieve detailed mention data including LLM-analyzed sentiment and computed signal fields.
- **Response:**
  ```json
  {
    "mentions": [
      {
        "id": 123,
        "comment_id": 456,
        "cast_member": "jane-doe",
        "sentiment_primary": "POSITIVE",
        "sentiment_secondary": "Admiration/Support",
        "emotions": [
          {"label": "joy", "score": 0.87},
          {"label": "amusement", "score": 0.65}
        ],
        "sarcasm_score": 0.42,
        "sarcasm_label": "not_sarcastic",
        "sarcasm_evidence": null,
        "emoji_count": 2,
        "has_gif": false,
        "has_image": true,
        "has_video": false,
        "domains": ["imgur.com"],
        "hashtag_count": 1,
        "all_caps_ratio": 0.05,
        "punctuation_intensity": 0.12,
        "negation_count": 0,
        "question": false,
        "toxicity": 0.08,
        "depth": 2,
        "replies": 5,
        "awards": 1,
        "velocity": 5.6,
        "controversy": 0.27,
        "weight_upvotes": 114,
        "cast_ids": ["jane-doe"],
        "created_utc": 1609459200,
        "text": "She absolutely killed it! 😍"
      }
    ],
    "total": 150,
    "page": 1,
    "page_size": 50
  }
  ```

**Signal Field Definitions**:
- **LLM-Analyzed Fields**:
  - `sentiment_primary`: Positive, Neutral, or Negative
  - `sentiment_secondary`: Fine-grained attitude (Admiration/Support, Shady/Humor, Analytical, Annoyed, Hatred/Disgust, Sadness/Sympathy/Distress)
  - `emotions`: Array of emotion labels and confidence scores
  - `sarcasm_score`: 0.0-1.0 sarcasm probability
  - `sarcasm_label`: "sarcastic" or "not_sarcastic"
  - `sarcasm_evidence`: Text snippet supporting sarcasm detection

- **Computed Signal Fields**:
  - `emoji_count`: Number of emojis in comment
  - `has_gif`: Boolean indicating GIF presence
  - `has_image`: Boolean indicating image URL presence
  - `has_video`: Boolean indicating video URL presence
  - `domains`: Array of external domains linked in comment
  - `hashtag_count`: Number of hashtags
  - `all_caps_ratio`: Proportion of text in ALL-CAPS
  - `punctuation_intensity`: Exclamation/question mark density
  - `negation_count`: Number of negation words
  - `question`: Boolean indicating question form
  - `toxicity`: 0.0-1.0 toxicity score
  - `depth`: Comment thread depth (replies to replies)
  - `replies`: Number of direct replies
  - `awards`: Number of Reddit awards received
  - `velocity`: Comments per hour rate
  - `controversy`: Vote disagreement metric (0.0-1.0)
  - `weight_upvotes`: Upvote count used for weighting
  - `cast_ids`: Array of cast member slugs mentioned

### GET `/cast/{cast_slug}/history`
- **Purpose:** Cross-thread history for a cast member.
- **Response:** Contains cast metadata plus an array of thread entries (`overall` + window metrics).

## Exports

### POST `/exports/csv`
### POST `/exports/json`
- **Purpose:** Queue an export for a thread in CSV or JSON format.
- **Request Body:** `{ "thread_id": 1 }`
- **Response:** `201 Created` with basic export metadata (`id`, `filename`, `created_at`).

### GET `/exports/{id}`
- **Purpose:** Download an export; `Content-Type` is `text/csv` or `application/json`.
- **Response:** Streaming payload with `Content-Disposition` download header or `404`.

## Instagram Ingest

### POST `/ingest/instagram/profiles`
- **Purpose:** Call Apify's `instagram-profile-scraper`, filter posts by date/tags/engagement, and optionally persist the normalized posts.
- **Request Body:**
  ```json
  {
    "usernames": ["BravoTV"],
    "startDate": "2025-09-01",
    "endDate": "2025-11-07",
    "includeTags": ["bravo"],
    "excludeTags": [],
    "minLikes": 25,
    "minComments": 5,
    "maxPostsPerUsername": 500,
    "includeAbout": false,
    "dryRun": true
  }
  ```
- **Response:**
  ```json
  {
    "actor": {
      "runId": "abc123",
      "startedAt": "2025-11-07T16:04:00Z",
      "finishedAt": "2025-11-07T16:06:00Z",
      "status": "SUCCEEDED"
    },
    "perUsername": {
      "BravoTV": {
        "fetched": 120,
        "kept": 12,
        "skipped": {
          "date": 40,
          "inc_tag": 30,
          "exc_tag": 5,
          "likes": 10,
          "comments": 5,
          "private": 20,
          "other": 0
        }
      }
    },
    "itemsKept": 12
  }
  ```
- **Notes:** Requires `APIFY_TOKEN`. When `dryRun=false`, the backend upserts `instagram_profiles`, `instagram_posts`, `instagram_post_hashtags`, and records a row in `instagram_runs`.

## Health

- **GET `/healthz`** — Simple liveness check (`{"status":"ok"}`).
- **GET `/api/v1/health`** — API health endpoint (same payload; honouring API prefix).

## Authentication & Headers

- All endpoints accept JSON bodies and return JSON unless downloading an export.
- Auth is planned via Auth0 bearer tokens; for MVP the endpoints above are currently unauthenticated to simplify internal testing. When Auth0 is enabled, supply `Authorization: Bearer <token>`.

## Error Shape

Errors follow FastAPI defaults:

```json
{
  "detail": "Thread not found."
}
```

Validation problems return a list in `detail` describing field validation issues.

## Status Codes Overview

| Endpoint                          | Success | Notable Errors                   |
|-----------------------------------|---------|----------------------------------|
| `POST /threads`                   | 201     | 400 duplicate reddit id          |
| `GET /threads` / `{id}`           | 200     | 404 unknown thread               |
| `DELETE /threads/{id}`            | 204     | 404 unknown thread               |
| `GET /threads/{id}/cast`          | 200     | 404 thread missing               |
| `GET /cast/{slug}/history`        | 200     | 404 cast missing                 |
| `POST /exports/{csv,json}`        | 201     | 404 thread missing               |
| `GET /exports/{id}`               | 200     | 404 export missing               |
| `POST /ingest/instagram/profiles` | 200     | 400 validation, 502 actor error  |
| `/healthz`, `/api/v1/health`      | 200     | —                                |

This reference should be kept in sync with the OpenAPI schema at `/docs` once staging is live.
