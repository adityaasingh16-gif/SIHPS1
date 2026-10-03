import logging

logger = logging.getLogger('auth')
"""
Router for Authentication & Identity.
Google OAuth 2.0 (Sign in with Google), public self-registration with password,
JWT session issuance, and current-user introspection.
"""

import base64
import json
import os
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth_security import (
    AUTH_DEMO_MODE,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    FRONTEND_URL,
    AUTH_SUPERADMIN_EMAILS,
    MAX_FAILED_ATTEMPTS,
    issue_user_token,
    verify_google_id_token,
    hash_password,
    verify_password,
    validate_password_strength,
    is_account_locked,
    register_failed_login,
    reset_login_failures,
    rate_limit_allowed,
    get_payload,
    get_current_user,
    log_audit,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

ALLOWED_INTENTS = ("enterprise", "public")


class PublicRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class PublicLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class PendingUserOut(schemas.UserOut):
    pending: bool = True


@router.get("/status", tags=["Authentication"])
def auth_status():
    """Public, non-secret readiness flags used to avoid sending users into a broken login flow."""
    return {"google_login_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
            "demo_login_enabled": AUTH_DEMO_MODE}


def _encode_state(obj: dict) -> str:
    raw = json.dumps(obj).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_state(state: Optional[str]) -> dict:
    if not state:
        return {}
    try:
        pad = "=" * (-len(state) % 4)
        return json.loads(base64.urlsafe_b64decode(state + pad).decode("utf-8"))
    except Exception:
        return {}


def _google_auth_url(intent: str) -> str:
    state = _encode_state({"intent": intent, "nonce": secrets.token_hex(8)})
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def _exchange_code_for_token(code: str) -> Optional[dict]:
    """Exchange the OAuth code for tokens at Google's token endpoint."""
    try:
        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=20.0,
        )
        if resp.status_code != 200:
            logger.error(f"Google token exchange failed: HTTP {resp.status_code} - {resp.text}")
            return None
        return resp.json()
    except Exception as exc:
        logger.error(f"Exception during Google token exchange: {exc}", exc_info=True)
        return None


class DemoLoginRequest(BaseModel):
    role: str = Field(..., description="admin | ministry | agency | contractor | viewer | citizen")


@router.post("/demo-login", response_model=schemas.LoginResponse, tags=["Authentication"])
def demo_login_endpoint(payload: DemoLoginRequest, db: Session = Depends(get_db)):
    req_role = payload.role.strip().lower()
    if req_role not in {"admin", "ministry", "agency", "contractor", "viewer", "citizen"}:
        raise HTTPException(status_code=400, detail="Unknown demo role.")
    role_email_map = {
        "admin": "admin@gov.in",
        "ministry": "ministry@gov.in",
        "contractor": "contractor@gov.in",
        "agency": "contractor@gov.in",
        "viewer": "citizen@gov.in",
        "citizen": "citizen@gov.in",
    }
    email = role_email_map.get(req_role, "admin@gov.in")
    user = db.query(models.User).filter(models.User.email == email).first()
    initial_pw = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip() or "Admin@12345"
    pw_hash = hash_password(initial_pw)
    if not user:
        role_specs = {
            "admin": {"name": "Platform Administrator", "role": "admin", "ministry": None, "agency": None, "project_id": None},
            "ministry": {"name": "MoRTH Ministry Officer", "role": "ministry", "ministry": "Ministry of Road Transport & Highways", "agency": None, "project_id": None},
            "contractor": {"name": "NHAI Project Contractor", "role": "agency", "ministry": None, "agency": "National Highways Authority of India [NHAI]", "project_id": "701392"},
            "agency": {"name": "NHAI Implementing Agency", "role": "agency", "ministry": None, "agency": "National Highways Authority of India [NHAI]", "project_id": "701392"},
            "viewer": {"name": "Citizen / Public Analyst", "role": "viewer", "ministry": None, "agency": None, "project_id": None},
            "citizen": {"name": "Citizen / Public Analyst", "role": "viewer", "ministry": None, "agency": None, "project_id": None},
        }
        spec = role_specs.get(req_role, role_specs["admin"])
        user = models.User(
            email=email,
            name=spec["name"],
            role=spec["role"],
            ministry=spec.get("ministry"),
            agency=spec.get("agency"),
            project_id=spec.get("project_id"),
            status="active",
            password_hash=pw_hash,
            created_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.status = "active"
        if not user.password_hash:
            user.password_hash = pw_hash
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
    token = issue_user_token(user)
    return schemas.LoginResponse(token=token, user=schemas.UserOut.model_validate(user))


@router.get("/google/login", tags=["Authentication"])
def google_login_redirect(
    intent: str = Query("enterprise", description="enterprise (default) | public"),
    db: Session = Depends(get_db),
):
    """Redirect to Google OAuth; never issue an unauthenticated fallback session."""
    if intent not in ALLOWED_INTENTS:
        raise HTTPException(status_code=400, detail="intent must be 'enterprise' or 'public'.")
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on the backend.",
        )
    return RedirectResponse(_google_auth_url(intent), status_code=302)


