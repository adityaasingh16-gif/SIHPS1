"""MongoDB CRUD/query helpers for the Dhrishti monitoring collections."""
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import List, Optional, Dict, Any
from . import schemas


def _format_date(val: Any) -> str:
    if val is None:
        return ""
    return val.isoformat() if hasattr(val, "isoformat") else str(val)


def _resolve_project_id(db, project_id: str) -> str:
    if not project_id:
        return ""
    if db.mongo.projects.find_one({"project_id": project_id}, {"_id": 1}):
        return project_id
    if project_id.startswith("P-"):
        alt = "PRJ_" + project_id[2:]
    elif project_id.startswith("PRJ_"):
        alt = "P-" + project_id[4:]
    else:
        alt = ""
    return alt if alt and db.mongo.projects.find_one({"project_id": alt}, {"_id": 1}) else project_id


def _latest_prediction(db, project_id):
    return db.mongo.predictions.find_one({"project_id": project_id}, sort=[("snapshot_month", -1)])


def get_latest_prediction_subquery(db):
    """A latest-prediction selector for the legacy SQL compatibility queries.

    Every caller joins this into a SQLAlchemy query over the compatibility
    tables (``.c.project_id`` / ``.c.max_month``), so it has to be a SQLAlchemy
    selectable. The request-scoped ``db`` is a DatabaseHandle, whose ``query``
    delegates to the SQL session. Mongo-backed readers do not want a subquery at
    all -- they get the latest prediction straight from the collection via
    ``_latest_prediction`` -- so an earlier attempt to return an aggregation
    result here only ever broke the SQL callers.
    """
    from sqlalchemy import func
    from . import models
    return db.query(models.Prediction.project_id, func.max(models.Prediction.snapshot_month).label("max_month")).group_by(models.Prediction.project_id).subquery()


def get_projects(db, ministry=None, sector=None, risk_tiers=None, status=None, search=None,
                 limit=None, offset=0, sort="risk"):
    """Filtered projects with their latest prediction joined in.

    ``limit``/``offset`` are optional. Omitting ``limit`` returns the whole
    filtered set. ``sort`` is one of ``risk`` (default, composite risk
    descending), ``cost`` (highest sanctioned-or-revised cost first) or
    ``project_id``.

    Every sort is tie-broken on ``project_id`` so paging is stable: two
    projects can share a composite score, and a page boundary landing between
    two equal-scoring rows would otherwise repeat or drop one.
    """
    summaries = _sorted_summaries(
        _filtered_summaries(db, ministry, sector, risk_tiers, status, search), sort
    )
    if limit is not None:
        return summaries[offset:offset + limit]
    return summaries[offset:] if offset else summaries


def count_projects(db, ministry=None, sector=None, risk_tiers=None, status=None, search=None):
    """Counts projects matching the same filters as ``get_projects``.

    Paged callers use this for the ``X-Total-Count`` header without a second
    full fetch. Both take their results from ``_filtered_summaries``, so the
    count cannot drift from the list it describes.
    """
    return len(_filtered_summaries(db, ministry, sector, risk_tiers, status, search))


def _latest_predictions_bulk(db, pids):
    """Latest prediction per project_id in one aggregation instead of an N+1 find."""
    if not pids:
        return {}
    pipe = [
        {"$match": {"project_id": {"$in": pids}}},
        {"$sort": {"project_id": 1, "snapshot_month": -1}},
        {"$group": {"_id": "$project_id", "doc": {"$first": "$$ROOT"}}},
    ]
    return {d["_id"]: d.get("doc") or {} for d in db.mongo.predictions.aggregate(pipe)}


def _latest_snapshots_bulk(db, pids):
    """Latest snapshot per project_id in one aggregation instead of an N+1 find."""
    if not pids:
        return {}
    pipe = [
        {"$match": {"project_id": {"$in": pids}}},
        {"$sort": {"project_id": 1, "snapshot_month": -1}},
        {"$group": {"_id": "$project_id", "doc": {"$first": "$$ROOT"}}},
    ]
    return {d["_id"]: d.get("doc") or {} for d in db.mongo.snapshots.aggregate(pipe)}


_FILTER_CACHE = {}
_FILTER_CACHE_TTL = 45.0


