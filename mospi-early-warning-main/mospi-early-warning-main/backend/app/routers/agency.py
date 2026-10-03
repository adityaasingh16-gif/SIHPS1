"""
Router for Project / Agency Role.
Scoped to the agency user's own assigned project(s).
Submit milestone updates, upload proof documents, report budget spent,
flag anticipated delays, view upload history and project thread.
"""

import os
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth_security import require_roles, require_scope_project, log_audit
from ..crud import get_project_detail, _format_date

router = APIRouter(prefix="/agency", tags=["Agency"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads")))


def _agency_projects(me: models.User, db: Session) -> List[str]:
    """Return project ids visible to the agency user: assigned project (or all if not scoped)."""
    if me.project_id:
        return [me.project_id]
    # Unscoped agency (shouldn't normally happen) — fall back to first project
    first = db.query(models.Project).first()
    return [first.project_id] if first else []


def _shareable_url(filename: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    return f"{base}/agency/documents/{filename}"


@router.get("/dashboard", response_model=schemas.AgencyDashboardResponse)
def agency_dashboard(
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Agency: own project timeline, milestone checklist, upload history, thread."""
    project_ids = _agency_projects(me, db)
    project_id = project_ids[0]
    detail = get_project_detail(db, project_id)

    subs = (
        db.query(models.MilestoneSubmission)
        .filter(models.MilestoneSubmission.project_id == project_id)
        .order_by(models.MilestoneSubmission.submitted_at.desc())
        .limit(50)
        .all()
    )
    uploads = (
        db.query(models.ProofDocument)
        .filter(models.ProofDocument.project_id == project_id)
        .order_by(models.ProofDocument.uploaded_at.desc())
        .limit(50)
        .all()
    )
    thread = (
        db.query(models.MessageNote)
        .filter(models.MessageNote.project_id == project_id)
        .order_by(models.MessageNote.created_at)
        .all()
    )

    milestone_out = [
        schemas.MilestoneSubmissionOut(
            id=ms.id, project_id=ms.project_id, title=ms.title, description=ms.description,
            budget_spent_crore=ms.budget_spent_crore, status=ms.status, flagged_delay=ms.flagged_delay,
            delay_note=ms.delay_note, submitted_at=_format_date(ms.submitted_at),
            decided_at=_format_date(ms.decided_at), decision_note=ms.decision_note, submitted_by=ms.submitted_by,
        )
        for ms in subs
    ]
    upload_out = [
        schemas.ProofDocumentOut(
            id=d.id, project_id=d.project_id, filename=d.filename, url=d.url,
            uploaded_at=_format_date(d.uploaded_at),
        )
        for d in uploads
    ]
    thread_out = [
        schemas.MessageNoteOut(
            id=n.id, project_id=n.project_id, sender_role=n.sender_role, sender_id=n.sender_id,
            text=n.text, created_at=_format_date(n.created_at),
        )
        for n in thread
    ]
    return schemas.AgencyDashboardResponse(
        project_id=project_id,
        project_detail=detail,
        milestones=milestone_out,
        uploads=upload_out,
        thread=thread_out,
    )


@router.post("/milestones", response_model=schemas.MilestoneSubmissionOut)
def submit_milestone(
    payload: schemas.MilestoneSubmissionIn,
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Agency: submit a milestone update (pending ministry approval)."""
    for pid in _agency_projects(me, db):
        require_scope_project(me, pid)
        break
    project_id = _agency_projects(me, db)[0]

    sub = models.MilestoneSubmission(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        budget_spent_crore=payload.budget_spent_crore,
        status="pending",
        flagged_delay=payload.flagged_delay,
        delay_note=payload.delay_note,
        submitted_by=me.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    log_audit(db, me.email, me.id, "milestone_submitted", "milestone", str(sub.id),
              {"project_id": project_id, "title": payload.title, "flag_delay": payload.flagged_delay})
    return schemas.MilestoneSubmissionOut(
        id=sub.id, project_id=sub.project_id, title=sub.title, description=sub.description,
        budget_spent_crore=sub.budget_spent_crore, status=sub.status, flagged_delay=sub.flagged_delay,
        delay_note=sub.delay_note, submitted_at=_format_date(sub.submitted_at),
        decided_at=_format_date(sub.decided_at), decision_note=sub.decision_note, submitted_by=sub.submitted_by,
    )


@router.post("/documents", response_model=schemas.ProofDocumentOut)
def upload_proof_document(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Agency: upload a proof document against their project."""
    require_scope_project(me, project_id)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(file.filename or "document")
    path = os.path.join(UPLOAD_DIR, f"{project_id}_{int(datetime.now().timestamp())}_{safe_name}")
    with open(path, "wb") as f:
        content = file.file.read()
        f.write(content)

    doc = models.ProofDocument(
        user_id=me.id,
        project_id=project_id,
        filename=safe_name,
        stored_path=path,
        url=_shareable_url(os.path.basename(path)),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log_audit(db, me.email, me.id, "document_uploaded", "document", str(doc.id),
              {"project_id": project_id, "filename": safe_name})
    return schemas.ProofDocumentOut(
        id=doc.id, project_id=doc.project_id, filename=doc.filename, url=doc.url,
        uploaded_at=_format_date(doc.uploaded_at),
    )


@router.get("/documents/{filename}")
def serve_proof_document(
    filename: str,
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Serve an uploaded document to the owning agency user."""
    from fastapi.responses import FileResponse
    full = os.path.abspath(os.path.join(UPLOAD_DIR, os.path.basename(filename)))
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Document not found.")
    return FileResponse(full, filename=os.path.basename(filename))


@router.get("/documents", response_model=list[schemas.ProofDocumentOut])
def list_documents(
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Agency: upload history for their project."""
    project_ids = _agency_projects(me, db)
    rows = (
        db.query(models.ProofDocument)
        .filter(models.ProofDocument.project_id.in_(project_ids))
        .order_by(models.ProofDocument.uploaded_at.desc())
        .all()
    )
    return [
        schemas.ProofDocumentOut(
            id=d.id, project_id=d.project_id, filename=d.filename, url=d.url,
            uploaded_at=_format_date(d.uploaded_at),
        )
        for d in rows
    ]


@router.get("/projects/{project_id}/thread", response_model=list[schemas.MessageNoteOut])
def agency_thread(
    project_id: str,
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Agency: read ministry ↔ agency thread for their project."""
    require_scope_project(me, project_id)
    rows = db.query(models.MessageNote).filter(models.MessageNote.project_id == project_id).order_by(models.MessageNote.created_at).all()
    return [
        schemas.MessageNoteOut(
            id=n.id, project_id=n.project_id, sender_role=n.sender_role, sender_id=n.sender_id,
            text=n.text, created_at=_format_date(n.created_at),
        )
        for n in rows
    ]


@router.post("/projects/{project_id}/thread", response_model=schemas.MessageNoteOut)
def agency_post_thread(
    project_id: str,
    payload: schemas.MessageNoteIn,
    me: models.User = Depends(require_roles("agency")),
    db: Session = Depends(get_db),
):
    """Agency: reply on their project's thread."""
    require_scope_project(me, project_id)
    note = models.MessageNote(
        project_id=project_id, sender_id=me.id, sender_role=me.role, text=payload.text,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return schemas.MessageNoteOut(
        id=note.id, project_id=note.project_id, sender_role=note.sender_role, sender_id=note.sender_id,
        text=note.text, created_at=_format_date(note.created_at),
    )