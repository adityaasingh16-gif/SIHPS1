"""
Router for Ministry Role.
Scoped to the authenticated ministry user's own ministry only.
Dashboard, project list, pending milestone approvals with approve/reject,
budget vs utilization chart, delay alerts, and communication with agencies.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth_security import require_roles, log_audit
from ..crud import get_projects, get_project_detail

router = APIRouter(prefix="/ministry", tags=["Ministry"])


def _ministry_projects(db: Session, ministry: Optional[str]):
    return get_projects(db, ministry=ministry)


def _get_ministry_project(db: Session, ministry: str, project_id: str) -> models.Project:
    from ..crud import _resolve_project_id
    resolved = _resolve_project_id(db, project_id)
    project = db.query(models.Project).filter(models.Project.project_id == resolved).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if project.ministry != ministry:
        raise HTTPException(status_code=403, detail="Project is not under your ministry.")
    return project


@router.get("/dashboard", response_model=schemas.MinistryDashboardResponse)
def ministry_dashboard(
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: scoped dashboard — own ministry projects, approvals, budget, alerts."""
    ministry = me.ministry or ""
    projects = _ministry_projects(db, ministry)

    ids = [p.project_id for p in projects]
    pending_approvals = []
    if ids:
        pending_approvals = (
            db.query(models.MilestoneSubmission)
            .filter(
                models.MilestoneSubmission.project_id.in_(ids),
                models.MilestoneSubmission.status == "pending",
            )
            .order_by(models.MilestoneSubmission.submitted_at.desc())
            .all()
        )

    detail_rows = []
    for p in projects:
        detail_rows.append(get_project_detail(db, p.project_id))

    delayed = [d for d in detail_rows if d and (d.composite_risk_score or 0) >= 50]
    active_projects = [d for d in detail_rows if d and d.status == "Ongoing"]

    from ..crud import _format_date
    alerts = []
    for d in delayed or []:
        alerts.append(
            schemas.AlertItem(
                id=f"MALT_{d.project_id}",
                project_id=d.project_id,
                severity="Critical" if (d.composite_risk_score or 0) >= 75 else "High",
                message=f"Project {d.project_id} ({d.sector}) is flagged as delayed with risk score {d.composite_risk_score:.1f}.",
                alert_type="tier_boundary_crossed" if (d.composite_risk_score or 0) >= 75 else "trend_increasing",
                composite_risk_score=d.composite_risk_score,
                risk_tier=d.risk_tier,
                timestamp=_format_date(datetime.now(timezone.utc)),
            )
        )

    total_budget = sum(d.original_cost_crore for d in detail_rows if d)
    spent = sum(d.cumulative_expenditure_crore for d in detail_rows if d)
    utils = (spent / total_budget * 100.0) if total_budget else 0.0
    avg_risk = (sum(d.composite_risk_score for d in detail_rows if d) / len(detail_rows)) if detail_rows else 0.0

    milestone_out = []
    for ms in pending_approvals:
        milestone_out.append(
            schemas.MilestoneSubmissionOut(
                id=ms.id,
                project_id=ms.project_id,
                title=ms.title,
                description=ms.description,
                budget_spent_crore=ms.budget_spent_crore,
                status=ms.status,
                flagged_delay=ms.flagged_delay,
                delay_note=ms.delay_note,
                submitted_at=_format_date(ms.submitted_at),
                decided_at=_format_date(ms.decided_at),
                decision_note=ms.decision_note,
                submitted_by=ms.submitted_by,
            )
        )

    budget_chart = [
        {"label": "Sanctioned", "value": round(total_budget, 1)},
        {"label": "Utilised", "value": round(spent, 1)},
    ]
    risk_chart = [
        {"label": tier, "count": sum(1 for d in detail_rows if d and d.risk_tier == tier)}
        for tier in ["Critical", "High", "Medium", "Low"]
    ]

    return schemas.MinistryDashboardResponse(
        ministry=ministry,
        total_projects=len(projects),
        active_projects=len(active_projects),
        delayed_projects=len(delayed),
        pending_approvals=len(pending_approvals),
        avg_composite_risk=round(avg_risk, 1),
        budget_total_crore=round(total_budget, 1),
        budget_utilized_pct=round(utils, 1),
        projects=[p for p in projects],
        milestones=milestone_out,
        alerts=alerts,
        chart_budget=budget_chart,
        chart_risk=risk_chart,
    )


