# MVP Demo & Staging Release Checklist

## Objectives
- Demonstrate end-to-end Reddit analytics workflow to internal stakeholders.
- Deploy the MVP stack to staging for alpha testing by 5 internal users.

## Pre-Demo Preparation
- [ ] Refresh sample database with recent Bravo episodes.
- [ ] Seed cast photos/profile data for improved visuals (optional for demo).
- [ ] Verify background services:
  - Redis running.
  - Celery worker processing aggregates successfully.
  - ML inference service reachable (health endpoint).
- [ ] Run regression suite:
  - `npm run lint`, `npm run test`, `npm run build`.
  - `pytest` (full backend suite).

## Demo Flow Outline (≈15 minutes)
1. **Intro & Goals** — what sentiment questions we answer.
2. **Thread creation** — show URL submission + success toast.
3. **Dashboard overview** — highlight live metrics, cast grid, drill-down links.
4. **Cast deep dive** — walk through sentiment shifts & history table.
5. **Export workflow** — generate CSV, download, open in spreadsheet.
6. **Q&A** — capture feedback for V1 planning.

## Staging Release Tasks
- [ ] Create staging environment variables (.env.staging) and Auth0 application.
- [ ] Build & push backend Docker image.
- [ ] Apply database migrations on staging Postgres.
- [ ] Deploy infrastructure (API, workers, frontend) via the chosen platform.
- [ ] Smoke test staging endpoints and UI.

## Alpha Testing
- [ ] Invite 5 internal users, provide onboarding quick-start (link to user guide).
- [ ] Enable telemetry/logging to capture usage & errors.
- [ ] Schedule feedback session after 1 week to inform V1 backlog.

Document completion status in `docs/MasterTaskList.md` once each checklist section is complete.
