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
| `/healthz`, `/api/v1/health`      | 200     | —                                |

This reference should be kept in sync with the OpenAPI schema at `/docs` once staging is live.
