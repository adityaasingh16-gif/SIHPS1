"""
Router for Admin Platform Operations.

Admin-only governance endpoints that sit outside user management:
  - public directory visibility control (what the anonymous portal may show)
  - data operations status (table counts, system metadata, model load state)
  - milestone submission triage and proof-document review
  - model registry health
  - risk-signal remarks and ministry/agency message threads

Every mutation writes an audit row, so the governance actions taken here show
up in the same trail as role changes.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..ml_loader import ml_registry, MODEL_DIR
from ..auth_security import require_roles, log_audit

router = APIRouter(prefix="/admin", tags=["Admin · Operations"])

# Tables an admin can audit at a glance from the data-operations card.
COUNTED_TABLES = {
    "projects": models.Project,
    "snapshots": models.Snapshot,
    "predictions": models.Prediction,
    "shap_explanations": models.SHAPExplanation,
    "project_public": models.ProjectPublicRow,
    "remark_signals": models.RemarkSignal,
    "milestone_submissions": models.MilestoneSubmission,
    "proof_documents": models.ProofDocument,
    "message_notes": models.MessageNote,
    "project_complaints": models.ProjectComplaint,
    "officer_optimization_runs": models.OfficerOptimizationRun,
}

# Registry attribute -> the artifact file that fills it. Used to mark which
# files on disk are actually live in memory versus merely present.
REGISTRY_FILES = {
    "cost_reg_xgb": "cost_reg_xgb.joblib",
    "cost_cls_xgb": "cost_cls_xgb.joblib",
    "delay_reg_xgb": "delay_reg_xgb.joblib",
    "delay_cls_xgb": "delay_cls_xgb.joblib",
    "calibrator": "calibrator.joblib",
    "feature_extractor": "feature_extractor.joblib",
    "cost_cls_mlp": "cost_cls_mlp.joblib",
    "delay_cls_mlp": "delay_cls_mlp.joblib",
    "cost_reg_lgbm": "cost_reg_lgbm.joblib",
    "cost_cls_lgbm": "cost_cls_lgbm.joblib",
    "delay_reg_lgbm": "delay_reg_lgbm.joblib",
    "delay_cls_lgbm": "delay_cls_lgbm.joblib",
    "cost_reg_catboost": "cost_reg_catboost.joblib",
    "cost_cls_catboost": "cost_cls_catboost.joblib",
    "delay_reg_catboost": "delay_reg_catboost.joblib",
    "delay_cls_catboost": "delay_cls_catboost.joblib",
}


def _fmt(dt) -> Optional[str]:
    """Datetime columns are read back as naive strings on SQLite."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Public directory visibility
# ---------------------------------------------------------------------------

@router.get("/public-projects", response_model=list[schemas.PublicRowAdminOut])
def list_public_rows(
    response: Response,
    search: Optional[str] = Query(None),
    visible: Optional[int] = Query(None, description="1 = public only, 0 = hidden only"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0, description="Row offset for paging."),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: every public-directory row, including the hidden ones.

    The public router only ever returns `is_public_visible = 1`, so without
    this endpoint an admin has no way to see — let alone restore — a row that
    was unpublished.

    Paged with limit/offset, ordered by project_id so paging is stable, and the
    number of rows matching the filters is reported in ``X-Total-Count``. The
    table holds a couple of thousand rows, so the cap matters: without it this
    endpoint would hand the browser the whole directory on every keystroke.
    """
    q = db.query(models.ProjectPublicRow)
    if visible is not None:
        q = q.filter(models.ProjectPublicRow.is_public_visible == (1 if visible else 0))
    if search:
        pat = f"%{search}%"
        q = q.filter(
            (models.ProjectPublicRow.project_id.ilike(pat))
            | (models.ProjectPublicRow.ministry.ilike(pat))
            | (models.ProjectPublicRow.sector.ilike(pat))
        )
    if response is not None:
        response.headers["X-Total-Count"] = str(q.count())
    rows = q.order_by(models.ProjectPublicRow.project_id).limit(limit).offset(offset).all()
    return [
        schemas.PublicRowAdminOut(
            project_id=r.project_id,
            sector=r.sector,
            ministry=r.ministry,
            status=r.status,
            completion_percent=r.completion_percent,
            on_track=bool(r.on_track),
            risk_tier_label=r.risk_tier_label,
            public_summary=r.public_summary,
            is_public_visible=bool(r.is_public_visible),
            updated_at=_fmt(r.updated_at),
        )
        for r in rows
    ]


@router.patch("/public-projects/{project_id}", response_model=schemas.PublicRowAdminOut)
def update_public_row(
    project_id: str,
    payload: schemas.PublicRowUpdate,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: publish/unpublish a project and edit its public summary.

    `exclude_unset` matters here: omitting `public_summary` must leave the
    existing text alone rather than blanking it.
    """
    row = db.query(models.ProjectPublicRow).filter(
        models.ProjectPublicRow.project_id == project_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="No public-directory row for this project.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes supplied.")

    if "is_public_visible" in changes:
        row.is_public_visible = 1 if changes["is_public_visible"] else 0
    if "public_summary" in changes:
        row.public_summary = changes["public_summary"]
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        admin.email,
        admin.id,
        "public_visibility_changed",
        "project",
        project_id,
        {
            "is_public_visible": bool(row.is_public_visible),
            "summary_edited": "public_summary" in changes,
        },
    )

    return schemas.PublicRowAdminOut(
        project_id=row.project_id,
        sector=row.sector,
        ministry=row.ministry,
        status=row.status,
        completion_percent=row.completion_percent,
        on_track=bool(row.on_track),
        risk_tier_label=row.risk_tier_label,
        public_summary=row.public_summary,
        is_public_visible=bool(row.is_public_visible),
        updated_at=_fmt(row.updated_at),
    )


