"""Database connections for the Dhrishti backend.

MongoDB is the source of truth for project monitoring data. A small SQLite
compatibility session is retained for legacy authentication/admin tables while
those auxiliary routes are migrated independently.
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# The backend package root (backend/), used to anchor relative SQLite paths.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _resolve_sqlite_path(url: str) -> str:
    """Anchor a relative SQLite URL to the backend directory.

    SQLAlchemy hands a relative ``sqlite:///mospi_ew.db`` straight to SQLite,
    which resolves it against the *process working directory*. Launching pytest
    or uvicorn from the repo root therefore creates a 0-byte database there and
    every query fails with "no such table: projects" -- silently, and with the
    real data still intact but unused. Anchoring to the backend directory makes
    the URL independent of where the command was invoked from.

    Absolute paths, ``:memory:`` and non-SQLite URLs are returned unchanged, and
    any query string (``?mode=ro``) is preserved.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    rest = url[len(prefix):]
    path, sep, query = rest.partition("?")
    if not path or path == ":memory:" or os.path.isabs(path):
        return url
    return prefix + os.path.join(_BACKEND_ROOT, *path.split("/")) + sep + query


# Read DATABASE_URL from environment; default to SQLite fallback using absolute path
_default_db = os.path.join(_BACKEND_ROOT, "mospi_ew.db")
DATABASE_URL = _resolve_sqlite_path(os.getenv("DATABASE_URL", f"sqlite:///{_default_db}"))

# SQLAlchemy connection arguments
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "dhrishti")
_mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=int(os.getenv("MONGO_SERVER_TIMEOUT_MS", "3000")))
mongo_db = _mongo_client[MONGO_DB]

class DatabaseHandle:
    """Hybrid dependency: Mongo for monitoring data, SQL compatibility for legacy auth."""
    def __init__(self, sql_session):
        self.sql = sql_session
        self.mongo = mongo_db

    def __getattr__(self, name):
        return getattr(self.sql, name)


def get_db():
    db = SessionLocal()
    try:
        yield DatabaseHandle(db)
    finally:
        db.close()


def mongo_ping() -> bool:
    try:
        _mongo_client.admin.command("ping")
        return True
    except Exception:
        return False


def create_mongo_indexes():
    """Create the indexes required by the monitoring/security layer."""
    for name in ("projects", "snapshots", "predictions", "shap_explanations", "remarks_signals", "project_dependencies", "officer_optimization_runs"):
        mongo_db[name].create_index("project_id")
    mongo_db["snapshots"].create_index([("project_id", 1), ("snapshot_month", 1)], unique=True)
    mongo_db["predictions"].create_index([("project_id", 1), ("snapshot_month", 1)], unique=True)
    mongo_db["project_dependencies"].create_index([("project_id", 1), ("related_project_id", 1)], unique=True)
