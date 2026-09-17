# EQIP — Enterprise Quality Intelligence Platform

EQIP is a governed quality-workflow foundation for enterprise engineering teams. This increment provides a Vite/React dashboard and FastAPI API for registering scoped applications, transitioning demands with optimistic concurrency, and calculating explainable release-readiness snapshots.

## Delivered workflows

- **Governed portfolio** — create and list actor-scoped applications with real MongoDB persistence and immutable audit records.
- **Demand workflow** — transition an owned demand through allowed states, enforcing current versions and terminal resolution notes.
- **Release readiness** — persist an explainable weighted score from gates, tests, defects, and automation; unwaived gate failures produce `Blocked`.
- **Safety controls** — strict request validation, actor-scoped reads/writes, 401/403/404/409/422 API behavior, safe resource IDs, and audit evidence.

## Architecture

- `frontend/` — Vite, React 18, TypeScript, Vitest, Playwright.
- `backend/` — FastAPI, Pydantic v2, PyMongo async driver.
- MongoDB — durable system of record for applications, demands, readiness snapshots, and audits.
- Redis — provisioned in Compose for the planned worker/cache plane.
- `docker-compose.yml` — frontend, backend, MongoDB, and Redis topology.

All business routes use `/api/v1`; process liveness is `GET /api/health`.

## Run locally

### Prerequisites

- Python 3.11+ (the sandbox was verified with Python 3.14)
- Node.js 20+
- MongoDB running on `127.0.0.1:27017`

### Backend

```bash
cd backend
python3 -m venv --copies "$HOME/venvs/eqip"
"$HOME/venvs/eqip/bin/pip" install -r requirements.txt
export MONGODB_URI=mongodb://127.0.0.1:27017
export MONGODB_DB=eqip
export AUTH_MODE=development
export DEVELOPMENT_USER_ID=local-user
export CORS_ORIGINS=http://127.0.0.1:5173
PYTHONPATH=. "$HOME/venvs/eqip/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install --no-bin-links
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
```

The Vite development proxy forwards `/api` to the backend. The shipped client uses same-origin API paths rather than a hardcoded backend URL.

### Containers

```bash
docker compose up --build -d
```

The frontend is available at `http://localhost:8080`; the backend is available at `http://localhost:8000/api/health`. MongoDB and Redis remain internal Compose services.

## Verification

```bash
# Real-Mongo API and integration suite
cd backend && MONGODB_URI=mongodb://127.0.0.1:27017 PYTHONPATH=. "$HOME/venvs/eqip/bin/python" -m pytest tests -q

# Frontend components
cd frontend && node node_modules/vitest/vitest.mjs run --environment jsdom

# Production bundle
cd frontend && node node_modules/vite/bin/vite.js build

# Browser journeys (when Playwright Chromium is available)
cd frontend && node node_modules/@playwright/test/cli.js test --config playwright.config.ts
```

In the sandbox, Playwright’s managed Chromium installer does not support Ubuntu 26.04. E2E was verified with an official Chrome-for-Testing binary using `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.

## Security and development identity

`AUTH_MODE=development` supplies a constrained local identity for developer workflows and tests. Production mode deliberately rejects protected calls until an OIDC adapter is configured. Do not use development identity mode in production.

## License

This project is private and proprietary.
