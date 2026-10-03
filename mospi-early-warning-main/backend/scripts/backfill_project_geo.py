"""Populate `project_geo` from the panel CSV, without re-seeding anything else.

The seeder in `app/routers/admin.py` already writes this table, but running it
regenerates every snapshot, prediction and SHAP row and re-runs the ML
pipeline. That is a destructive way to recover one column. This script only
touches `project_geo`, is safe to re-run, and leaves the rest of the database
byte-for-byte alone.

    python backend/scripts/backfill_project_geo.py --dry-run
    python backend/scripts/backfill_project_geo.py

`--dry-run` reports what would be written without writing it.
"""

import argparse
import os
import shutil
import sys
import tempfile
from collections import Counter

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import DATABASE_URL, Base  # noqa: E402
from app import models  # noqa: E402
from app.geo import (  # noqa: E402
    coordinates_for,
    code_for,
    is_mappable,
    multi_state_members,
    normalise_state,
)

PANEL_CSV = os.getenv(
    "PANEL_CSV",
    os.path.abspath(os.path.join(BACKEND_DIR, "data", "panel_mospi.csv")),
)


def resolve_database_url(url: str) -> str:
    """Anchor a relative SQLite path to the backend directory.

    `.env` pins `DATABASE_URL=sqlite:///mospi_ew.db`, which SQLAlchemy
    resolves against the *current working directory*. Run from `backend/` that
    is the real database, but from any other directory it is a different file,
    and this script would populate a stray empty database while appearing to
    succeed. Anchoring to the backend directory makes the target explicit and
    identical from any working directory.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix):]
    if os.path.isabs(path) or path == ":memory:":
        return url
    return prefix + os.path.abspath(os.path.join(BACKEND_DIR, path))


DB_URL = resolve_database_url(DATABASE_URL)

# Built from the anchored URL, not `app.database.engine`, which is bound to
# the raw CWD-relative path at import time.
_engine = create_engine(
    DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def build_rows():
    """One ProjectGeo-shaped dict per project, from the CSV's first row."""
    panel = pd.read_csv(PANEL_CSV)
    panel = panel.dropna(subset=["project_code", "ministry"])
    panel = panel.sort_values(["project_code", "snapshot_full"])

    rows = {}
    for p_id, p_rows in panel.groupby("project_code"):
        first = p_rows.iloc[0]
        state = normalise_state(first.get("state"))
        lat, lon = coordinates_for(state) if is_mappable(state) else (None, None)
        rows[str(p_id)] = {
            "project_id": str(p_id),
            "state": state,
            "state_code": code_for(state),
            "lat": lat,
            "lon": lon,
            "precision": "state" if lat is not None else "none",
            "member_count": len(multi_state_members(first.get("state"))) or None,
            "geo_source": "panel_csv",
        }
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    if not os.path.exists(PANEL_CSV):
        sys.exit(f"panel CSV not found: {PANEL_CSV}")

    if DB_URL != DATABASE_URL:
        print(f"note     : relative DATABASE_URL anchored to backend dir "
              f"(was {DATABASE_URL!r})")

    db_path = DB_URL.replace("sqlite:///", "")
    if DB_URL.startswith("sqlite") and not os.path.exists(db_path):
        sys.exit(
            f"refusing to create a new database at {db_path}.\n"
            "This script populates an existing deployment; if you meant to "
            "start one, seed it with POST /admin/seed first."
        )

    print(f"database : {DB_URL}")
    print(f"panel    : {PANEL_CSV}")

    rows = build_rows()
    states = Counter(r["state"] for r in rows.values())
    mappable = {k: v for k, v in states.items() if is_mappable(k)}
    buckets = {k: v for k, v in states.items() if not is_mappable(k)}

    total = len(rows)
    print(f"projects : {total}")
    print(f"  on a choropleth  : {sum(mappable.values())} across {len(mappable)} states")
    for name, n in sorted(mappable.items(), key=lambda kv: -kv[1]):
        print(f"      {name:<42} {n:>5}")
    print(f"  unplaced buckets : {sum(buckets.values())}")
    for name, n in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"      {name:<42} {n:>5}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    # Only ever additive: creates project_geo if absent, never alters other tables.
    Base.metadata.create_all(_engine, tables=[models.ProjectGeo.__table__])

    # Back up before the first real write, so a bad run is recoverable.
    if DB_URL.startswith("sqlite") and os.path.exists(db_path):
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(db_path, tmp)
        print(f"\nbackup   : {tmp}")

    db = Session()
    try:
        existing = {pid for (pid,) in db.execute(text("SELECT project_id FROM project_geo"))}
        for row in rows.values():
            if row["project_id"] in existing:
                continue
            db.execute(
                text(
                    "INSERT INTO project_geo "
                    "(project_id, state, state_code, lat, lon, precision, "
                    "member_count, geo_source) "
                    "VALUES (:project_id, :state, :state_code, :lat, :lon, "
                    ":precision, :member_count, :geo_source)"
                ),
                row,
            )
        db.commit()
        total_rows = db.execute(text("SELECT COUNT(*) FROM project_geo")).scalar()
        with_coords = db.execute(
            text("SELECT COUNT(*) FROM project_geo WHERE lat IS NOT NULL")
        ).scalar()
        print(f"\nwrote    : {len(rows) - len(existing)} new rows "
              f"({len(existing)} already present)")
        print(f"verify   : project_geo now has {total_rows} rows, "
              f"{with_coords} with coordinates")
    finally:
        db.close()


if __name__ == "__main__":
    main()
