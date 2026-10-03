# MoSPI Dhrishti Early-Warning Platform — FastAPI Backend

Backend services for the **AI-Powered Early-Warning and Decision-Support Platform for Government Infrastructure Project Monitoring** (SIH 26103, MoSPI).

---

## 🚀 Quickstart Guide

### Option 1: Docker Compose (Recommended)

The compose stack (`docker-compose.yml` at the repo root) runs **MongoDB 7**, the
**FastAPI backend** (which also serves the built React SPA single-origin), and
**Ollama** for the assistant/RAG:

```bash
docker compose up --build -d
```

- **Web app (SPA + API)**: `http://localhost:8000`
- **Swagger docs**: `http://localhost:8000/docs`
- **MongoDB**: `mongodb://mongo:27017`, database `dhrishti` (internal network)
- **Ollama**: `http://ollama:11434` (internal network)

All data lives in named volumes (`mongo_data`, `data` for SQLite, `uploads`,
`ollama_models`) — nothing is written into the image. On **first boot** the
backend auto-seeds the database from `backend/data/panel_mospi.csv` and trains
the `.joblib` models (`AUTO_SEED_DATABASE=true`), so startup is slow (≈2–4 min);
the healthcheck's `start_period` absorbs this.

After first boot, pull the assistant models once:

```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Chat degrades to its keyword fallback until those models are available.

---

### Option 2: Local Python Environment

1. **Install Dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure Environment (`.env`)**:
   ```bash
   cp .env.example .env
   ```
   *Note: If PostgreSQL is not running locally, the application automatically falls back to local SQLite (`sqlite:///./mospi_ew.db`).*
   For the one-click sample-role accounts on a localhost-only demo, set `AUTH_DEMO_MODE=true` in this local `.env`; leave it `false` for production.

3. **Seed Database & Export Joblib Models**:
   Run the database seeder to populate PostgreSQL/SQLite tables and train/save `.joblib` model artifacts to `backend/models/`:
   ```bash
   python -c "from app.database import engine, Base, SessionLocal; from app.routers.admin import seed_database; Base.metadata.create_all(bind=engine); print(seed_database(SessionLocal()))"
   ```

4. **Start FastAPI Server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

## ☁️ Deploying to a server

1. **Put the repo on the host** (e.g. `git clone https://github.com/vsaurabh10779-ctrl/mospi-early-warning`).
2. **Set secrets** by creating `.env` **next to `docker-compose.yml`** (the repo root — the compose file only interpolates variables from there, not from `backend/.env`):
   ```bash
   # .env (repo root)
   JWT_SECRET=$(openssl rand -hex 32)
   CORS_ORIGINS=https://your-domain.example
   ```
3. **Build and start**:
   ```bash
   docker compose up --build -d
   ```
4. **Verify**:
   ```bash
   curl http://localhost:8000/health
   # {"status":"ONLINE","platform":"MoSPI Dhrishti Early-Warning Backend",...}
   ```
5. **Assistant models (one-time)**:
   ```bash
   docker compose exec ollama ollama pull llama3.2
   docker compose exec ollama ollama pull nomic-embed-text
   ```
6. **Reseed after the panel CSV changes**:
   ```bash
   docker compose exec backend python -c "from app.database import SessionLocal; from app.routers.admin import seed_database; print(seed_database(SessionLocal()))"
   ```
7. **Update to a new version**:
   ```bash
   git pull && docker compose up --build -d
   ```

> Serving on a real domain: put the stack behind a reverse proxy (Caddy/Nginx)
> that terminates TLS and proxies to `127.0.0.1:8000`, set `CORS_ORIGINS` to that
> origin, and keep a strong `JWT_SECRET`. MongoDB and Ollama are not exposed on
> host ports.

### Pairing this API with the Vercel frontend

Deploying only `frontend/` to Vercel does **not** deploy this API, MongoDB, or
Ollama. In that setup `/api/*` resolves to the static frontend, project requests
fall back to sample data, authentication cannot reach its routes, and the local
assistant correctly reports offline. Host the Docker stack on a service that can
run the full container and retain persistent database/model storage, then set
these values:

- Vercel Production: `VITE_API_URL=https://<backend-host>` (API origin only;
  no `/api` suffix or trailing slash), then redeploy the frontend.
- Backend: `FRONTEND_URL=https://sihps-1-f.vercel.app` and
  `CORS_ORIGINS=https://sihps-1-f.vercel.app` (plus any other real frontend
  origins), `GOOGLE_REDIRECT_URI=https://<backend-host>/auth/google/callback`,
  and valid `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` values.
- Google OAuth client: add the exact backend callback URL above as an
  authorized redirect URI.
- Backend: set a unique, strong `JWT_SECRET`, persistent MongoDB and auth
  database configuration, and `OLLAMA_BASE_URL` to the Ollama service address
  on the backend's reachable private network. `localhost` is the backend
  container, not the user's PC or a separate Ollama container.
- Ollama: pull the same models named by `OLLAMA_CHAT_MODEL` and
  `OLLAMA_EMBED_MODEL` in the backend environment.

Keep `AUTH_DEMO_MODE=false` in production. The demo role-login route returns
404 unless explicitly enabled, and Google sign-in returns a clear 503 when its
OAuth credentials are missing; neither path silently issues a fallback session.
Never expose secrets through Vercel `VITE_*` variables.

---

