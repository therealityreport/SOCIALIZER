# SOCIALIZER User Guide (MVP)

## 1. Overview

SOCIALIZER tracks live Reddit discussion for Bravo programming, summarising sentiment per cast member and exporting analytics for producers. This guide walks through the MVP workflow end-to-end.

## 2. Prerequisites

- Backend API running at `http://localhost:8000` (via `uvicorn app.main:app --reload`).
- Frontend dev server running at `http://localhost:5173` (`npm run dev` from `src/frontend`).
- Auth0 configuration is optional for MVP; unauthenticated usage is enabled for internal testing.

## 3. Sign In (Optional)

- Click **Sign in** in the header if Auth0 is configured. After login you are returned to the dashboard.
- Without Auth0 configured the app defaults to an authenticated state for internal evaluation.

## 4. Track a New Thread

1. Open the dashboard.
2. Paste a Reddit discussion link into **Thread URL**. The app auto-detects the subreddit, reddit id, and a fallback title.
3. (Optional) Adjust the episode title, air time (UTC), or synopsis.
4. Submit. A success notice confirms ingestion has been queued.

Behind the scenes the backend stores the thread, triggers ingestion, and background workers populate mention aggregates.

## 5. Review Episode Analytics

1. Select an episode from the dashboard card grid (or head directly to `/threads/{id}`).
2. The thread detail page highlights:
   - Episode metadata & synopsis.
   - Top-line metrics (mentions, sentiment, total comments).
   - Time window summary (Live, Day-Of, After).
   - Cast grid with share of voice and quick sentiment cues.
3. Click **Dive deeper** on a cast card to inspect long-tail metrics (time windows, mention counts, historical comparisons).

## 6. Export Data

1. On the thread detail page, open **Export analytics**.
2. Choose CSV or JSON. The export is generated immediately using current aggregates.
3. The download endpoint streams the file with a timestamped filename. Recent exports are listed for convenience.

## 7. Tips & Troubleshooting

- **Stale Data:** The dashboard refreshes automatically via React Query; use the **Export** panel to regenerate snapshots as needed.
- **Thread Ingestion:** Ensure Celery workers & Redis are running for real-time updates. The UI will still display seeded demo aggregates if background workers are offline.
- **Auth:** If Auth0 credentials are missing, login prompts redirect to a friendly message. Populate `.env` with `VITE_AUTH0_*` and backend `AUTH0_*` values to enable secure mode.
- **API Docs:** Visit `http://localhost:8000/docs` for interactive Swagger documentation.

## 8. Next Steps

- Collect internal feedback during the MVP demo.
- Prioritise unit/integration testing, documentation polish, and staging deployment ahead of V1 features.
