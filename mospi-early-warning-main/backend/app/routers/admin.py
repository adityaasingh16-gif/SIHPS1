"""
Router for Database Admin & Seeding Endpoint (Endpoint 11).
Executes synthetic generator / real PDF-panel ML pipeline, saves joblib models,
and seeds SQLite/PostgreSQL.
"""

from datetime import datetime, timedelta, date, timezone
import os
import hashlib
import logging
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..database import get_db, engine, Base
from .. import models, schemas
from ..geo import (
    coordinates_for,
    code_for,
    is_mappable,
    multi_state_members,
    normalise_state,
)
from ..auth_security import require_roles
from ..ml_loader import ml_registry, MODEL_DIR

logger = logging.getLogger("mospi_backend.admin")


def _mirror_to_mongo(db) -> str:
    """Mirror the freshly seeded SQL rows into Mongo, the monitoring read path.

    Returns an empty string on success, or a warning to surface in the seed
    response. mirror_snapshot() reports an unreachable server by return value
    rather than raising, so without this a seed that never reached Mongo would
    still answer SUCCESS while the portal -- which reads Mongo -- stayed empty.
    """
    from ..mongo_store import mirror_snapshot
    result = mirror_snapshot(db)
    if result.get("status") != "ok":
        logger.warning("MongoDB mirror skipped during seeding: %s", result)
        return (
            f" WARNING: MongoDB was not written ({result.get('status')}); "
            "the monitoring portal will show no projects until it is reachable "
            "and seeding is run again."
        )
    return ""


# Import existing ML package modules
from src.config import PipelineConfig
from src.generator import MoSPIDataGenerator
from src.integration_pipeline import EarlyWarningPipeline

PANEL_CSV = os.getenv(
    "PANEL_CSV",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "panel_mospi.csv")),
)

router = APIRouter(prefix="/admin", tags=["Admin & Seeding"])


def _clear_project_tables(db: Session):
    db.query(models.SHAPExplanation).delete()
    db.query(models.Prediction).delete()
    db.query(models.Snapshot).delete()
    db.query(models.RemarkSignal).delete()
    db.query(models.ProjectDependency).delete()
    db.query(models.OfficerOptimizationRun).delete()
    db.query(models.Project).delete()
    # Derived from the same CSV rows, so it is rebuilt with them. Cleared
    # before Project to respect the absence of a foreign key.
    db.query(models.ProjectGeo).delete()
    db.commit()