@router.get("/google/callback", tags=["Authentication"])
def google_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Google redirects here after consent. Exchanges the code, verifies the ID token
    server-side, upserts the user, and redirects to the frontend with a freshly
    issued session token. Users signing in with intent=public are activated as
    viewers immediately; all other new users are created as pending.
    """
    intent = _decode_state(state).get("intent", "enterprise")
    if error == "access_denied":
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_cancelled", status_code=302)
    if not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_failed", status_code=302)

    tokens = _exchange_code_for_token(code)
    if not tokens or "id_token" not in tokens:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=token_exchange_failed", status_code=302)

    claims = verify_google_id_token(tokens["id_token"])
    if claims is None:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=verification_failed", status_code=302)
    if not claims.get("email_verified", False):
        return RedirectResponse(f"{FRONTEND_URL}/login?error=email_unverified", status_code=302)

    email = claims["email"]
    user = db.query(models.User).filter(
        (models.User.email == email) | (models.User.google_sub == claims.get("google_sub"))
    ).first()

    if user is None:
        if intent == "public":
            user = models.User(
                google_sub=claims.get("google_sub"),
                email=email,
                name=claims.get("name") or email.split("@")[0],
                avatar_url=claims.get("picture"),
                role="viewer",
                status="active",
                created_at=datetime.now(timezone.utc),
            )
            created_label = "user_registered_public_google"
        else:
            user = models.User(
                google_sub=claims.get("google_sub"),
                email=email,
                name=claims.get("name") or email.split("@")[0],
                avatar_url=claims.get("picture"),
                role="pending",
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            created_label = "user_created_google"
        db.add(user)
        db.commit()
        db.refresh(user)
        log_audit(db, email, user.id, created_label, "user", email, {"source": "google"})
    else:
        user.google_sub = user.google_sub or claims.get("google_sub")
        user.avatar_url = claims.get("picture") or user.avatar_url
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)

    # Bootstrap admin: Google accounts listed in AUTH_SUPERADMIN_EMAILS own the platform.
    promoted = False
    if email.lower() in AUTH_SUPERADMIN_EMAILS:
        if user.role != "admin" or user.status != "active":
            user.role = "admin"
            user.status = "active"
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(user)
            promoted = True
            log_audit(db, email, user.id, "role_promoted_superadmin", "user", email, {})

    token = issue_user_token(user)
    if user.status == "pending":
        return RedirectResponse(f"{FRONTEND_URL}/login?pending=1&token={token}", status_code=302)
    if user.status == "revoked":
        return RedirectResponse(f"{FRONTEND_URL}/login?revoked=1&token={token}", status_code=302)
    return RedirectResponse(f"{FRONTEND_URL}?token={token}", status_code=302)


@router.post("/register", response_model=schemas.LoginResponse, tags=["Authentication"])
def public_register(payload: PublicRegisterRequest, db: Session = Depends(get_db)):
    """Lightweight self-registration for public (citizen) accounts.

    A new public account is created active ('viewer') immediately — no admin
    approval needed. Government roles (Admin/Ministry/Agency) are still gated
    behind admin creation / role assignment.
    """
    policy_error = validate_password_strength(payload.password)
    if policy_error:
        raise HTTPException(status_code=400, detail=policy_error)

    email = payload.email.lower()
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = models.User(
        email=email,
        name=payload.name.strip(),
        role="viewer",
        status="active",
        password_hash=hash_password(payload.password),
        created_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(db, email, user.id, "user_registered_public", "user", email, {})
    token = issue_user_token(user)
    return schemas.LoginResponse(token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.LoginResponse, tags=["Authentication"])
def public_login(
    payload: PublicLoginRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Password sign-in for all accounts (public viewers and gov roles).

    Enforces brute-force protection: sliding-window rate limiting per
    email/IP, and per-account lockout after MAX_FAILED_ATTEMPTS.
    """
    email = payload.email.lower()
    ip = request.client.host if request and request.client else "unknown"
    logger.info(f"Login attempt for email={email} from ip={ip}")

    if not rate_limit_allowed(f"{email}|{ip}"):
        logger.warning(f"Rate limit exceeded for {email} ({ip})")
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait a minute and try again.")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        logger.warning(f"Login failed: User not found for email={email}")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.password_hash or not verify_password(payload.password, user.password_hash):
        logger.warning(f"Login failed: Invalid password for email={email}")
        if register_failed_login(db, user):
            raise HTTPException(
                status_code=423,
                detail=f"Account locked after {MAX_FAILED_ATTEMPTS} failed attempts. Try again later.",
            )
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if user.status == "revoked":
        logger.warning(f"Login rejected: Account revoked for email={email}")
        raise HTTPException(status_code=403, detail="Access revoked. Contact your administrator.")

    if is_account_locked(user):
        logger.warning(f"Login rejected: Account locked for email={email}")
        raise HTTPException(status_code=423, detail="Account is temporarily locked. Try again later.")

    reset_login_failures(db, user)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    token = issue_user_token(user)
    logger.info(f"User successfully logged in: email={email}, role={user.role}")
    log_audit(db, email, user.id, "user_logged_in_password", "user", email, {})
    return schemas.LoginResponse(token=token, user=schemas.UserOut.model_validate(user))


