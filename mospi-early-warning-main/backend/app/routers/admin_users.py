"""
Router for Admin User Management.
Admin-only endpoints: list users, assign roles/scopes, revoke access, audit logs.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth_security import (
    require_roles,
    log_audit,
    domain_allowed_for_admin,
    hash_password,
    validate_password_strength,
)
from ..phase_gate import ministry_expansion_allowed

router = APIRouter(prefix="/admin", tags=["Admin · Users & Access"])

ADMIN_ROLE_NAMES = {"admin", "ministry", "agency", "viewer"}
ELEVATED_DOMAIN_ROLES = {"admin", "ministry"}


class CreateUserRequest(BaseModel):
    email: str = Field(..., description="User email")
    name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(..., description="admin | ministry | agency | viewer")
    password: str = Field(..., min_length=1, max_length=128)
    ministry: Optional[str] = None
    agency: Optional[str] = None
    project_id: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=1, max_length=128)


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(
    role: Optional[str] = Query(None),
    status_: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: list all platform users (optionally filtered)."""
    q = db.query(models.User)
    if role:
        q = q.filter(models.User.role == role)
    if status_:
        q = q.filter(models.User.status == status_)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (models.User.email.ilike(pattern)) | (models.User.name.ilike(pattern))
        )
    users = q.order_by(models.User.id).all()
    return [schemas.UserOut.model_validate(u) for u in users]