## 📡 API Endpoints Summary

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/projects` | Multi-filtered project list with latest risk score, tier, and trend. |
| `GET` | `/projects/{project_id}` | Full project detail + latest snapshot + top SHAP drivers + suggested review text. |
| `GET` | `/projects/{project_id}/history` | Risk trajectory time-series across all monthly snapshots. |
| `GET` | `/projects/{project_id}/explanation` | SHAP positive risk drivers (increasing) and mitigating factors (decreasing). |
| `GET` | `/projects/{project_id}/similar` | 3–5 nearest-neighbor similar projects based on sector, cost, and duration. |
| `GET` | `/projects/{project_id}/dependencies` | Project cascade graph with current risk status of related projects. |
| `POST` | `/projects/{project_id}/simulate` | **Live What-If Simulator** running real loaded XGBoost models on altered feature vectors. |
| `POST` | `/optimize-queue` | **Live OR-Tools Knapsack Optimizer** prioritizing review queue under officer hour constraints. |
| `GET` | `/alerts` | Projects with increasing risk trends or tier boundary crossings. |
| `GET` | `/model-comparison` | CUF-only vs Enhanced-data model benchmark study metrics. |
| `POST` | `/admin/seed-database` | Internal endpoint to train models, save `.joblib` artifacts, and seed database tables. |

---

## 🧪 Running Automated Tests

Run the backend test suite covering all 11 API endpoints, database seeding, joblib model persistence, and simulation:

```bash
python -m pytest backend/tests/test_api.py -v
```

## MongoDB + MongoDB Compass

Project monitoring data is stored in MongoDB (`MONGO_URI`, default `mongodb://localhost:27017`, database `MONGO_DB`, default `dhrishti`). Start the stack with `docker compose up --build`.

In MongoDB Compass use:

- Local Docker: `mongodb://localhost:27017`
- Database: `dhrishti`
- Expected monitoring collections: `projects`, `snapshots`, `predictions`, `shap_explanations`, `remarks_signals`, `project_dependencies`, `officer_optimization_runs`
- Security collections: `security_logs`, `threat_intelligence`, `blocked_ips`

After `POST /admin/seed-database`, refresh Compass and open `projects`/`predictions` to visually verify seeded documents. `predictions` contain an embedded `shap_explanations` array; the separate `shap_explanations` collection is retained for audit/query compatibility.

## Security Monitoring

The backend includes a defensive IDS under `app/security/`. It inspects every incoming request for NoSQL/SQL injection signatures, path traversal, oversized payloads and common probing paths, applies an in-memory sliding-window rate limiter, and scores request telemetry with a real scikit-learn Isolation Forest. Flagged activity is written to `security_logs` and aggregated in `threat_intelligence`. Repeated violations can automatically add an IP to `blocked_ips` for a configurable TTL (default 24 hours).

Security API endpoints:

- `GET /security/threats?page=1&page_size=20` — risk-sorted flagged IPs
- `GET /security/threats/{ip_address}` — threat record + recent timeline
- `GET /security/blocked-ips` — active blocks
- `POST /security/unblock/{ip_address}` — manual unblock
- `GET /security/logs?flagged=true` — raw audit events

For a localhost-only demo, start the server and run:

```bash
python scripts/simulate_attack.py
```

The script refuses non-localhost targets and sends only clearly malicious test traffic to your own local API. It then prints where to inspect live threat and block records.

### IDS configuration

- `IDS_RATE_LIMIT=300` and `IDS_RATE_WINDOW_SECONDS=60`
- `IDS_BLOCK_THRESHOLD=20`
- `IDS_BLOCK_DURATION_HOURS=24`
- `IDS_ANOMALY_THRESHOLD=85`
- `IDS_IFOREST_ESTIMATORS=120`

No component performs scanning, exploitation, geolocation, identity enrichment, retaliation, or requests to external systems.

## Local project assistant

The compatibility route `POST /groq-chat` now uses the configured local Ollama service. It requires an active bearer-token session. Ministry and agency records are filtered before index construction and checked again before retrieval; viewers receive only the `project_public` projection. The approved index includes project records plus a small curated platform guide; it does not crawl source files or index uploaded content.

Retrieval checks exact project IDs first, then combines BM25 lexical ranking with local Ollama embeddings. If embeddings are unavailable, it falls back to BM25. Generation and embedding requests have independent timeouts. Answers without citations, with unauthorized citations, or with numbers absent from cited records are replaced with a safe decline. Latest project snapshot reporting dates are included in source metadata. Conversation history is accepted only as context and is not used to widen the caller's record scope.

Read-only lookup: `GET /groq-chat/tools/get-project/{project_id}`. It uses the same role filter and returns the same not-found response for missing and unauthorized project IDs. The route name remains stable for clients; the assistant is local Ollama, not Groq.

Pull the local models once with `docker compose exec ollama ollama pull llama3.1` and `docker compose exec ollama ollama pull nomic-embed-text`. Configure `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`, and the request timeout values in the backend environment. Dense retrieval degrades to BM25 when the local embedding model is unavailable; generation degrades to a short unavailable response if the chat model times out.

### Ministry expansion gate

New ministry account scopes are blocked unless `MINISTRY_EXPANSION_ORDER` lists the next ministry in sequence and `PHASE_GATE_EVALUATIONS_JSON` contains that ministry's measured report. Existing ministry scopes are unaffected. The required report fields are `accuracy` (at least 0.90), `safety` (at least 0.95), `p95_latency_seconds` (at most 35), and `cross_role_leaks` (exactly 0). Example:

```json
{"Ministry of Example": {"accuracy": 0.95, "safety": 0.99, "p95_latency_seconds": 12.4, "cross_role_leaks": 0}}
```

Set only the next ministry in the order after it passes the security, accuracy, safety, and latency evaluation suite. Missing or invalid reports keep expansion closed. Each new ministry requires its own report.

Run the assistant guardrail and cross-role integration tests with `pytest tests/test_local_chat_security.py` from `backend/`.