@router.post("/change-password", response_model=schemas.LoginResponse, tags=["Authentication"])
def change_password(
    payload: schemas.ChangePasswordRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password.

    Enforces the portal password policy and clears the forced-password-change
    flag. Returns a fresh token (old ones stay valid only until expiry).
    """
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    policy_error = validate_password_strength(payload.new_password)
    if policy_error:
        raise HTTPException(status_code=400, detail=policy_error)

    user.password_hash = hash_password(payload.new_password)
    user.password_must_change = 0
    db.commit()
    db.refresh(user)
    log_audit(db, user.email, user.id, "password_changed", "user", user.email, {})
    token = issue_user_token(user)
    return schemas.LoginResponse(token=token, user=schemas.UserOut.model_validate(user))


@router.get("/me", response_model=schemas.AuthStatusResponse, tags=["Authentication"])
def auth_me(
    payload: dict = Depends(get_payload),
    db: Session = Depends(get_db),
):
    """Current session user from JWT."""
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        user_id = 0
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return schemas.AuthStatusResponse(authenticated=False, message="unknown_user")
    out = schemas.UserOut.model_validate(user)
    return schemas.AuthStatusResponse(
        authenticated=user.status == "active",
        user=out,
        pending=user.status == "pending",
        message={
            "pending": "Awaiting Admin Approval",
            "active": "Active",
            "revoked": "Access Revoked",
        }.get(user.status, user.status),
    )


@router.post("/logout", tags=["Authentication"])
def logout():
    """Stateless logout: client discards token. Provided for completeness."""
    return {"status": "logged_out"}
