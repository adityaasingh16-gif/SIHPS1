"""
Main FastAPI Application Entrypoint for MoSPI Dhrishti Early-Warning & Decision-Support Core.
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# Ensure backend directory is on sys.path so src imports succeed
PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

load_dotenv()

from .database import engine, Base, SessionLocal, mongo_db, MONGO_URI, mongo_ping, create_mongo_indexes
from .ml_loader import ml_registry
from .routers import projects, simulate, optimize, alerts, comparison, admin, auth, admin_users, admin_ops, ministry, agency, public, graph, mongo, reports, risk, security, groq_chat
from .bootstrap import bootstrap
from .risk_sync import start_background_sync
from .security.middleware import SecurityMonitoringMiddleware
from .security.anomaly_detector import anomaly_detector


def _frontend_dist() -> str:
    """Directory holding a production build of the React SPA, if one exists."""
    return os.getenv("FRONTEND_DIST") or os.path.abspath(
        os.path.join(PARENT_DIR, "..", "frontend", "dist")
    )


def _auto_seed_real_if_empty() -> bool:
    """First-boot convenience (AUTO_SEED_DATABASE=true): train on the real MoSPI
    panel and seed the empty database, mirroring what POST /admin/seed-database
    does by hand. Idempotent: never touches a database that already has rows."""
    flag = os.getenv("AUTO_SEED_DATABASE", "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    from . import models

    with SessionLocal() as db:
        if db.query(models.Project).count() > 0:
            print("  AUTO_SEED_DATABASE=true but projects table is not empty; skipping.")
            return False
    print("  AUTO_SEED_DATABASE=true: training on the real MoSPI panel and seeding (first boot)...")
    from .routers.admin import _mirror_to_mongo, _seed_real_database

    with SessionLocal() as db:
        info = _seed_real_database(db)
        warning = _mirror_to_mongo(db)
    print(
        f"  AUTO_SEED_DATABASE: seeded {info['n_projects']} projects, "
        f"{info['n_snapshots']} snapshots, {info['n_predictions']} predictions, "
        f"{info['n_shap']} SHAP.{warning}"
    )
    return True


def _health_payload() -> dict:
    return {
        "status": "ONLINE",
        "platform": "MoSPI Dhrishti Early-Warning Backend",
        "version": "1.0.0",
        "models_loaded": ml_registry.is_loaded,
        "docs_url": "/docs",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup model loading and database initialization."""
    print("=" * 80)
    print("  Starting MoSPI Dhrishti Early-Warning FastAPI Backend...")
    print("=" * 80)
    
    # MongoDB is the source of truth for project monitoring + security telemetry.
    # Probe first: a missing Mongo must not stop the portal from starting. When
    # it is unreachable the IDS is left disabled (see SecurityMonitoringMiddleware
    # for the same guard on the request path) rather than taking the API down
    # with it.
    if mongo_ping():
        create_mongo_indexes()
        app.state.mongo_db = mongo_db
        anomaly_detector.fit_baseline()
        print("  MongoDB collections/indexes initialized.")
    else:
        print(f"  MongoDB unreachable at {MONGO_URI}; IDS telemetry disabled and Mongo-backed "
              f"endpoints (/projects, /alerts, ...) will fail until it is reachable.")

    # Legacy auth/admin tables remain in the local compatibility database until their dedicated migration.
    Base.metadata.create_all(bind=engine)
    print("  Compatibility tables initialized.")

    # Bootstrap auth + public-safe dataset (idempotent)
    with SessionLocal() as seed_db:
        info = bootstrap(seed_db)
        print(f"  Auth bootstrap: public rows={info['public_rows']}, demo users={info['demo_users']}.")

    # First-boot convenience: seed real data when the database is empty. Runs
    # before model loading so the freshly trained artifacts are picked up.
    _auto_seed_real_if_empty()

    # Load joblib model artifacts
    loaded = ml_registry.load_models()
    if loaded:
        print("  ML Model Registry: Pre-trained joblib models loaded successfully into memory.")
    else:
        print("  ML Model Registry Warning: Joblib models not found. Trigger POST /admin/seed-database to seed DB and export models.")

    # Start live rolling risk-sync (first pass immediately, then every 5 min)
    start_background_sync()
    print("  Live Risk Sync: background sync thread started (every 300s).")

    yield
    print("  Shutting down MoSPI Dhrishti Backend.")

