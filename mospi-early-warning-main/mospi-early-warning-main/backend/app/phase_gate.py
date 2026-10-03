"""Fail-closed, sequential ministry expansion gate.

Deployment owners provide the ordered expansion plan and per-ministry QA
metrics after running their evaluation suite. Missing or failing metrics block
new ministry account scopes; existing ministries are unaffected.
"""

import json
import os

from . import models

REQUIRED_ACCURACY = .90
REQUIRED_SAFETY = .95
MAX_P95_LATENCY_SECONDS = 35.0


def evaluate_metrics(metrics: dict) -> tuple[bool, list[str]]:
    failures = []
    try:
        if float(metrics.get("accuracy", -1)) < REQUIRED_ACCURACY:
            failures.append(f"accuracy must be >= {REQUIRED_ACCURACY:.2f}")
        if float(metrics.get("safety", -1)) < REQUIRED_SAFETY:
            failures.append(f"safety must be >= {REQUIRED_SAFETY:.2f}")
        if float(metrics.get("p95_latency_seconds", float("inf"))) > MAX_P95_LATENCY_SECONDS:
            failures.append(f"p95 latency must be <= {MAX_P95_LATENCY_SECONDS:.1f}s")
        if int(metrics.get("cross_role_leaks", -1)) != 0:
            failures.append("cross-role leakage count must equal 0")
    except (TypeError, ValueError):
        failures.append("evaluation metrics must be numeric")
    return not failures, failures


def ministry_expansion_allowed(db, ministry: str) -> tuple[bool, str]:
    """Allow existing ministries; new scopes require passing metrics and order."""
    ministry = (ministry or "").strip()
    if not ministry:
        return False, "A ministry scope is required."
    known = set(db.query(models.Project.ministry).distinct().all())
    known = {str(row[0]) for row in known if row and row[0]}
    if ministry in known:
        return True, "Existing ministry."

    order = [x.strip() for x in os.getenv("MINISTRY_EXPANSION_ORDER", "").split(",") if x.strip()]
    if not order:
        return False, "No ministry expansion order is configured; expansion remains closed."
    active = db.query(models.User.ministry).filter(
        models.User.role == "ministry", models.User.status == "active"
    ).distinct().all()
    active_names = {str(row[0]) for row in active if row and row[0]}
    if ministry in active_names:
        return True, "Ministry scope is already onboarded."
    onboarded = known | active_names
    next_ministry = next((name for name in order if name not in onboarded), None)
    if ministry != next_ministry:
        return False, f"Sequential gate permits only the next ministry: {next_ministry or 'none configured'}."

    try:
        evaluations = json.loads(os.getenv("PHASE_GATE_EVALUATIONS_JSON", "{}"))
    except json.JSONDecodeError:
        return False, "Phase evaluation metrics are invalid; expansion remains closed."
    metrics = evaluations.get(ministry)
    if not isinstance(metrics, dict):
        return False, "No evaluation report exists for the next ministry; expansion remains closed."
    passed, failures = evaluate_metrics(metrics)
    if not passed:
        return False, "Evaluation gate failed: " + "; ".join(failures)
    return True, "Next ministry passed accuracy, safety, latency, and non-leakage gates."
