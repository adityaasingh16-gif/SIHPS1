"""
Startup bootstrap: seeds public-safe dataset projection, default admin, and
a handful of demo users (in AUTH_DEMO_MODE) so all role dashboards are testable.
"""

import os
from datetime import datetime, timezone
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from . import models
from .auth_security import AUTH_DEMO_MODE, AUTH_SEED_ADMIN, seed_default_admin, log_audit, hash_password


def ensure_auth_columns(db: Session) -> None:
    """Lightweight migration: add auth columns to the users table if missing."""
    cols = {row[1] for row in db.execute(text("PRAGMA table_info(users)")).fetchall()}
    if "password_hash" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
    if "password_must_change" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN password_must_change INTEGER NOT NULL DEFAULT 0"))
    if "failed_attempts" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"))
    if "account_locked_until" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN account_locked_until DATETIME"))
    db.commit()

DEMO_USERS = [
    {
        "email": "ministry@gov.in",
        "name": "MoRTH Ministry Officer",
        "role": "ministry",
        "ministry": "Ministry of Road Transport & Highways",
        "agency": None,
        "project_id": None,
    },
    {
        "email": "contractor@gov.in",
        "name": "NHAI Project Contractor",
        "role": "agency",
        "ministry": None,
        "agency": "National Highways Authority of India [NHAI]",
        "project_id": "701392",
    },
    {
        "email": "agency@gov.in",
        "name": "NHAI Implementing Agency Cell",
        "role": "agency",
        "ministry": None,
        "agency": "National Highways Authority of India [NHAI]",
        "project_id": "701392",
    },
    {
        "email": "citizen@gov.in",
        "name": "Citizen / Public Analyst",
        "role": "viewer",
        "ministry": None,
        "agency": None,
        "project_id": None,
    },
    {
        "email": os.getenv("DEMO_MINISTRY_EMAIL", "ministry.petroleum@nic.in"),
        "name": "MoPNG Monitoring Officer",
        "role": "ministry",
        "ministry": "Ministry of Petroleum and Natural Gas",
        "project_id": None,
    },
    {
        "email": os.getenv("DEMO_AGENCY_EMAIL", "iocl.agency@iocl.gov.in"),
        "name": "IOCL Project Cell",
        "role": "agency",
        "agency": "IOCL",
        "project_id": os.getenv("DEMO_AGENCY_PROJECT", "701392"),
    },
    {
        "email": os.getenv("DEMO_PUBLIC_EMAIL", "public.analyst@citizen.in"),
        "name": "Public Analyst",
        "role": "viewer",
        "project_id": None,
    },
]


def _latest_prediction_summary(db: Session, project_ids):
    """Return latest prediction row per project (id, risk_tier, composite score)."""
    from .crud import get_latest_prediction_subquery
    subq = get_latest_prediction_subquery(db)
    rows = (
        db.query(
            models.Project.project_id,
            models.Project.sector,
            models.Project.ministry,
            models.Project.status,
            models.Snapshot.physical_progress_pct,
            models.Snapshot.cumulative_expenditure_crore,
            models.Prediction.composite_risk_score,
            models.Prediction.risk_tier,
            models.Prediction.delay_risk_months,
        )
        .join(subq, models.Project.project_id == subq.c.project_id)
        .join(
            models.Prediction,
            (models.Prediction.project_id == subq.c.project_id)
            & (models.Prediction.snapshot_month == subq.c.max_month),
        )
        .join(
            models.Snapshot,
            (models.Snapshot.project_id == subq.c.project_id)
            & (models.Snapshot.snapshot_month == subq.c.max_month),
        )
        .all()
    )
    return rows


def seed_public_rows(db: Session) -> int:
    """(Re)build the PUBLIC-SAFE projection table from raw project data.
    Only 'public-visible' fields are copied; never budgets, remarks, documents."""
    rows = _latest_prediction_summary(db, None)
    # Clear and rebuild
    db.query(models.ProjectPublicRow).delete()
    for (
        pid,
        sector,
        ministry,
        status,
        phys_pct,
        expenditure,
        score,
        tier,
        delay_months,
    ) in rows:
        on_track = 1 if (score or 0) < 50 else 0
        summary = (
            f"{sector} infrastructure project in {ministry}, current physical progress "
            f"{phys_pct:.1f}%, status {status}."
        )
        db.add(
            models.ProjectPublicRow(
                project_id=pid,
                is_public_visible=1,
                sector=sector,
                ministry=ministry,
                status=status,
                completion_percent=round(phys_pct or 0.0, 1),
                on_track=on_track,
                risk_tier_label=tier,
                public_summary=summary,
                updated_at=datetime.now(timezone.utc),
            )
        )
    db.commit()
    return len(rows or [])


def seed_demo_users(db: Session) -> int:
    """Create demo role users (idempotent) so each dashboard can be demoed."""
    seed_default_admin(db)
    initial_pw = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip() or "Admin@12345"
    pw_hash = hash_password(initial_pw)
    created = 0
    for spec in DEMO_USERS:
        existing = db.query(models.User).filter(models.User.email == spec["email"]).first()
        if existing:
            existing.password_hash = pw_hash
            existing.status = "active"
            if spec.get("ministry"):
                existing.ministry = spec["ministry"]
            if spec.get("agency"):
                existing.agency = spec["agency"]
            if spec.get("project_id"):
                existing.project_id = spec["project_id"]
            db.commit()
            continue
        db.add(
            models.User(
                email=spec["email"],
                name=spec["name"],
                role=spec["role"],
                status="active",
                ministry=spec.get("ministry"),
                agency=spec.get("agency"),
                project_id=spec.get("project_id"),
                password_hash=pw_hash,
                created_at=datetime.now(timezone.utc),
                last_login_at=datetime.now(timezone.utc),
            )
        )
        created += 1
    if created:
        db.commit()
        for spec in DEMO_USERS:
            log_audit(db, "system", None, "demo_user_seeded", "user", spec["email"], {"role": spec["role"]})
    return created


def bootstrap(db: Session) -> dict:
    """Run all startup seed steps; returns counts."""
    ensure_auth_columns(db)
    public_n = seed_public_rows(db)
    admin_n = seed_default_admin(db)
    sig = seed_demo_users(db)
    return {"public_rows": public_n, "admin": admin_n, "demo_users": sig}