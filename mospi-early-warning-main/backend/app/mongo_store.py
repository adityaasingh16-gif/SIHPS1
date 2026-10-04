"""MongoDB storage/bootstrap helpers."""
import datetime as dt
import csv
import logging, os
from .database import mongo_db, create_mongo_indexes, mongo_ping

logger = logging.getLogger("mospi_backend.mongo")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "dhrishti")


def mongo_status():
    try:
        mongo_db.command("ping")
        return {"configured": True, "connected": True, "database": MONGO_DB,
                "collections": {n: mongo_db[n].estimated_document_count() for n in mongo_db.list_collection_names()}}
    except Exception as e:
        return {"configured": True, "connected": False, "database": MONGO_DB, "error": str(e)}


def _bson_value(value):
    """Coerce a SQLAlchemy column value into something BSON can store.

    PyMongo encodes ``datetime.datetime`` but rejects the bare ``datetime.date``
    that SQL ``Date`` columns hand back, so mirroring a seeded snapshot straight
    from SQL raises InvalidDocument. Widen dates to UTC midnight. The datetime
    check must come first, since datetime is a subclass of date.
    """
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
    return value


def _rows(db, model):
    return [{c.name: _bson_value(getattr(x, c.name)) for c in model.__table__.columns} for x in db.query(model).all()]


def mirror_snapshot(db):
    """Copy the seeded SQL compatibility data into the Mongo source-of-truth collections."""
    from . import models
    if not mongo_ping():
        return {"status": "mongo_unavailable", "database": MONGO_DB}
    create_mongo_indexes()
    written = {}
    projects = _rows(db, models.Project)
    snaps = _rows(db, models.Snapshot)
    preds = _rows(db, models.Prediction)
    shaps = _rows(db, models.SHAPExplanation)
    remarks = _rows(db, models.RemarkSignal)
    deps = _rows(db, models.ProjectDependency)
    runs = _rows(db, models.OfficerOptimizationRun)

    for c in ("projects", "snapshots", "predictions", "shap_explanations", "remarks_signals", "project_dependencies", "officer_optimization_runs"):
        mongo_db[c].delete_many({})

    if projects: mongo_db.projects.insert_many(projects)
    if snaps: mongo_db.snapshots.insert_many(snaps)
    if preds:
        shap_by_pred = {}
        for s in shaps: shap_by_pred.setdefault(s["prediction_id"], []).append({k:v for k,v in s.items() if k != "prediction_id"})
        for p in preds: p["shap_explanations"] = shap_by_pred.get(p.get("id"), [])
        mongo_db.predictions.insert_many(preds)
    if shaps:
        pred_to_project = {p.get("id"): p.get("project_id") for p in preds}
        for sh in shaps: sh["project_id"] = pred_to_project.get(sh.get("prediction_id"))
        mongo_db.shap_explanations.insert_many(shaps)
    if remarks: mongo_db.remarks_signals.insert_many(remarks)
    if deps: mongo_db.project_dependencies.insert_many(deps)
    if runs: mongo_db.officer_optimization_runs.insert_many(runs)
    written.update(projects=len(projects), snapshots=len(snaps), predictions=len(preds), shap_explanations=len(shaps), remarks_signals=len(remarks), project_dependencies=len(deps), officer_optimization_runs=len(runs))
    return {"status":"ok", "database":MONGO_DB, "written":written}


def restore_sql_cache_from_mongo(db):
    """Restore the disposable SQL compatibility cache from Mongo's saved rows.

    Monitoring data is authoritative in Mongo. Render's container filesystem
    is ephemeral, so SQLite can be empty after any restart. This imports the
    already persisted records verbatim (apart from BSON dates converted to SQL
    Date values) and never reads, trains, or writes an ML artifact.
    """
    from sqlalchemy import Date, DateTime
    from . import models
    from .database import mongo_db

    if db.query(models.Project).count():
        return {"status": "sql_cache_present", "projects": 0}
    if not mongo_ping():
        return {"status": "mongo_unavailable", "projects": 0}

    collections = [
        ("projects", models.Project),
        ("snapshots", models.Snapshot),
        ("predictions", models.Prediction),
        ("shap_explanations", models.SHAPExplanation),
        ("remarks_signals", models.RemarkSignal),
        ("project_dependencies", models.ProjectDependency),
        ("officer_optimization_runs", models.OfficerOptimizationRun),
    ]
    project_count = mongo_db.projects.count_documents({})
    if not project_count:
        return {"status": "mongo_project_data_empty", "projects": 0}

    def sql_row(model, doc):
        row = {}
        for column in model.__table__.columns:
            name = column.name
            if name not in doc:
                continue
            value = doc[name]
            if isinstance(column.type, Date) and isinstance(value, dt.datetime):
                value = value.date()
            elif isinstance(column.type, DateTime) and isinstance(value, dt.date) and not isinstance(value, dt.datetime):
                value = dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone.utc)
            row[name] = value
        return row

    written = {}
    try:
        for collection_name, model in collections:
            rows = []
            for doc in mongo_db[collection_name].find({}, {"_id": 0}):
                # The Mongo prediction document also embeds SHAP rows for the
                # monitoring API; that field is not a SQL Prediction column.
                rows.append(sql_row(model, doc))
            if rows:
                db.bulk_insert_mappings(model, rows)
            written[collection_name] = len(rows)

        # Geography is a derived lookup and was not part of the historical
        # Mongo mirror. Recreate only the state reference mapping from the
        # unchanged panel CSV; it does not score or alter source/model data.
        panel_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "panel_mospi.csv"))
        if os.path.isfile(panel_path):
            from ..geo import coordinates_for, code_for, is_mappable, multi_state_members, normalise_state
            from .models import ProjectGeo
            with open(panel_path, newline="", encoding="utf-8-sig") as panel_file:
                latest_by_project = {}
                for panel_row in csv.DictReader(panel_file):
                    project_id = str(panel_row.get("project_code") or "").strip()
                    if project_id and project_id not in latest_by_project:
                        latest_by_project[project_id] = panel_row.get("state")
            geo_rows = []
            for project in mongo_db.projects.find({}, {"_id": 0, "project_id": 1}):
                pid = str(project.get("project_id", ""))
                state = normalise_state(latest_by_project.get(pid))
                lat, lon = coordinates_for(state) if is_mappable(state) else (None, None)
                geo_rows.append({
                    "project_id": pid, "state": state, "state_code": code_for(state),
                    "lat": lat, "lon": lon, "precision": "state" if lat is not None else "none",
                    "member_count": len(multi_state_members(latest_by_project.get(pid))) or None,
                    "geo_source": "panel_csv",
                })
            if geo_rows:
                db.bulk_insert_mappings(ProjectGeo, geo_rows)
            written["project_geo"] = len(geo_rows)

        db.commit()
        logger.info("Restored SQL compatibility cache from Mongo: %s", written)
        return {"status": "restored", "projects": written.get("projects", 0), "written": written}
    except Exception:
        db.rollback()
        logger.exception("Could not restore SQL compatibility cache from Mongo")
        raise