def _filtered_summaries(db, ministry=None, sector=None, risk_tiers=None, status=None, search=None):
    """The one place the project filters live, shared by the list and the count.

    Latest predictions and snapshots are pulled in bulk (one aggregation per
    collection) rather than one find per project -- the per-project N+1 pattern
    turned a 2,185-project listing into ~4,400 sequential round-trips against a
    shared cluster and hung the endpoint for minutes.

    The heavy Mongo work is memoized for 45s: the risk-sync engine only
    rewrites prediction scores on a 5-minute cadence, so a short-lived list
    cache cannot go stale in practice, while it collapses a slow ~10s first
    fetch into sub-second repeats for every filter/pagination combo.
    """
    key = (ministry, sector, tuple(sorted(risk_tiers or ())), status, search)
    now = time.time()
    hit = _FILTER_CACHE.get(key)
    if hit and now - hit[0] < _FILTER_CACHE_TTL:
        return hit[1]
    q = {}
    if ministry: q["ministry"] = {"$regex": str(ministry), "$options": "i"}
    if sector: q["sector"] = {"$regex": str(sector), "$options": "i"}
    if status: q["status"] = {"$regex": str(status), "$options": "i"}
    projects = list(db.mongo.projects.find(q))
    if not projects:
        return []
    pids = [p["project_id"] for p in projects]
    preds = _latest_predictions_bulk(db, pids)
    snaps = _latest_snapshots_bulk(db, pids)
    summaries = []
    for p in projects:
        pid = p["project_id"]
        if search:
            s = str(search).lower()
            if not any(s in str(p.get(k, "")).lower() for k in ("project_id", "sector", "ministry", "implementing_agency")):
                continue
        pred = preds.get(pid)
        if not pred or (risk_tiers and pred.get("risk_tier") not in risk_tiers):
            continue
        snap = snaps.get(pid)
        summaries.append(schemas.ProjectSummary(
            project_id=p["project_id"], sector=p.get("sector"), ministry=p.get("ministry"),
            implementing_agency=p.get("implementing_agency"), original_cost_crore=p.get("original_cost_crore", 0),
            original_duration_months=p.get("original_duration_months", 0), start_date=_format_date(p.get("start_date")),
            planned_completion_date=_format_date(p.get("planned_completion_date")), status=p.get("status"),
            composite_risk_score=round(pred.get("composite_risk_score", 0), 1), risk_tier=pred.get("risk_tier"),
            cost_risk_pct=round(pred.get("cost_risk_pct", 0), 2), cost_overrun_probability=round(pred.get("cost_overrun_probability", 0), 4),
            delay_risk_months=round(pred.get("delay_risk_months", 0), 1), delay_probability=round(pred.get("delay_probability", 0), 4),
            risk_trend=pred.get("risk_trend", "stable"), latest_snapshot_month=snap.get("snapshot_month") if snap else None,
            cumulative_expenditure_crore=round(snap.get("cumulative_expenditure_crore", 0), 2) if snap else None,
            latest_revised_cost_crore=round(snap.get("latest_revised_cost_crore", 0), 2) if snap else None))
    _FILTER_CACHE[key] = (now, summaries)
    if len(_FILTER_CACHE) > 512:
        _FILTER_CACHE.clear()
    return summaries


def _sorted_summaries(summaries, sort="risk"):
    if sort == "cost":
        return sorted(summaries, key=lambda x: (
            -(x.latest_revised_cost_crore or x.original_cost_crore or 0), x.project_id))
    if sort == "project_id":
        return sorted(summaries, key=lambda x: x.project_id)
    return sorted(summaries, key=lambda x: (-x.composite_risk_score, x.project_id))


def _shap_items(pred):
    rows = pred.get("shap_explanations") or list(db_dummy for db_dummy in [])
    return rows