@router.get("/users/pending", response_model=list[schemas.UserOut])
def list_pending_users(
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: users awaiting role assignment."""
    users = db.query(models.User).filter(models.User.status == "pending").order_by(models.User.id).all()
    return [schemas.UserOut.model_validate(u) for u in users]


@router.post("/users", response_model=schemas.UserOut)
def create_user(
    payload: CreateUserRequest,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: create an account with a role, scope, and initial password.

    The new user is created active and must change their password on first
    login (password_must_change=1). Emails for newly created users are still
    restricted to @gov.in / @nic.in for Admin/Ministry roles.
    """
    role = payload.role.strip().lower()
    if role not in ADMIN_ROLE_NAMES:
        raise HTTPException(status_code=400, detail=f"Invalid role '{role}'.")
    if role in ELEVATED_DOMAIN_ROLES and not domain_allowed_for_admin(payload.email):
        raise HTTPException(
            status_code=400,
            detail="Only @gov.in / @nic.in accounts can be assigned Admin or Ministry roles.",
        )
    if role in ("ministry",) and not payload.ministry:
        raise HTTPException(status_code=400, detail="A ministry must be specified for the Ministry role.")
    if role == "ministry":
        allowed, reason = ministry_expansion_allowed(db, payload.ministry)
        if not allowed:
            raise HTTPException(status_code=403, detail=f"Ministry expansion gate closed: {reason}")
    if role == "agency" and not (payload.project_id or payload.agency):
        raise HTTPException(
            status_code=400,
            detail="An agency name and/or project id must be specified for the Agency role.",
        )

    policy_error = validate_password_strength(payload.password)
    if policy_error:
        raise HTTPException(status_code=400, detail=policy_error)

    email = payload.email.strip().lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = models.User(
        email=email,
        name=payload.name.strip(),
        role=role,
        status="active",
        password_hash=hash_password(payload.password),
        password_must_change=1,
        ministry=payload.ministry,
        agency=payload.agency,
        project_id=payload.project_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(
        db,
        admin.email,
        admin.id,
        "user_created_with_password",
        "user",
        user.email,
        {"role": role, "ministry": payload.ministry, "project_id": payload.project_id},
    )
    return schemas.UserOut.model_validate(user)


@router.post("/users/{user_id}/reset-password", response_model=schemas.UserOut)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: force a user's password to a new value and require change on next login."""
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    policy_error = validate_password_strength(payload.new_password)
    if policy_error:
        raise HTTPException(status_code=400, detail=policy_error)

    target.password_hash = hash_password(payload.new_password)
    target.password_must_change = 1
    target.failed_attempts = 0
    target.account_locked_until = None
    db.commit()
    db.refresh(target)
    log_audit(
        db,
        admin.email,
        admin.id,
        "password_reset_by_admin",
        "user",
        target.email,
        {"forced_change": True},
    )
    return schemas.UserOut.model_validate(target)


@router.put("/users/{user_id}/role", response_model=schemas.UserOut)
def assign_role(
    user_id: int,
    payload: schemas.AssignRoleRequest,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: assign a role + scope (ministry / agency / project) to a user."""
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    role = payload.role.strip().lower()
    if role not in ADMIN_ROLE_NAMES:
        raise HTTPException(status_code=400, detail=f"Invalid role '{role}'.")

    if role in ELEVATED_DOMAIN_ROLES and not domain_allowed_for_admin(target.email):
        raise HTTPException(
            status_code=400,
            detail="Only @gov.in / @nic.in accounts can be assigned Admin or Ministry roles.",
        )

    if role in ("ministry",) and not payload.ministry:
        raise HTTPException(status_code=400, detail="A ministry must be specified for the Ministry role.")
    if role == "ministry":
        allowed, reason = ministry_expansion_allowed(db, payload.ministry)
        if not allowed:
            raise HTTPException(status_code=403, detail=f"Ministry expansion gate closed: {reason}")
    if role == "agency" and not (payload.project_id or payload.agency):
        raise HTTPException(
            status_code=400,
            detail="An agency name and/or project id must be specified for the Agency role.",
        )

    target.role = role
    target.status = "active"
    target.ministry = payload.ministry
    target.agency = payload.agency
    target.project_id = payload.project_id
    db.commit()
    db.refresh(target)

    log_audit(
        db,
        admin.email,
        admin.id,
        "role_assigned",
        "user",
        target.email,
        {"role": role, "ministry": payload.ministry, "project_id": payload.project_id},
    )
    return schemas.UserOut.model_validate(target)


@router.post("/users/{user_id}/revoke", response_model=schemas.UserOut)
def revoke_user(
    user_id: int,
    payload: schemas.RevokeRequest = None,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: revoke access. Revoked users cannot authenticate until reinstated."""
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot revoke your own account.")
    target.status = "revoked"
    db.commit()
    db.refresh(target)
    log_audit(
        db,
        admin.email,
        admin.id,
        "user_revoked",
        "user",
        target.email,
        {"reason": (payload.reason if payload else None)},
    )
    return schemas.UserOut.model_validate(target)


@router.post("/users/{user_id}/reinstate", response_model=schemas.UserOut)
def reinstate_user(
    user_id: int,
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: reinstate a previously revoked user to their last role."""
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.status == "revoked":
        target.status = "active"
        db.commit()
        db.refresh(target)
        log_audit(db, admin.email, admin.id, "user_reinstated", "user", target.email, {})
    return schemas.UserOut.model_validate(target)


@router.get("/audit-logs", response_model=list[schemas.AuditLogOut])
def list_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = Query(None),
    actor: Optional[str] = Query(None, description="Match the actor email"),
    entity_type: Optional[str] = Query(None),
    entity_ref: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO date; only events at or after this date"),
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: system-wide audit trail, filtered.

    Every filter is a substring match rather than an exact one, because the
    action and entity vocabularies are open-ended — an admin searching for
    "revoke" should also catch "user_revoked" and "user_reinstatement".
    """
    q = db.query(models.AuditLog)
    if action:
        q = q.filter(models.AuditLog.action.ilike(f"%{action}%"))
    if actor:
        q = q.filter(models.AuditLog.actor_email.ilike(f"%{actor}%"))
    if entity_type:
        q = q.filter(models.AuditLog.entity_type.ilike(f"%{entity_type}%"))
    if entity_ref:
        q = q.filter(models.AuditLog.entity_ref.ilike(f"%{entity_ref}%"))
    if since:
        # SQLite hands back naive datetimes, so a parsed offset-aware value
        # would never compare equal to the stored column.
        try:
            cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="`since` must be an ISO date.")
        if cutoff.tzinfo is not None:
            cutoff = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
        q = q.filter(models.AuditLog.created_at >= cutoff)
    logs = q.order_by(models.AuditLog.id.desc()).limit(limit).all()

    def fmt(dt):
        return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)

    return [
        schemas.AuditLogOut(
            id=l.id,
            actor_email=l.actor_email,
            action=l.action,
            entity_type=l.entity_type,
            entity_ref=l.entity_ref,
            details=l.details,
            created_at=fmt(l.created_at),
        )
        for l in logs
    ]


@router.get("/dashboard", response_model=schemas.AdminDashboardResponse)
def admin_dashboard(
    admin: models.User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Admin: system-wide analytics + user management summary."""
    total_users = db.query(models.User).count()
    pending_users = db.query(models.User).filter(models.User.status == "pending").count()
    revoked_users = db.query(models.User).filter(models.User.status == "revoked").count()
    active_users = db.query(models.User).filter(models.User.status == "active").count()
    role_rows = db.query(models.User.role, func.count()).group_by(models.User.role).all()
    users_by_role = {r: int(c) for r, c in role_rows}
    # Aggregate projects
    total_projects = db.query(models.Project).count()
    active_projects = db.query(models.Project).filter(models.Project.status == "Ongoing").count()

    from ..crud import get_latest_prediction_subquery
    subq = get_latest_prediction_subquery(db)
    rows = (
        db.query(
            models.Project.ministry,
            models.Prediction.composite_risk_score,
            models.Prediction.risk_tier,
            models.Prediction.cost_risk_pct,
            models.Prediction.delay_risk_months,
            models.Snapshot.cumulative_expenditure_crore,
            models.Project.original_cost_crore,
        )
        .join(subq, models.Project.project_id == subq.c.project_id)
        .join(models.Prediction,
              (models.Prediction.project_id == subq.c.project_id)
              & (models.Prediction.snapshot_month == subq.c.max_month))
        .join(models.Snapshot,
              (models.Snapshot.project_id == subq.c.project_id)
              & (models.Snapshot.snapshot_month == subq.c.max_month))
        .all()
    )

    ministries = {r[0] for r in rows}
    n = max(1, len(rows))
    delayed = sum(1 for r in rows if (r[1] or 0) >= 50)
    critical = sum(1 for r in rows if r[2] == "Critical")
    avg_risk = sum(r[1] or 0 for r in rows) / n
    avg_overrun = sum(r[3] or 0 for r in rows) / n
    total_budget = sum(r[6] or 0 for r in rows)
    spent = sum(r[5] or 0 for r in rows)
    utilized = (spent / total_budget * 100.0) if total_budget else 0.0

    return schemas.AdminDashboardResponse(
        total_users=total_users,
        pending_users=pending_users,
        active_users=active_users,
        revoked_users=revoked_users,
        users_by_role=users_by_role,
        total_ministries=len(ministries),
        total_projects=total_projects,
        active_projects=active_projects,
        delayed_projects=delayed,
        critical_projects=critical,
        avg_composite_risk=round(avg_risk, 1),
        avg_cost_overrun_pct=round(avg_overrun, 2),
        total_budget_crore=round(total_budget, 2),
        budget_utilized_pct=round(utilized, 1),
    )
