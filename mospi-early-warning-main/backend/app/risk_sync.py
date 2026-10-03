"""
Live Risk Sync Engine.

Recomputes the LATEST composite risk score for every project on a rolling
cadence (default every 5 minutes) so the risk factor genuinely moves with
time. The delay component is replaced by a schedule-pressure index derived
from the real calendar:

    progress gap        = linear-implied progress - reported physical progress
    overdue streak      = days past the planned completion date

As real days pass with no progress, the gap widens and risk rises; when a
project is on/near its implied pace the delay term stays low. The composite
keeps the ML cost probability and swaps in this responsive delay index.

State (last sync time + summary) is persisted in the system_meta table so
the UI can show "risk refreshed X minutes ago".
"""

import json
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import func

from . import models
from .database import SessionLocal, mongo_db, mongo_ping
from .mongo_store import _bson_value

SYNC_INTERVAL_SECONDS = 300  # 5 minutes

TIER_THRESHOLDS = [("Critical", 75.0), ("High", 50.0), ("Medium", 25.0)]


def _tier_for_score(score: float) -> str:
    for tier, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "Low"


def _trend_for(old: float, new: float) -> str:
    if new - old > 2.0:
        return "increasing"
    if new - old < -2.0:
        return "decreasing"
    return "stable"


def schedule_delay_index(
    monthly_physical: float,
    start_date,
    planned_date,
    now: datetime | None = None,
) -> float:
    """
    Responsive schedule-pressure term (0..100).

    baseline 25 for a project exactly on its implied linear pace.
    Each 1% of progress shortfall above the implied pace adds 0.8.
    Each 90 days of overdue streak adds up to +40 more.
    """
    now = now.astimezone(timezone.utc).date() if now else datetime.now(timezone.utc).date()
    start = start_date
    if not start or not planned_date:
        return 25.0
    total_span = (planned_date - start).days
    if total_span <= 0:
        return 80.0
    elapsed = (now - start).days
    if elapsed <= 0:
        return 25.0
    expected_progress = max(0.0, min(100.0, 100.0 * elapsed / total_span))
    gap = max(0.0, expected_progress - float(monthly_physical))
    overdue_days = max(0, (now - planned_date).days)
    overdue_term = min(40.0, (overdue_days / 90.0) * 20.0)
    delay_idx = 25.0 + gap * 0.8 + overdue_term
    return max(5.0, min(100.0, delay_idx))


def responsive_composite(cost_prob: float, delay_index: float) -> float:
    """50% ML cost probability + 50% responsive schedule-pressure index."""
    cost_c = max(0.0, min(100.0, float(cost_prob) * 100.0))
    return round(0.5 * cost_c + 0.5 * float(delay_index), 1)