def get_project_detail(db, project_id, *, include_similar=True):
    project_id = _resolve_project_id(db, project_id)
    p = db.mongo.projects.find_one({"project_id": project_id})
    pred = _latest_prediction(db, project_id)
    snap = db.mongo.snapshots.find_one({"project_id": project_id}, sort=[("snapshot_month", -1)])
    if not p or not pred or not snap: return None
    # Keep the live calendar-derived pressure separate from the stored ML
    # cost-overrun probability and blended tier. Use the same calculator as
    # the periodic risk sync; this does not alter or retrain either model.
    from .risk_sync import schedule_delay_index
    start_date = p.get("start_date")
    planned_date = p.get("planned_completion_date")
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date).date()
    elif isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(planned_date, str):
        planned_date = datetime.fromisoformat(planned_date).date()
    elif isinstance(planned_date, datetime):
        planned_date = planned_date.date()
    schedule_pressure = schedule_delay_index(
        snap.get("physical_progress_pct", 0), start_date, planned_date
    )
    shap = sorted(pred.get("shap_explanations", []), key=lambda x: x.get("rank", 999))
    top = [schemas.SHAPItem(**x) for x in shap if x.get("direction") == "increases_risk"][:3]
    mitigating = [schemas.SHAPItem(**x) for x in shap if x.get("direction") == "decreases_risk"][:2]
    tags = [x.get("tag") for x in db.mongo.remarks_signals.find({"project_id": project_id, "snapshot_month": snap.get("snapshot_month")})]
    deps = get_project_dependencies(db, project_id)
    similar = get_similar_projects(db, project_id) if include_similar else []
    return schemas.ProjectDetail(
        project_id=p["project_id"], sector=p.get("sector"), ministry=p.get("ministry"), implementing_agency=p.get("implementing_agency"),
        original_cost_crore=p.get("original_cost_crore", 0), original_duration_months=p.get("original_duration_months", 0),
        start_date=_format_date(p.get("start_date")), planned_completion_date=_format_date(p.get("planned_completion_date")), status=p.get("status"),
        composite_risk_score=round(pred.get("composite_risk_score", 0), 1), risk_tier=pred.get("risk_tier"),
        cost_risk_pct=round(pred.get("cost_risk_pct", 0), 2), cost_overrun_probability=round(pred.get("cost_overrun_probability", 0), 4),
        delay_risk_months=round(pred.get("delay_risk_months", 0), 1), delay_probability=round(pred.get("delay_probability", 0), 4),
        risk_trend=pred.get("risk_trend", "stable"), latest_snapshot_month=snap.get("snapshot_month"),
        physical_progress_pct=snap.get("physical_progress_pct", 0), financial_progress_pct=snap.get("financial_progress_pct", 0),
        schedule_pressure_score=round(schedule_pressure, 1),
        cumulative_expenditure_crore=snap.get("cumulative_expenditure_crore"), milestones_planned=snap.get("milestones_planned", 0),
        milestones_achieved=snap.get("milestones_achieved", 0), remarks_text=snap.get("remarks_text"), top_risk_drivers=top,
        mitigating_factors=mitigating, extracted_tags=tags, suggested_review=generate_suggested_review_text(top[0].factor_name if top else "Schedule Slippage", snap.get("remarks_text"), pred.get("risk_tier")),
        similar_projects=similar, dependencies=deps)


def get_project_history(db, project_id):
    project_id = _resolve_project_id(db, project_id)
    p = db.mongo.projects.find_one({"project_id": project_id})
    snaps = list(db.mongo.snapshots.find({"project_id": project_id}).sort("snapshot_month", 1))
    out=[]
    dur=max(1, int((p or {}).get("original_duration_months") or 36))
    for s in snaps:
        pred=db.mongo.predictions.find_one({"project_id": project_id,"snapshot_month":s["snapshot_month"]})
        if pred:
            out.append(schemas.RiskHistoryPoint(snapshot_month=s["snapshot_month"], reporting_date=_format_date(s.get("reporting_date")), composite_risk_score=round(pred.get("composite_risk_score",0),1), cost_risk_pct=round(pred.get("cost_risk_pct",0),2), delay_risk_months=round(pred.get("delay_risk_months",0),1), physical_progress_pct=s.get("physical_progress_pct",0), planned_progress_pct=min(100.0,round((s["snapshot_month"]/dur)*100,1))))
    return out


def get_project_explanation(db, project_id):
    project_id=_resolve_project_id(db, project_id); pred=_latest_prediction(db, project_id)
    if not pred:return None
    shap=sorted(pred.get("shap_explanations",[]),key=lambda x:x.get("rank",999))
    top=[schemas.SHAPItem(**x) for x in shap if x.get("direction")=="increases_risk"][:3]
    mitigating=[schemas.SHAPItem(**x) for x in shap if x.get("direction")=="decreases_risk"][:2]
    summary=f"Project {project_id} Risk Category: {pred.get('risk_tier')} (Score: {pred.get('composite_risk_score',0):.1f})."
    if top: summary += f" Primary risk factor: {top[0].factor_name} (SHAP impact +{top[0].impact_value:.3f})."
    return schemas.ProjectExplanationResponse(project_id=project_id,snapshot_month=pred["snapshot_month"],composite_risk_score=round(pred.get("composite_risk_score",0),1),risk_tier=pred.get("risk_tier"),top_risk_drivers=top,mitigating_factors=mitigating,explanation_summary=summary)


def get_similar_projects(db, project_id, limit=4):
    project_id=_resolve_project_id(db,project_id); target=db.mongo.projects.find_one({"project_id":project_id})
    if not target:return []
    out=[]
    projects = list(db.mongo.projects.find(
        {"project_id": {"$ne": project_id}},
        {"project_id": 1, "sector": 1, "original_cost_crore": 1, "original_duration_months": 1},
    ))
    # Fetch each project's latest prediction in one aggregation. The former
    # per-project find_one made a single detail request issue thousands of
    # sequential database round trips on the hosted dataset.
    predictions = _latest_predictions_bulk(db, [p["project_id"] for p in projects])
    for p in projects:
        pred=predictions.get(p["project_id"])
        if not pred:continue
        sector_dist=0 if p.get("sector")==target.get("sector") else 1
        cost_dist=abs(p.get("original_cost_crore",0)-target.get("original_cost_crore",0))/(target.get("original_cost_crore",0)+1e-5)
        dur_dist=abs(p.get("original_duration_months",0)-target.get("original_duration_months",0))/(target.get("original_duration_months",0)+1e-5)
        sim=round(max(0,(1-(sector_dist*.5+cost_dist*.3+dur_dist*.2))*100),1)
        out.append(schemas.SimilarProjectItem(project_id=p["project_id"],sector=p.get("sector"),original_cost_crore=p.get("original_cost_crore",0),original_duration_months=p.get("original_duration_months",0),composite_risk_score=round(pred.get("composite_risk_score",0),1),risk_tier=pred.get("risk_tier"),similarity_score=sim))
    return sorted(out,key=lambda x:x.similarity_score,reverse=True)[:limit]