@router.get("/projects", response_model=list[schemas.ProjectSummary])
def ministry_projects(
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: projects scoped to own ministry."""
    return _ministry_projects(db, me.ministry)


@router.get("/projects/{project_id}", response_model=schemas.ProjectDetail)
def ministry_project_detail(
    project_id: str,
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: single project detail (scope-checked)."""
    _get_ministry_project(db, me.ministry, project_id)
    return get_project_detail(db, project_id)


@router.get("/approvals", response_model=list[schemas.MilestoneSubmissionOut])
def ministry_approvals(
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: pending milestone approvals for own ministry."""
    projects = _ministry_projects(db, me.ministry)
    ids = [p.project_id for p in projects]
    if not ids:
        return []
    rows = (
        db.query(models.MilestoneSubmission)
        .filter(models.MilestoneSubmission.project_id.in_(ids))
        .order_by(models.MilestoneSubmission.submitted_at.desc())
        .all()
    )
    from ..crud import _format_date
    return [
        schemas.MilestoneSubmissionOut(
            id=ms.id,
            project_id=ms.project_id,
            title=ms.title,
            description=ms.description,
            budget_spent_crore=ms.budget_spent_crore,
            status=ms.status,
            flagged_delay=ms.flagged_delay,
            delay_note=ms.delay_note,
            submitted_at=_format_date(ms.submitted_at),
            decided_at=_format_date(ms.decided_at),
            decision_note=ms.decision_note,
            submitted_by=ms.submitted_by,
        )
        for ms in rows
    ]


@router.post("/approvals/{submission_id}/decision", response_model=schemas.MilestoneSubmissionOut)
def approve_or_reject(
    submission_id: int,
    payload: schemas.DecisionRequest,
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: approve or reject an agency milestone submission."""
    sub = db.query(models.MilestoneSubmission).filter(models.MilestoneSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    project = db.query(models.Project).filter(models.Project.project_id == sub.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if project.ministry != me.ministry:
        raise HTTPException(status_code=403, detail="Submission is not under your ministry.")

    sub.status = "approved" if payload.approve else "rejected"
    sub.decided_by = me.id
    sub.decided_at = datetime.now(timezone.utc)
    sub.decision_note = payload.note
    db.commit()
    db.refresh(sub)

    log_audit(
        db, me.email, me.id,
        "milestone_" + sub.status,
        "milestone", str(sub.id),
        {"project_id": sub.project_id, "title": sub.title, "note": payload.note},
    )
    from ..crud import _format_date
    return schemas.MilestoneSubmissionOut(
        id=sub.id,
        project_id=sub.project_id,
        title=sub.title,
        description=sub.description,
        budget_spent_crore=sub.budget_spent_crore,
        status=sub.status,
        flagged_delay=sub.flagged_delay,
        delay_note=sub.delay_note,
        submitted_at=_format_date(sub.submitted_at),
        decided_at=_format_date(sub.decided_at),
        decision_note=sub.decision_note,
        submitted_by=sub.submitted_by,
    )


@router.get("/projects/{project_id}/thread", response_model=list[schemas.MessageNoteOut])
def project_thread(
    project_id: str,
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: communication thread for a project (ministry ↔ agency)."""
    _get_ministry_project(db, me.ministry, project_id)
    rows = (
        db.query(models.MessageNote)
        .filter(models.MessageNote.project_id == project_id)
        .order_by(models.MessageNote.created_at)
        .all()
    )
    from ..crud import _format_date
    return [
        schemas.MessageNoteOut(
            id=n.id,
            project_id=n.project_id,
            sender_role=n.sender_role,
            sender_id=n.sender_id,
            text=n.text,
            created_at=_format_date(n.created_at),
        )
        for n in rows
    ]


@router.post("/projects/{project_id}/thread", response_model=schemas.MessageNoteOut)
def post_thread_message(
    project_id: str,
    payload: schemas.MessageNoteIn,
    me: models.User = Depends(require_roles("ministry")),
    db: Session = Depends(get_db),
):
    """Ministry: communicate with agency on a project thread."""
    _get_ministry_project(db, me.ministry, project_id)
    note = models.MessageNote(
        project_id=project_id,
        sender_id=me.id,
        sender_role=me.role,
        text=payload.text,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    from ..crud import _format_date
    return schemas.MessageNoteOut(
        id=note.id,
        project_id=note.project_id,
        sender_role=note.sender_role,
        sender_id=note.sender_id,
        text=note.text,
        created_at=_format_date(note.created_at),
    )