def set_meta(db, key: str, value: str) -> None:
    row = db.query(models.SystemMeta).filter(models.SystemMeta.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(models.SystemMeta(key=key, value=value, updated_at=datetime.now(timezone.utc)))


def get_meta(db, key: str) -> str | None:
    row = db.query(models.SystemMeta).filter(models.SystemMeta.key == key).first()
    return row.value if row else None


def get_sync_status(db):
    """Read the latest sync bookkeeping for the status endpoint."""
    last = get_meta(db, "risk_last_synced_at")
    summary = get_meta(db, "risk_sync_summary")
    if last:
        last_at = datetime.fromisoformat(last)
        elapsed = (datetime.now(timezone.utc) - last_at).total_seconds()
        next_at = last_at.timestamp() + SYNC_INTERVAL_SECONDS
    else:
        elapsed = None
        next_at = None
    return {
        "mode": "live_auto_sync",
        "interval_seconds": SYNC_INTERVAL_SECONDS,
        "last_synced_at": last,
        "seconds_since_last_sync": round(elapsed) if elapsed is not None else None,
        "next_sync_at": (datetime.fromtimestamp(next_at, timezone.utc).isoformat() if next_at else None),
        "summary": json.loads(summary) if summary else None,
    }


def run_risk_sync() -> dict:
    """
    One full sync pass: recompute the latest composite/tier/trend for every
    project using the responsive schedule-pressure index. Returns a summary.
    """
    now = datetime.now(timezone.utc)
    summary = {
        "scanned": 0,
        "updated": 0,
        "tiers_changed": 0,
        "score_drift_gt5": 0,
        "sync_started": now.isoformat(),
    }
    # Monitoring reads go to Mongo, so recomputing the scores in SQL alone
    # would leave the portal showing the old figures forever.
    mongo_updates = []

    with SessionLocal() as db:
        subq = (
            db.query(
                models.Prediction.project_id,
                func.max(models.Prediction.snapshot_month).label("max_month"),
            )
            .group_by(models.Prediction.project_id)
            .subquery()
        )
        rows = (
            db.query(models.Project, models.Snapshot, models.Prediction)
            .join(subq, models.Project.project_id == subq.c.project_id)
            .join(
                models.Prediction,
                models.Prediction.project_id == subq.c.project_id,
            )
            .filter(models.Prediction.snapshot_month == subq.c.max_month)
            .join(
                models.Snapshot,
                models.Snapshot.project_id == subq.c.project_id,
            )
            .filter(models.Snapshot.snapshot_month == subq.c.max_month)
            .all()
        )

        for proj, snap, pred in rows:
            summary["scanned"] += 1
            prev_score = float(pred.composite_risk_score or 0.0)
            delay_idx = schedule_delay_index(
                snap.physical_progress_pct,
                proj.start_date,
                proj.planned_completion_date,
                now,
            )
            new_score = responsive_composite(pred.cost_overrun_probability, delay_idx)
            new_tier = _tier_for_score(new_score)
            new_trend = _trend_for(prev_score, new_score)

            changed = (
                new_score != prev_score
                or new_tier != pred.risk_tier
                or new_trend != pred.risk_trend
            )
            if changed:
                summary["updated"] += 1
                if new_tier != pred.risk_tier:
                    summary["tiers_changed"] += 1
                if abs(new_score - prev_score) > 5.0:
                    summary["score_drift_gt5"] += 1
                pred.composite_risk_score = new_score
                pred.risk_tier = new_tier
                pred.risk_trend = new_trend
                pred.predicted_at = now
                mongo_updates.append(
                    (pred.project_id, pred.snapshot_month, new_score, new_tier, new_trend)
                )

        summary["sync_finished"] = datetime.now(timezone.utc).isoformat()
        set_meta(db, "risk_last_synced_at", now.isoformat())
        set_meta(db, "risk_sync_summary", json.dumps(summary))
        db.commit()

    if mongo_updates and mongo_ping():
        # Targeted updates, not mirror_snapshot(): a full mirror clears
        # officer_optimization_runs and would erase the run history, which only
        # ever lives in Mongo.
        for project_id, snapshot_month, score, tier, trend in mongo_updates:
            mongo_db.predictions.update_one(
                {"project_id": project_id, "snapshot_month": _bson_value(snapshot_month)},
                {"$set": {"composite_risk_score": score, "risk_tier": tier,
                          "risk_trend": trend, "predicted_at": now}},
            )

    print(f"[risk-sync] {summary['scanned']} scanned, {summary['updated']} updated, "
          f"{summary['tiers_changed']} tier changes ({datetime.now(timezone.utc).isoformat()})")
    return summary


def start_background_sync() -> threading.Thread:
    """Daemon thread: run one pass at startup, then every SYNC_INTERVAL_SECONDS."""

    def _loop():
        while True:
            try:
                run_risk_sync()
            except Exception as exc:  # pragma: no cover - guard against scheduler death
                print(f"[risk-sync] ERROR: {exc}")
            time.sleep(SYNC_INTERVAL_SECONDS)

    thread = threading.Thread(target=_loop, name="risk-sync", daemon=True)
    thread.start()
    return thread