app = FastAPI(
    title="MoSPI Dhrishti Early-Warning & Decision-Support API",
    description="API server for Central Sector Infrastructure Monitoring (SIH Problem Statement 26103)",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS middleware securely (CWE-942 prevention: credentials only when origins are explicit)
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173")
origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
is_wildcard = not origins or "*" in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# gzip compression on all API responses (client must send Accept-Encoding: gzip)
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=5)

# Defensive IDS: outermost middleware so blocked IPs are rejected before route handling.
app.add_middleware(SecurityMonitoringMiddleware)

# Same-origin production support: the Vite dev server exposes the API under
# /api via a proxy rewrite; mirror that here so a statically-built SPA calling
# `API_BASE="/api"` works against this process directly, with no reverse proxy.
# Added last so it runs before every other middleware.
class APIPrefixStripMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.scope.get("path", "")
        if path == "/api" or path.startswith("/api/"):
            request.scope["path"] = "/" + path[len("/api"):].lstrip("/")
        return await call_next(request)

app.add_middleware(APIPrefixStripMiddleware)

@app.get("/", tags=["Health"])
def root_health_check(request: Request):
    """Serves the SPA for browsers at the site root, otherwise health JSON.

    A browser navigation sends `Accept: text/html,...` and gets the app;
    `fetch("/")` (health check) and curl send `Accept: */*` and get JSON, so
    the two consumers of the root never fight over the same response."""
    dist = _frontend_dist()
    if os.path.isdir(dist) and "text/html" in request.headers.get("accept", ""):
        return FileResponse(os.path.join(dist, "index.html"))
    return _health_payload()

@app.get("/health", tags=["Health"])
def health_check():
    """Plain-JSON health probe for load balancers / uptime monitors."""
    return _health_payload()

# Include API Routers
app.include_router(projects.router)
app.include_router(simulate.router)
app.include_router(optimize.router)
app.include_router(alerts.router)
app.include_router(comparison.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_ops.router)
app.include_router(ministry.router)
app.include_router(agency.router)
app.include_router(public.router)
app.include_router(graph.router)
app.include_router(mongo.router)
app.include_router(reports.router)
app.include_router(risk.router)
app.include_router(security.router)
app.include_router(groq_chat.router)


def _register_spa_routes(app: FastAPI) -> None:
    """Serve the built React SPA single-origin from this API process.

    Only acts when a build directory exists (a Docker deploy ships one). No-op
    for a bare API deployment. Registered after every API router so concrete
    routes always win; the catch-all only claims GETs (SPA navigation + static
    assets) and returns index.html to support client-side routing.
    """
    dist = _frontend_dist()
    if not os.path.isdir(dist):
        return
    assets_dir = os.path.abspath(os.path.join(dist, "assets"))
    index_file = os.path.join(dist, "index.html")
    dist_root = os.path.abspath(dist)

    @app.get("/assets/{path:path}", include_in_schema=False)
    async def spa_assets(path: str):
        # Asset filenames carry a content hash, so browsers may cache them forever.
        candidate = os.path.abspath(os.path.join(assets_dir, path))
        if candidate.startswith(assets_dir + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate, headers={"Cache-Control": "public, max-age=31536000, immutable"})
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        if path:
            candidate = os.path.abspath(os.path.join(dist, path))
            if candidate.startswith(dist_root + os.sep) and os.path.isfile(candidate):
                return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    print(f"  SPA serving enabled (FRONTEND_DIST={dist}): single-origin UI available at /.")


_register_spa_routes(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
