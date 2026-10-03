"""MongoDB storage/bootstrap helpers."""
import datetime as dt
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
