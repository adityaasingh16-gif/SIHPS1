"""Hermetic test configuration.

The monitoring API reads its project data from MongoDB, and the security tests
written for the IDS layer talk to a live server on localhost:27017. Requiring
a running mongod just to run the suite makes it undeployable in CI and on a
fresh checkout, so we install mongomock's global client patch *before* the app
is imported and point the app at the in-memory server, doing by hand what the
lifespan hook does against a real one.

The patch has to happen before ``app.database`` is imported: that module builds
its ``MongoClient`` at import time, and later imports (``app.main``,
``app.mongo_store``) bind the resulting handle. Importing anything from ``app``
above the patch would bind a real client and every request would then fail to
connect.
"""
import os
import pathlib
import tempfile

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "dhrishti_test")
# The seed tests wipe every project row in the database they run against
# (POST /admin/seed-database deletes then rebuilds all project tables). Point
# the suite at its own throwaway SQLite file so the real backend database is
# never clobbered. Set before app.database is imported (it reads DATABASE_URL
# at import time); absolute path so no CWD anchoring is involved.
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///" + pathlib.Path(tempfile.gettempdir(), "mospi_ew_pytest.db").as_posix(),
)

import mongomock

_mongo_patcher = mongomock.patch(servers=(("localhost", 27017),))
_mongo_patcher.start()

import pytest

from app.database import mongo_db, engine, Base, create_mongo_indexes
from app.main import app
from app.security import middleware as security_middleware
from app.security.rate_limiter import rate_limiter

Base.metadata.create_all(bind=engine)
create_mongo_indexes()
app.state.mongo_db = mongo_db


@pytest.fixture(autouse=True)
def _isolate_ids_state():
    """Reset IDS state between tests.

    The security middleware now runs on every request, so the threat and
    blocklist collections and the rate limiter accumulate across the whole
    suite. A blocked IP from one test would 403 every later one, and a shared
    rate-limit window would 429 them, so each test starts from a clean slate.
    The limit is raised for the general suite; the rate-limit test sets its own.
    """
    for name in ("security_logs", "threat_intelligence", "blocked_ips"):
        mongo_db[name].delete_many({})
    rate_limiter.reset()
    rate_limiter.limit = 10_000_000
    security_middleware._block_cache.clear()
    security_middleware._tele_cache.clear()
    yield
    rate_limiter.reset()
    security_middleware._block_cache.clear()
    security_middleware._tele_cache.clear()