# ---------------------------------------------------------------------------
# Data operations
# ---------------------------------------------------------------------------

@router.get("/system-meta", response_model=schemas.DataOpsStatus)
def system_meta(
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: row counts per table, system metadata keys, model load state.

    Counted one table per query rather than in a loop over a shared session so
    each count is a single aggregate the database can answer directly.
    """
    counts = {name: db.query(model).count() for name, model in COUNTED_TABLES.items()}
    meta = db.query(models.SystemMeta).order_by(models.SystemMeta.key).all()
    return schemas.DataOpsStatus(
        models_loaded=ml_registry.is_loaded,
        table_counts=counts,
        meta=[
            schemas.SystemMetaOut(
                key=m.key, value=m.value, updated_at=_fmt(m.updated_at)
            )
            for m in meta
        ],
    )


@router.get("/model-health", response_model=schemas.ModelHealthOut)
def model_health(
    admin: models.User = Depends(require_roles("admin")),
):
    """Admin: which model artifacts exist on disk and which are live in memory.

    A file can be present but failed to unpickle, so the inventory reports both
    facts separately rather than inferring one from the other.
    """
    loaded_files = {fname for attr, fname in REGISTRY_FILES.items() if getattr(ml_registry, attr, None) is not None}

    artifacts = []
    if os.path.isdir(MODEL_DIR):
        for fname in sorted(os.listdir(MODEL_DIR)):
            path = os.path.join(MODEL_DIR, fname)
            if not os.path.isfile(path):
                continue
            stat = os.stat(path)
            artifacts.append(
                schemas.ModelArtifactOut(
                    name=fname,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    loaded_in_memory=fname in loaded_files,
                )
            )

    return schemas.ModelHealthOut(
        models_loaded=ml_registry.is_loaded,
        extra_models_loaded=ml_registry.extra_models_loaded,
        model_dir=MODEL_DIR,
        artifacts=artifacts,
        comparison_metrics_available=os.path.exists(os.path.join(MODEL_DIR, "metrics_70_30.joblib")),
        rag_index_available=os.path.exists(os.path.join(MODEL_DIR, "rag_index.pkl")),
    )


# ---------------------------------------------------------------------------
# Milestone triage & document review
# ---------------------------------------------------------------------------

@router.get("/submissions", response_model=list[schemas.MilestoneSubmissionOut])
def list_submissions(
    status_: Optional[str] = Query(None, alias="status"),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: every milestone submission across all ministries.

    Ministries only see their own queue (`GET /ministry/approvals`); this is
    the platform-wide view, which is what an admin needs to spot a ministry
    that has stopped clearing its queue.
    """
    q = db.query(models.MilestoneSubmission)
    if status_:
        q = q.filter(models.MilestoneSubmission.status == status_)
    rows = q.order_by(models.MilestoneSubmission.submitted_at.desc()).all()
    return [
        schemas.MilestoneSubmissionOut(
            id=s.id,
            project_id=s.project_id,
            title=s.title,
            description=s.description,
            budget_spent_crore=s.budget_spent_crore,
            status=s.status,
            flagged_delay=s.flagged_delay,
            delay_note=s.delay_note,
            submitted_at=_fmt(s.submitted_at),
            decided_at=_fmt(s.decided_at),
            decision_note=s.decision_note,
            submitted_by=s.submitted_by,
        )
        for s in rows
    ]


@router.post("/submissions/{submission_id}/decision", response_model=schemas.MilestoneSubmissionOut)
def decide_submission(
    submission_id: int,
    payload: schemas.DecisionRequest,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: approve or reject a milestone submission on a ministry's behalf.

    Reserved for escalation: the normal path is the ministry deciding its own
    queue. The audit row records that an admin overrode it.
    """
    row = db.query(models.MilestoneSubmission).filter(
        models.MilestoneSubmission.id == submission_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if row.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Submission is already {row.status}.",
        )

    row.status = "approved" if payload.approve else "rejected"
    row.decided_by = admin.id
    row.decided_at = datetime.now(timezone.utc)
    row.decision_note = payload.note
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        admin.email,
        admin.id,
        "milestone_escalation_decision",
        "milestone",
        str(row.id),
        {"project_id": row.project_id, "status": row.status, "note": payload.note},
    )

    return schemas.MilestoneSubmissionOut(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        description=row.description,
        budget_spent_crore=row.budget_spent_crore,
        status=row.status,
        flagged_delay=row.flagged_delay,
        delay_note=row.delay_note,
        submitted_at=_fmt(row.submitted_at),
        decided_at=_fmt(row.decided_at),
        decision_note=row.decision_note,
        submitted_by=row.submitted_by,
    )


@router.get("/documents", response_model=list[schemas.ProofDocumentAdminOut])
def list_documents(
    project_id: Optional[str] = Query(None),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: uploaded proof documents with the uploading account resolved."""
    q = db.query(models.ProofDocument)
    if project_id:
        q = q.filter(models.ProofDocument.project_id == project_id)
    rows = q.order_by(models.ProofDocument.uploaded_at.desc()).all()

    uploaders = {
        u.id: u
        for u in db.query(models.User).filter(
            models.User.id.in_({r.user_id for r in rows if r.user_id})
        ).all()
    } if rows else {}

    return [
        schemas.ProofDocumentAdminOut(
            id=d.id,
            project_id=d.project_id,
            milestone_id=d.milestone_id,
            filename=d.filename,
            url=d.url,
            uploaded_by=(uploaders[d.user_id].email if d.user_id in uploaders else None),
            uploaded_at=_fmt(d.uploaded_at),
        )
        for d in rows
    ]


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: remove a proof document that was uploaded in error.

    Deletes the row and, when the upload has a stored path, the file too. A
    document reachable only by `url` is left alone — the file is not ours to
    remove.
    """
    doc = db.query(models.ProofDocument).filter(
        models.ProofDocument.id == document_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    reference = {
        "project_id": doc.project_id,
        "filename": doc.filename,
        "file_removed": False,
    }
    if doc.stored_path and os.path.isfile(doc.stored_path):
        try:
            os.remove(doc.stored_path)
            reference["file_removed"] = True
        except OSError:
            # The row is still deleted; an orphaned file is preferable to a
            # 500 that leaves the admin unable to clear the queue.
            pass

    db.delete(doc)
    db.commit()
    log_audit(db, admin.email, admin.id, "proof_document_deleted", "document",
              str(document_id), reference)
    return {"deleted": True, "id": document_id}


# ---------------------------------------------------------------------------
# Risk-signal remarks & message threads
# ---------------------------------------------------------------------------

@router.get("/remark-signals", response_model=list[schemas.RemarkSignalOut])
def list_remark_signals(
    tag: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: NLP warning tags extracted from snapshot remarks.

    Joined to the project so a tag can be acted on without a second lookup.
    """
    q = db.query(
        models.RemarkSignal,
        models.Project.ministry,
        models.Project.sector,
    ).join(
        models.Project,
        models.Project.project_id == models.RemarkSignal.project_id,
    )
    if tag:
        q = q.filter(models.RemarkSignal.tag.ilike(f"%{tag}%"))
    rows = q.order_by(models.RemarkSignal.id.desc()).limit(limit).all()
    return [
        schemas.RemarkSignalOut(
            id=r.id,
            project_id=r.project_id,
            ministry=ministry,
            sector=sector,
            snapshot_month=r.snapshot_month,
            tag=r.tag,
            confidence=r.confidence,
        )
        for r, ministry, sector in rows
    ]


@router.get("/message-notes", response_model=list[schemas.MessageNoteAdminOut])
def list_message_notes(
    project_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: ministry/agency message threads, flattened for oversight."""
    q = db.query(models.MessageNote)
    if project_id:
        q = q.filter(models.MessageNote.project_id == project_id)
    rows = q.order_by(models.MessageNote.id.desc()).limit(limit).all()

    senders = {
        u.id: u
        for u in db.query(models.User).filter(
            models.User.id.in_({r.sender_id for r in rows if r.sender_id})
        ).all()
    } if rows else {}

    return [
        schemas.MessageNoteAdminOut(
            id=n.id,
            project_id=n.project_id,
            sender_id=n.sender_id,
            sender_email=(senders[n.sender_id].email if n.sender_id in senders else None),
            sender_role=n.sender_role,
            text=n.text,
            created_at=_fmt(n.created_at),
        )
        for n in rows
    ]


# Triage states a complaint can be moved to. `new` is where it lands on
# arrival and is not a destination an admin can set by hand.
COMPLAINT_STATUSES = ("new", "reviewing", "resolved", "rejected")


@router.get("/complaints", response_model=list[schemas.ComplaintAdminOut])
def list_complaints(
    status_: Optional[str] = Query(None, alias="status", description="new|reviewing|resolved|rejected"),
    category: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: the public complaint queue, newest first.

    `reporter_email` is only ever populated when the visitor chose to give one,
    which is why it is optional in the public schema.
    """
    q = db.query(models.ProjectComplaint)
    if status_:
        q = q.filter(models.ProjectComplaint.status == status_)
    if category:
        q = q.filter(models.ProjectComplaint.category == category)
    if project_id:
        q = q.filter(models.ProjectComplaint.project_id == project_id)
    rows = q.order_by(models.ProjectComplaint.id.desc()).limit(limit).all()

    # Complaints carry no foreign key on purpose, so the ministry comes from
    # the public projection and is simply absent for a project not in it.
    ministries = {}
    if rows:
        ministries = {
            r.project_id: r.ministry
            for r in db.query(models.ProjectPublicRow)
            .filter(models.ProjectPublicRow.project_id.in_({r.project_id for r in rows}))
            .all()
        }

    return [
        schemas.ComplaintAdminOut(
            id=c.id,
            project_id=c.project_id,
            ministry=ministries.get(c.project_id),
            category=c.category,
            subject=c.subject,
            description=c.description,
            reporter_email=c.reporter_email,
            status=c.status,
            admin_note=c.admin_note,
            created_at=_fmt(c.created_at),
            updated_at=_fmt(c.updated_at),
            resolved_at=_fmt(c.resolved_at),
        )
        for c in rows
    ]


@router.patch("/complaints/{complaint_id}", response_model=schemas.ComplaintAdminOut)
def update_complaint(
    complaint_id: int,
    payload: schemas.ComplaintStatusUpdate,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: move a complaint through triage, or attach an internal note.

    Closing a complaint sets `resolved_at`; reopening it clears it, so the
    timestamp always describes the current state rather than the first time it
    was closed.
    """
    complaint = db.query(models.ProjectComplaint).filter(
        models.ProjectComplaint.id == complaint_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if not payload.status and payload.admin_note is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a status to change, or a note to record.",
        )

    # Read the state we are moving away from before anything is overwritten.
    previous_status = complaint.status

    if payload.status:
        if payload.status not in COMPLAINT_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"`status` must be one of: {', '.join(COMPLAINT_STATUSES)}.",
            )
        if complaint.status != "new" and payload.status == "new":
            raise HTTPException(
                status_code=409,
                detail="A complaint already in triage cannot go back to `new`.",
            )
        complaint.status = payload.status

    if payload.admin_note is not None:
        complaint.admin_note = payload.admin_note.strip() or None

    complaint.updated_at = datetime.now(timezone.utc)
    if complaint.status in ("resolved", "rejected"):
        complaint.resolved_at = complaint.updated_at
    elif previous_status in ("resolved", "rejected"):
        complaint.resolved_at = None

    db.commit()
    log_audit(
        db,
        admin.email,
        admin.id,
        "complaint_updated",
        "complaint",
        str(complaint.id),
        {
            "project_id": complaint.project_id,
            "status": complaint.status,
            "note_recorded": payload.admin_note is not None,
        },
    )

    return schemas.ComplaintAdminOut(
        id=complaint.id,
        project_id=complaint.project_id,
        category=complaint.category,
        subject=complaint.subject,
        description=complaint.description,
        reporter_email=complaint.reporter_email,
        status=complaint.status,
        admin_note=complaint.admin_note,
        created_at=_fmt(complaint.created_at),
        updated_at=_fmt(complaint.updated_at),
        resolved_at=_fmt(complaint.resolved_at),
    )