def _seed_real_database(db: Session) -> dict:
    """Train on the real MoSPI Flash-Report panel and seed the DB with real projects."""
    from src.real_data_engine import RealDataRiskEngine

    if not os.path.exists(PANEL_CSV):
        raise FileNotFoundError(
            f"Panel CSV not found at {PANEL_CSV}. Run the PDF parser (src/pdf_panel.py) first."
        )

    engine_ml = RealDataRiskEngine(config=PipelineConfig())
    result = engine_ml.run_full(
        panel_path=PANEL_CSV,
        with_70_30=True,
        with_groupkfold=True,
        fit_production=True,
    )

    # Save all trained artifacts (rename xgb keys so legacy /simulate artifacts
    # trained on the synthetic feature space are never overwritten).
    real_models = {
        "real_" + k if k in ("cost_reg_xgb", "cost_cls_xgb", "delay_reg_xgb", "delay_cls_xgb") else k: v
        for k, v in engine_ml.models.items()
    }
    models_to_save = dict(real_models)
    models_to_save["feature_extractor_real"] = engine_ml.feature_extractor
    models_to_save["metrics_70_30"] = result["metrics_70_30"]
    models_to_save["groupkfold_metrics"] = result["groupkfold_metrics"]
    models_to_save["dataset_info"] = {
        "n_snapshots": result["n_snapshots"],
        "n_projects": result["n_projects"],
        "n_features": result["n_features"],
        "months_covered": result["months_covered"],
        "source": "pdf_flash_reports",
        "as_of_report": str(max(result["months_covered"])),
    }
    ml_registry.save_models(models_to_save, MODEL_DIR)

    # Build a df_risk-like frame from the real panel for DB seeding
    panel = pd.read_csv(PANEL_CSV)
    panel = panel.dropna(subset=["project_code", "ministry"])
    panel = panel.sort_values(["project_code", "snapshot_full"])

    # Score the whole panel with the production (full-data) models so the seeded
    # predictions reflect actual ML outputs rather than raw ground-truth flags.
    best_cost_cls = engine_ml.best_model_key("cost", "cls")
    best_delay_cls = engine_ml.best_model_key("delay", "cls")
    best_cost_reg = engine_ml.best_model_key("cost", "reg")
    best_delay_reg = engine_ml.best_model_key("delay", "reg")
    X_seed = engine_ml.feature_extractor.transform(panel)
    cost_escal_all = engine_ml.models[best_cost_reg].predict(X_seed)
    delay_months_all = engine_ml.models[best_delay_reg].predict(X_seed)
    cost_prob_all = engine_ml.models[best_cost_cls].predict_proba(X_seed)[:, 1]
    delay_prob_all = engine_ml.models[best_delay_cls].predict_proba(X_seed)[:, 1]
    pred_map = {
        idx: (float(cost_escal), float(cost_p), float(delay_m), float(delay_p))
        for (idx, cost_escal, cost_p, delay_m, delay_p) in zip(
            panel.index, cost_escal_all, cost_prob_all, delay_months_all, delay_prob_all
        )
    }

    risk_df = panel.copy()
    risk_df = risk_df.rename(columns={"project_code": "project_id"})
    risk_df["snapshot_month"] = (
        risk_df["report_year"] - 2000
    ) * 12 + risk_df["report_month"]
    # rescale to a stable 1..N month index per project for display simplicity
    risk_df["snapshot_idx"] = risk_df.groupby("project_id").cumcount() + 1
    risk_df["physical_progress_pct"] = risk_df["physical_progress_pct"].fillna(0.0)
    risk_df["cumulative_expenditure"] = risk_df["cumulative_expenditure_crore"].fillna(0.0)

    n_projects = 0
    n_geo = 0
    n_snapshots = 0
    n_predictions = 0
    n_shap = 0

    for p_id, p_rows in risk_df.groupby("project_id"):
        p_rows = p_rows.sort_values("snapshot_full")
        first = p_rows.iloc[0]
        # Build a synthetic-but-realistic project record from the first snapshot
        ministry = str(first["ministry"])
        sector = str(first.get("sector") or ministry)
        agency = str(first.get("agency") or "Multiple Agencies")
        original_cost = float(first.get("original_cost_crore") or 0.0)
        # estimate original duration from target DoC if available else 48 months
        orig_dur = 48
        if pd.notna(first.get("target_doc_year")) and pd.notna(first.get("approval_year")):
            orig_dur = max(
                6,
                (int(first["target_doc_year"]) - int(first["approval_year"])) * 12
                + (int(first.get("target_doc_month") or 1) - int(first.get("approval_month") or 1)),
            )
        start_ref = date(2023, 1, 15) + timedelta(
            days=(int(hashlib.md5(str(p_id).encode("utf-8")).hexdigest()[:8], 16) % 600)
        )
        planned_done = start_ref + timedelta(days=orig_dur * 30)

        proj = models.Project(
            project_id=str(p_id),
            sector=sector,
            ministry=ministry,
            implementing_agency=schemas.normalize_agency(agency, ministry) or "Unknown",
            original_cost_crore=original_cost,
            original_duration_months=int(orig_dur),
            start_date=start_ref,
            planned_completion_date=planned_done,
            status="Ongoing",
            created_at=datetime.now(timezone.utc),
        )
        db.add(proj)
        n_projects += 1

        # Recover the location the panel has been carrying and discarding.
        # `first["state"]` is the authoritative cell: for a multi-state project
        # it is the whole `Multi-States (...)` list, which `normalise_state`
        # reduces to a bucket rather than to whichever state is written
        # first, so no project is silently attributed somewhere it may not be.
        state = normalise_state(first.get("state"))
        lat, lon = coordinates_for(state) if is_mappable(state) else (None, None)
        members = multi_state_members(first.get("state"))
        db.add(
            models.ProjectGeo(
                project_id=str(p_id),
                state=state,
                state_code=code_for(state),
                lat=lat,
                lon=lon,
                precision="state" if lat is not None else "none",
                member_count=len(members) or None,
                geo_source="panel_csv",
            )
        )
        n_geo += 1

        prev_score = None
        for m_idx, (_, row) in enumerate(p_rows.iterrows()):
            snap_month = int(row["snapshot_idx"])
            reporting = start_ref + timedelta(days=snap_month * 30)
            physical = float(row["physical_progress_pct"])
            # financial progress ~ expenditure as % of revised cost
            exp_amt = float(row["cumulative_expenditure"] or 0.0)
            rev_cost = float(row.get("revised_cost_crore") or original_cost or 1.0)
            financial = min(100.0, (exp_amt / rev_cost * 100.0)) if rev_cost > 0 else 0.0

            snap = models.Snapshot(
                project_id=str(p_id),
                snapshot_month=snap_month,
                reporting_date=reporting,
                physical_progress_pct=physical,
                financial_progress_pct=financial,
                cumulative_expenditure_crore=exp_amt,
                latest_revised_cost_crore=rev_cost,
                milestones_planned=int(snap_month // 3),
                milestones_achieved=int(round(physical / 100.0 * (snap_month // 3))),
                remarks_text="Real MoSPI Flash-Report snapshot (Dhrishti/CRIP).",
            )
            db.add(snap)
            n_snapshots += 1

            cost_escal_p, cost_prob, delay_months_p, delay_prob = pred_map[row.name]
            score = round(0.5 * (cost_prob * 100.0) + 0.5 * (delay_prob * 100.0), 1)
            tier = (
                "Critical" if score >= 75 else
                "High" if score >= 50 else
                "Medium" if score >= 25 else "Low"
            )
            if prev_score is None:
                trend = "stable"
            elif score > prev_score + 2.0:
                trend = "increasing"
            elif score < prev_score - 2.0:
                trend = "decreasing"
            else:
                trend = "stable"
            prev_score = score

            pred = models.Prediction(
                project_id=str(p_id),
                snapshot_month=snap_month,
                cost_risk_pct=cost_escal_p,
                cost_overrun_probability=cost_prob,
                delay_risk_months=delay_months_p,
                delay_probability=delay_prob,
                composite_risk_score=score,
                risk_tier=tier,
                risk_trend=trend,
                model_version="real-pdf-v1.0.0",
                predicted_at=datetime.now(timezone.utc),
            )
            db.add(pred)
            db.flush()
            n_predictions += 1

            # SHAP-style top drivers for latest snapshot (feature-based heuristics)
            if m_idx == len(p_rows) - 1:
                drivers = [
                    ("physical_progress_pct", -physical, "decreases_risk"),
                    ("cost_escalation_pct", max(0.0, cost_escal_p), "increases_risk"),
                    ("delay_months", max(0.0, delay_months_p), "increases_risk"),
                ]
                drivers.sort(key=lambda d: abs(d[1]), reverse=True)
                rank = 1
                for d in drivers[:3]:
                    db.add(models.SHAPExplanation(
                        prediction_id=pred.id,
                        factor_name=d[0],
                        impact_value=round(d[1], 4),
                        direction=d[2],
                        rank=rank,
                    ))
                    rank += 1
                    n_shap += 1

    # Project dependencies (shared ministry)
    p_list = list(risk_df["project_id"].unique())
    for i in range(len(p_list) - 1):
        if i % 5 == 0 and i + 1 < len(p_list):
            db.add(models.ProjectDependency(
                project_id=str(p_list[i]),
                related_project_id=str(p_list[i + 1]),
                relation_type="shared_ministry",
            ))
    db.commit()

    # Rebuild public-safe projection
    from ..bootstrap import seed_public_rows
    seed_public_rows(db)

    return {
        "n_projects": n_projects,
        "n_geo": n_geo,
        "n_snapshots": n_snapshots,
        "n_predictions": n_predictions,
        "n_shap": n_shap,
        "metrics_70_30": result["metrics_70_30"],
        "groupkfold_metrics": result["groupkfold_metrics"],
        "n_features": result["n_features"],
        "months_covered": result["months_covered"],
    }

@router.post("/seed-database", response_model=schemas.SeedDatabaseResponse)
def seed_database(
    source: str = Query("synthetic", description="synthetic | pdf"),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_roles("admin")),
):
    """
    Endpoint 11: POST /admin/seed-database?source=synthetic|pdf
    source=synthetic: runs the classic synthetic generator pipeline.
    source=pdf: trains LightGBM/CatBoost/XGBoost on the real MoSPI Flash-Report
    panel (70/30 leakage-safe split) and seeds the DB with those real projects.
    """
    try:
        # Recreate tables if needed
        Base.metadata.create_all(bind=engine)

        # Clear existing data
        _clear_project_tables(db)

        if source == "pdf":
            seed = _seed_real_database(db)
            mirror_warning = _mirror_to_mongo(db)
            return schemas.SeedDatabaseResponse(
                status="SUCCESS",
                message=(
                    f"Database seeded from REAL MoSPI Flash-Report panel "
                    f"({seed['n_projects']} real projects, {seed['n_snapshots']} snapshots). "
                    "Models trained on a leakage-safe 70/30 project split."
                    + mirror_warning
                ),
                projects_seeded=seed["n_projects"],
                snapshots_seeded=seed["n_snapshots"],
                predictions_seeded=seed["n_predictions"],
                shap_records_seeded=seed["n_shap"],
                models_saved_to=MODEL_DIR,
            )

        # Step 1: Execute ML Early Warning Pipeline
        # NOTE: n_projects was previously 35, which is too small for the ML models to
        # learn reliable patterns (produced negative R^2 and calibration scores that
        # collapsed to exact clustered values like 100.0/50.0/0.0). Raised to 250 so the
        # models have enough project-level variety to generalize, while still seeding
        # in a reasonable time for a hackathon demo.
        config = PipelineConfig(n_projects=250, min_snapshots=12, max_snapshots=24)
        pipeline = EarlyWarningPipeline(config)
        pipeline.run_full_pipeline()
        
        df_risk = pipeline.df_risk
        
        # Step 2: Save trained model artifacts to joblib
        models_to_save = {
            "cost_reg_xgb": pipeline.ml_engine.cost_reg_xgb,
            "cost_cls_xgb": pipeline.ml_engine.cost_cls_xgb,
            "delay_reg_xgb": pipeline.ml_engine.delay_reg_xgb,
            "delay_cls_xgb": pipeline.ml_engine.delay_cls_xgb,
            "calibrator": pipeline.calibrator,
            "feature_extractor": pipeline.feature_extractor,
            "cost_cls_mlp": pipeline.ml_engine.cost_cls_mlp,
            "delay_cls_mlp": pipeline.ml_engine.delay_cls_mlp,
        }
        ml_registry.save_models(models_to_save, MODEL_DIR)
        
        # Step 3: Insert Projects into Database
        project_ids = df_risk["project_id"].unique()
        projects_dict = {}
        
        base_start = date(2023, 1, 15)
        
        for p_id in project_ids:
            p_rows = df_risk[df_risk["project_id"] == p_id].sort_values("snapshot_month")
            first_row = p_rows.iloc[0]
            
            dur_months = max(1, int(first_row["original_duration_months"]))
            date_offset = int(hashlib.md5(p_id.encode("utf-8")).hexdigest()[:8], 16) % 300
            start_d = base_start + timedelta(days=date_offset)
            planned_comp = start_d + timedelta(days=dur_months * 30)
            
            proj_obj = models.Project(
                project_id=p_id,
                sector=first_row["sector"],
                ministry=first_row["ministry"],
                implementing_agency=schemas.normalize_agency(
                    first_row["implementing_agency"], first_row["ministry"]
                ) or "Unknown",
                original_cost_crore=float(first_row["original_cost"]),
                original_duration_months=dur_months,
                start_date=start_d,
                planned_completion_date=planned_comp,
                status="Ongoing",
                created_at=datetime.now(timezone.utc)
            )
            db.add(proj_obj)
            projects_dict[p_id] = proj_obj
            
        db.commit()

        # Step 4: Insert Snapshots, Predictions, SHAP, and Remarks Signals
        n_snapshots_inserted = 0
        n_predictions_inserted = 0
        n_shap_inserted = 0

        for p_id in project_ids:
            p_rows = df_risk[df_risk["project_id"] == p_id].sort_values("snapshot_month")
            prev_score = None
            
            for _, row in p_rows.iterrows():
                m = int(row["snapshot_month"])
                r_date = projects_dict[p_id].start_date + timedelta(days=m * 30)
                
                # Snapshot record
                snap = models.Snapshot(
                    project_id=p_id,
                    snapshot_month=m,
                    reporting_date=r_date,
                    physical_progress_pct=float(row["physical_progress_pct"]),
                    financial_progress_pct=float(row["financial_progress_pct"]),
                    cumulative_expenditure_crore=float(row["cumulative_expenditure"]),
                    latest_revised_cost_crore=float(row["original_cost"] * (1 + (row["final_cost_escalation_pct"] / 100.0))),
                    milestones_planned=int(m / 3),
                    milestones_achieved=int(row["completed_milestones_count"]),
                    remarks_text=str(row["remarks_text"])
                )
                db.add(snap)
                n_snapshots_inserted += 1
                
                # Calculate risk trend
                curr_score = float(row["composite_risk_score"])
                if prev_score is None:
                    trend = "stable"
                elif curr_score > prev_score + 2.0:
                    trend = "increasing"
                elif curr_score < prev_score - 2.0:
                    trend = "decreasing"
                else:
                    trend = "stable"
                prev_score = curr_score
                
                # Prediction record
                pred = models.Prediction(
                    project_id=p_id,
                    snapshot_month=m,
                    cost_risk_pct=float(row["final_cost_escalation_pct"]),
                    cost_overrun_probability=float(row["calibrated_cost_prob"]),
                    delay_risk_months=float(row["final_delay_months"]),
                    delay_probability=float(row["calibrated_delay_prob"]),
                    composite_risk_score=curr_score,
                    risk_tier=str(row["risk_tier"]),
                    risk_trend=trend,
                    model_version="v1.0.0",
                    predicted_at=datetime.now(timezone.utc)
                )
                db.add(pred)
                db.flush()
                n_predictions_inserted += 1
                
                # Generate SHAP explanation records for latest snapshot
                if m == p_rows["snapshot_month"].max():
                    explanation = pipeline.get_explanation(p_id, snapshot_month=m)
                    
                    rank = 1
                    for item in explanation["top_3_positive_contributors"]:
                        shap_obj = models.SHAPExplanation(
                            prediction_id=pred.id,
                            factor_name=item["feature"],
                            impact_value=float(item["shap_impact"]),
                            direction="increases_risk",
                            rank=rank
                        )
                        db.add(shap_obj)
                        rank += 1
                        n_shap_inserted += 1
                        
                    for item in explanation["top_2_mitigating_factors"]:
                        shap_obj = models.SHAPExplanation(
                            prediction_id=pred.id,
                            factor_name=item["feature"],
                            impact_value=float(item["shap_impact"]),
                            direction="decreases_risk",
                            rank=rank
                        )
                        db.add(shap_obj)
                        rank += 1
                        n_shap_inserted += 1

                # Remarks tags
                remarks = str(row["remarks_text"])
                if "Land" in remarks:
                    db.add(models.RemarkSignal(project_id=p_id, snapshot_month=m, tag="Land Acquisition Issue", confidence=0.92))
                if "clearance" in remarks.lower() or "Approval" in remarks:
                    db.add(models.RemarkSignal(project_id=p_id, snapshot_month=m, tag="Forest/Environmental Clearance Pending", confidence=0.88))
                if "milestone" in remarks.lower():
                    db.add(models.RemarkSignal(project_id=p_id, snapshot_month=m, tag="Multiple Milestones Slippage", confidence=0.95))

        # Step 5: Insert Project Dependencies Graph
        p_list = list(project_ids)
        for i in range(len(p_list) - 1):
            if i % 2 == 0:
                dep1 = models.ProjectDependency(
                    project_id=p_list[i],
                    related_project_id=p_list[i+1],
                    relation_type="shared_agency"
                )
                dep2 = models.ProjectDependency(
                    project_id=p_list[i+1],
                    related_project_id=p_list[i],
                    relation_type="shared_agency"
                )
                db.add(dep1)
                db.add(dep2)
                
        db.commit()

        mirror_warning = _mirror_to_mongo(db)

        return schemas.SeedDatabaseResponse(
            status="SUCCESS",
            message=("Database successfully seeded with real pipeline snapshots, predictions, SHAP explanations, and saved joblib models." + mirror_warning),
            projects_seeded=len(project_ids),
            snapshots_seeded=n_snapshots_inserted,
            predictions_seeded=n_predictions_inserted,
            shap_records_seeded=n_shap_inserted,
            models_saved_to=MODEL_DIR
        )
    except Exception as e:
        db.rollback()
        logger.exception("Database seeding failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database seeding failed due to an internal error. Check server logs."
        )
