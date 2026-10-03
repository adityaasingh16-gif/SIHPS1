"""
Router for Officer Capacity Optimization Endpoint (Endpoint 8).
Calls OR-Tools solver to prioritize high-risk project reviews under officer hour constraints.
"""

from datetime import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, crud

# Import OfficerCapacityOptimizer from existing mospi_early_warning package
from src.optimization import OfficerCapacityOptimizer
from src.config import PipelineConfig

router = APIRouter(prefix="", tags=["Optimization"])

@router.post("/optimize-queue", response_model=schemas.OptimizeQueueResponse)
def optimize_officer_queue(
    payload: schemas.OptimizeQueueRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint 8: POST /optimize-queue
    Calls OR-Tools MILP solver to select high-risk projects for review under capacity constraints.
    Logs execution run to officer_optimization_runs database table.
    """
    if payload.available_hours <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="available_hours must be a positive float."
        )

    # Construct DataFrame of projects with latest predictions from database
    subq = crud.get_latest_prediction_subquery(db)
    
    rows = db.query(
        models.Project, models.Snapshot, models.Prediction
    ).join(
        subq, models.Project.project_id == subq.c.project_id
    ).join(
        models.Snapshot,
        and_(
            models.Snapshot.project_id == subq.c.project_id,
            models.Snapshot.snapshot_month == subq.c.max_month
        )
    ).join(
        models.Prediction,
        and_(
            models.Prediction.project_id == subq.c.project_id,
            models.Prediction.snapshot_month == subq.c.max_month
        )
    ).all()
    
    if len(rows) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No projects found in database to optimize."
        )

    records = []
    for proj, snap, pred in rows:
        records.append({
            "project_id": proj.project_id,
            "sector": proj.sector,
            "ministry": proj.ministry,
            "implementing_agency": proj.implementing_agency,
            "original_cost": proj.original_cost_crore,
            "snapshot_month": snap.snapshot_month,
            "composite_risk_score": pred.composite_risk_score,
            "risk_tier": pred.risk_tier,
            "unresolved_land_issues": 1 if "Land" in str(snap.remarks_text) else 0,
            "unresolved_approval_issues": 1 if "Approval" in str(snap.remarks_text) else 0,
            "remarks_text": snap.remarks_text or "No remarks"
        })

    df_risk = pd.DataFrame(records)
    
    # Instantiate OfficerCapacityOptimizer
    optimizer = OfficerCapacityOptimizer(PipelineConfig())
    opt_res = optimizer.optimize_review_queue(
        df_risk=df_risk,
        officer_capacity_hours=payload.available_hours
    )
    
    selected_pids = [p["project_id"] for p in opt_res["selected_projects_queue"]]
    
    # Log run into database table officer_optimization_runs
    log_run = crud.create_officer_run_log(
        db,
        available_hours=payload.available_hours,
        selected_ids=selected_pids,
        total_risk_mitigated=opt_res["total_risk_mitigated"]
    )

    formatted_queue = [
        schemas.OptimizedProjectItem(
            project_id=p["project_id"],
            sector=p["sector"],
            ministry=p["ministry"],
            composite_risk_score=round(p["composite_risk_score"], 1),
            risk_tier=p["risk_tier"],
            required_review_hours=p["required_review_hours"],
            risk_reduction_impact=p["risk_reduction_impact"],
            unresolved_land_issues=p["unresolved_land_issues"],
            unresolved_approval_issues=p["unresolved_approval_issues"],
            remarks_text=p["remarks_text"]
        ) for p in opt_res["selected_projects_queue"]
    ]

    return schemas.OptimizeQueueResponse(
        run_id=log_run.id,
        run_at=log_run.run_at.isoformat(),
        available_hours=payload.available_hours,
        total_hours_allocated=opt_res["total_hours_allocated"],
        capacity_utilization_pct=opt_res["capacity_utilization_pct"],
        total_risk_mitigated=opt_res["total_risk_mitigated"],
        n_projects_selected=opt_res["n_projects_selected"],
        total_candidates=opt_res["total_high_risk_candidates"],
        selected_projects_queue=formatted_queue
    )