def get_project_dependencies(db, project_id):
    project_id=_resolve_project_id(db,project_id); out=[]
    for d in db.mongo.project_dependencies.find({"project_id":project_id}):
        pred=_latest_prediction(db,d.get("related_project_id"))
        if pred: out.append(schemas.DependencyItem(related_project_id=d["related_project_id"],relation_type=d.get("relation_type","related"),risk_tier=pred.get("risk_tier"),composite_risk_score=round(pred.get("composite_risk_score",0),1)))
    return out


_ALERTS_CACHE = {"ts": 0.0, "data": None}
_ALERTS_CACHE_TTL = 90.0


def get_alerts(db):
    # The risk-sync engine rewrites scores on a 5-minute cadence, so an
    # organisational alert feed cached for 90s cannot look stale in practice,
    # and the per-request aggregation over 18k predictions was the single
    # slowest endpoint on the hosted instance.
    now = time.time()
    if _ALERTS_CACHE["data"] is not None and now - _ALERTS_CACHE["ts"] < _ALERTS_CACHE_TTL:
        return _ALERTS_CACHE["data"]
    out=[]
    pred_col=db.mongo.predictions; proj_col=db.mongo.projects
    sector_map={p["project_id"]: p.get("sector") for p in proj_col.find({}, {"project_id": 1, "sector": 1})}
    pipe=[
        {"$project": {"_id": 0, "project_id": 1, "snapshot_month": 1, "risk_tier": 1,
                      "risk_trend": 1, "composite_risk_score": 1, "predicted_at": 1}},
        {"$sort": {"project_id": 1, "snapshot_month": -1}},
        {"$group": {"_id": "$project_id", "pred": {"$first": "$$ROOT"}}},
    ]
    for doc in pred_col.aggregate(pipe):
        pred=doc.get("pred") or {}
        if pred.get("risk_tier")=="Critical" or (pred.get("risk_trend")=="increasing" and pred.get("risk_tier") in ("Critical","High")):
            sev="Critical" if pred.get("risk_tier")=="Critical" else "High"
            pid=pred.get("project_id")
            out.append(schemas.AlertItem(id=f"ALT_{len(out)+1:03d}",project_id=pid,severity=sev,message=f"Project {pid} ({sector_map.get(pid)}) risk score reached {pred.get('composite_risk_score',0):.1f} ({pred.get('risk_tier')}). Risk trend is {pred.get('risk_trend')}",alert_type="trend_increasing" if pred.get("risk_trend")=="increasing" else "tier_boundary_crossed",composite_risk_score=round(pred.get("composite_risk_score",0),1),risk_tier=pred.get("risk_tier"),timestamp=_format_date(pred.get("predicted_at")) or datetime.now(timezone.utc).isoformat()))
    out.sort(key=lambda a: a.composite_risk_score, reverse=True)
    _ALERTS_CACHE["ts"] = now
    _ALERTS_CACHE["data"] = out
    return out


def create_officer_run_log(db, available_hours, selected_ids, total_risk_mitigated):
    now=datetime.now(timezone.utc); doc={"run_at":now,"available_hours":available_hours,"selected_project_ids":selected_ids,"total_risk_mitigated":total_risk_mitigated}
    result=db.mongo.officer_optimization_runs.insert_one(doc); doc["id"]=str(result.inserted_id)
    return SimpleNamespace(**doc)


def generate_suggested_review_text(top_driver, remarks, risk_tier):
    if "land" in top_driver.lower() or "land" in str(remarks).lower(): return "Priority 1: Convene joint review with State Revenue Authorities and District Collector to expedite land acquisition and ROW clearance."
    if "approval" in top_driver.lower() or "forest" in str(remarks).lower(): return "Priority 1: Escalate environmental & forest clearance pending at Ministry stage; conduct inter-ministerial taskforce review."
    if "gap" in top_driver.lower() or "progress" in top_driver.lower(): return "Priority 1: Issue formal notice to EPC contractor regarding physical execution lag and request revised recovery schedule."
    return f"Priority 1: Schedule comprehensive project review meeting with {risk_tier} tier monitoring team."
