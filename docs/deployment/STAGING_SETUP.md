# Staging Deployment Guide

This document outlines how to promote the SOCIALIZER stack from local development to a TLS-enabled staging environment with basic observability.

## Prerequisites
- A Linux host (x86_64) with Docker Engine 24+ and Docker Compose v2.
- DNS A records for the following hostnames pointing at the staging server:
  - `APP_HOST` (e.g., `staging.socializer.app`)
  - `API_HOST` (e.g., `api.staging.socializer.app`)
  - `FLOWER_HOST` (optional, e.g., `flower.staging.socializer.app`)
  - `ML_HOST` (optional, e.g., `ml.staging.socializer.app`)
- Valid secrets for the staging `.env` file (Auth0, Reddit, database, S3, etc.) and the `config/environments/staging.env` template updated with the correct values.
- Optional: Sentry DSN and Datadog API/app keys if you plan to forward metrics and traces.

## 1. Build images for staging
```bash
docker compose build backend worker ml-inference frontend
```

The staging override removes live code mounts, so rebuild the images whenever you promote new commits.

## 2. Configure environment variables
1. Review `config/environments/staging.env` and ensure keys like `ML_INFERENCE_URL`, `THREAD_ARCHIVE_IDLE_MINUTES`, and Auth0 credentials are correct.
2. Populate `.env` (not checked into source control) with secrets that are only available at runtime (database password, AWS keys, Auth0 secrets, etc.).
3. Export the reverse proxy variables before launching:
   ```bash
   export LETSENCRYPT_EMAIL=ops@socializer.app
   export APP_HOST=staging.socializer.app
   export API_HOST=api.staging.socializer.app
   export FLOWER_HOST=flower.staging.socializer.app
   export ML_HOST=ml.staging.socializer.app
   ```
   Caddy uses these values to request certificates and route traffic. If you do not want Caddy to request certificates, keep the hosts on a private TLD (e.g., `*.test`) and supply a dummy email.

## 3. Launch the staging stack
Start the full stack (including the HTTPS reverse proxy) with:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

The override file:
- Runs the backend without auto-reload.
- Switches services to the `staging.env` configuration.
- Serves the front-end via `npm run preview` on port `4173`.
- Adds a `caddy` reverse proxy that terminates TLS on ports 80/443.

Verify container health:
```bash
docker compose ps
docker compose logs reverse-proxy
```

## 4. Database migrations
Run migrations inside the backend container:
```bash
docker compose exec backend alembic upgrade head
```

## 5. Observability options
- **Flower**: available at `https://$FLOWER_HOST/` when the hostname is configured. Lock it down behind VPN or basic auth at the proxy layer.
- **Sentry**: set `SENTRY_DSN` and `SENTRY_TRACES_SAMPLE_RATE` in `staging.env`.
- **Datadog**: set `DATADOG_API_KEY`, `DATADOG_APP_KEY`, and `DATADOG_ENV`. Deploy the Datadog agent alongside the stack (outside this Compose file) to collect metrics and traces.
- **Health checks**: Caddy exposes `/health` for the backend (`/health` endpoint) and the ML service (`/health`). Integrate these URLs with your external monitoring provider (e.g., UptimeRobot, Pingdom).

## 6. HTTPS certificate management
Caddy automatically provisions and renews certificates via Let's Encrypt using the email supplied in `LETSENCRYPT_EMAIL`. Certificates are persisted in the `caddy_data` volume. Ensure ports 80/443 are reachable from the public internet during issuance.

## 7. Rolling updates
To deploy a new build:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml pull
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d backend frontend worker ml-inference
```

## 8. Teardown
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml down
```
This keeps named volumes (`postgres_data`, `redis_data`, `caddy_data`, `caddy_config`) so you can restart later.

Refer to `docs/SOLUTION_ARCHITECTURE.md` for a deeper view of the production topology once you graduate past staging.
