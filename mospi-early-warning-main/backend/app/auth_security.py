"""
Security & Access Control for MoSPI Dhrishti.

Implements:
  - Google Sign-In (OAuth 2.0) with server-side ID token verification
  - Own JWT session tokens embedding role + scope
  - Role & scope guard dependencies for FastAPI routes
  - Domain restriction policy (@gov.in / @nic.in for admin/ministry roles)
"""

import os
import json
import time
import hmac
import hashlib
import base64
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, List

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from . import models

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
IS_PRODUCTION = (
    os.getenv("APP_ENV", "").strip().lower() == "production"
    or os.getenv("RENDER", "").strip().lower() == "true"
)

# Production backend on Render is sihps1-3.onrender.com; fallback to it if not configured
_DEFAULT_REDIRECT_URI = (
    "https://sihps1-3.onrender.com/auth/google/callback"
    if IS_PRODUCTION
    else "http://127.0.0.1:8000/auth/google/callback"
)
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT_URI).strip()
# Auto-correct legacy/inactive Render URL if provided in environment
if "sihps1.onrender.com" in GOOGLE_REDIRECT_URI and "sihps1-3.onrender.com" not in GOOGLE_REDIRECT_URI:
    GOOGLE_REDIRECT_URI = GOOGLE_REDIRECT_URI.replace("sihps1.onrender.com", "sihps1-3.onrender.com")

_DEFAULT_FRONTEND_URL = (
    "https://sihps-1.vercel.app" if IS_PRODUCTION else "http://localhost:5173"
)
FRONTEND_URL = os.getenv("FRONTEND_URL", _DEFAULT_FRONTEND_URL).strip()
if IS_PRODUCTION and ("localhost" in FRONTEND_URL or "127.0.0.1" in FRONTEND_URL):
    FRONTEND_URL = "https://sihps-1.vercel.app"

_DEV_JWT_SECRET = "dev-secret-change-me-in-production-mospi-ew"
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if not JWT_SECRET:
    JWT_SECRET = os.getenv("SECRET_KEY", "").strip() or _DEV_JWT_SECRET
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

# Whether to allow demo (password-less) login for evaluation and review
AUTH_DEMO_MODE = os.getenv("AUTH_DEMO_MODE", "true").lower() in ("1", "true", "yes")
# Seed a default admin at startup (default to true so admin@gov.in is always created)
AUTH_SEED_ADMIN = os.getenv("AUTH_SEED_ADMIN", "true").lower() in ("1", "true", "yes")
# Google sign-in emails auto-promoted to Admin (Active) on first login — bootstraps the first admin.
AUTH_SUPERADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv("AUTH_SUPERADMIN_EMAILS", "").split(",") if e.strip()
}

ADMIN_ROLES = {"admin", "ministry", "agency", "viewer"}

# --- Password policy ---
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "10"))
PASSWORD_REQUIRE_UPPER = True
PASSWORD_REQUIRE_LOWER = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = True

# --- Account lockout policy ---
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))

bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Minimal JWT implementation (no external signing lib needed beyond stdlib)
# ---------------------------------------------------------------------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_jwt(payload: Dict) -> str:
    """Issue a signed JWT session token."""
    header = {"alg": JWT_ALGO, "typ": "JWT"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    hdr = json.dumps(header, separators=(",", ":")).encode("utf-8")
    signing_input = _b64url(hdr) + "." + _b64url(body)
    sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    token = signing_input + "." + _b64url(sig)
    return token


def verify_jwt(token: str) -> Optional[Dict]:
    """Verify JWT signature + expiry. Returns payload or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = parts[0] + "." + parts[1]
        expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(parts[2])):
            return None
        payload = json.loads(_b64url_decode(parts[1]))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def issue_user_token(user: "models.User") -> str:
    """Build + sign a JWT embedding identity, role, and scope."""
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "ministry": user.ministry,
        "project_id": user.project_id,
        "agency": user.agency,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
    }
    return create_jwt(payload)


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256) for public self-registration
# ---------------------------------------------------------------------------

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """Hash a password with a fresh random salt (format: pbkdf2_sha256$iter$salt$digest)."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a password against a stored hash."""
    try:
        _algo, iterations, salt, expected = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """Enforce the portal password policy. Returns an error message or None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if PASSWORD_REQUIRE_UPPER and not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if PASSWORD_REQUIRE_LOWER and not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter."
    if PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return "Password must contain at least one digit."
    if PASSWORD_REQUIRE_SPECIAL and not any(not c.isalnum() for c in password):
        return "Password must contain at least one special character (e.g. !@#$%)."
    return None


def is_account_locked(user: "models.User") -> bool:
    """True if the account is currently in a lockout window."""
    if not user.account_locked_until:
        return False
    try:
        expiry = user.account_locked_until
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry.replace(" ", "T"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > datetime.now(timezone.utc)
    except Exception:
        return False


def register_failed_login(db: Session, user: "models.User") -> bool:
    """Increment failed-attempt counter; lock the account when the threshold is hit."""
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        from datetime import timedelta
        user.account_locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        user.failed_attempts = 0
        db.commit()
        db.refresh(user)
        log_audit(db, user.email, user.id, "account_locked", "user", user.email,
                  {"attempts": MAX_FAILED_ATTEMPTS, "lockout_minutes": LOCKOUT_MINUTES})
        return True
    db.commit()
    db.refresh(user)
    return False


def reset_login_failures(db: Session, user: "models.User") -> None:
    """Clear failed-attempt counters on a successful login."""
    if user.failed_attempts or user.account_locked_until:
        user.failed_attempts = 0
        user.account_locked_until = None
        db.commit()
        db.refresh(user)


# --- Login rate limiting (in-memory, per email + per IP) ---
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_PER_WINDOW = 10
_rate_buckets: Dict[str, list] = {}


def rate_limit_allowed(key: str) -> bool:
    """Sliding-window rate limiter keyed by 'email|ip'. Returns True if allowed."""
    now = time.time()
    bucket = _rate_buckets.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW_SECONDS]
    if len(bucket) >= _RATE_MAX_PER_WINDOW:
        return False
    bucket.append(now)
    return True


# ---------------------------------------------------------------------------
# Google ID token verification (server-side)
# ---------------------------------------------------------------------------

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_certs_cache: Dict = {"fetched_at": 0.0, "certs": None}


def _fetch_google_certs() -> Dict:
    if _certs_cache["certs"] and (time.time() - _certs_cache["fetched_at"]) < 3600:
        return _certs_cache["certs"]
    try:
        resp = httpx.get(GOOGLE_CERTS_URL, timeout=10.0)
        certs = resp.json()
        _certs_cache["certs"] = certs
        _certs_cache["fetched_at"] = time.time()
        return certs
    except Exception:
        return _certs_cache["certs"] or {"keys": []}


def verify_google_id_token(id_token: str) -> Optional[Dict]:
    """
    Verify a Google ID token signature and claims server-side.
    Returns claims dict (email, sub, name, picture) or None if invalid.
    """
    try:
        parts = id_token.split(".")
        if len(parts) != 3:
            return None
        header = json.loads(_b64url_decode(parts[0]))
        kid = header.get("kid")
        certs = _fetch_google_certs()
        key = next((k for k in certs.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            return None
        # Verify RS256 signature using the certificate n/e exponents
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
        import jwt as pyjwt

        # Build public key from JWK
        n = int(base64.urlsafe_b64decode(key["n"] + "=" * (-len(key["n"]) % 4)).hex(), 16)
        e = int(base64.urlsafe_b64decode(key["e"] + "=" * (-len(key["e"]) % 4)).hex(), 16)
        pub = rsa.RSAPublicNumbers(e, n).public_key(default_backend())

        claims = pyjwt.decode(
            id_token,
            key=pub,
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
            options={"verify_exp": True},
        )
        issuer = claims.get("iss")
        allowed = {"accounts.google.com", "https://accounts.google.com"}
        if issuer not in allowed:
            return None
        if not GOOGLE_CLIENT_ID:
            return None
        return {
            "google_sub": claims.get("sub"),
            "email": claims.get("email"),
            "name": claims.get("name") or "",
            "picture": claims.get("picture"),
            "email_verified": claims.get("email_verified", False),
        }
    except Exception:
        return None


def domain_allowed_for_admin(email: str) -> bool:
    """Optional restriction: only @gov.in / @nic.in eligible for Admin/Ministry roles."""
    domain = (email.rsplit("@", 1)[-1] if "@" in email else "").lower()
    return domain in ("gov.in", "nic.in")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def read_token(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if credentials is None:
        return None
    return credentials.credentials


def get_payload(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Optional[Dict]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_jwt(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token invalid or expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def get_current_user(
    payload: Dict = Depends(get_payload),
    db: Session = Depends(get_db),
) -> "models.User":
    """Resolve the authenticated user from the JWT payload, enforcing active status."""
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        user_id = 0
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    if user.status == "revoked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access revoked. Contact your administrator.")
    if user.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is still awaiting role assignment by an administrator.",
            headers={"X-Auth-Pending": "true"},
        )
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assigned to your account.")
    return user


def require_roles(*roles: str):
    """Dependency factory: require the current user to hold one of the given roles."""
    allowed = set(roles)

    def _guard(user: "models.User" = Depends(get_current_user)) -> "models.User":
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires role: {', '.join(sorted(allowed))}.",
            )
        return user

    return _guard


def require_scope_project(user: "models.User", project_id: str) -> None:
    """Entitlement check: an agency user may only act on assigned project(s)."""
    if user.role == "agency" and user.project_id and project_id != user.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your assigned project.",
        )


def require_scope_ministry(user: "models.User", project: "models.Project") -> None:
    """Entitlement check: a ministry user may only access own ministry projects."""
    if user.role == "ministry" and user.ministry and project.ministry != user.ministry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access projects under your ministry.",
        )


def log_audit(
    db: Session,
    actor_email: Optional[str],
    user_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_ref: Optional[str] = None,
    details: Optional[Dict] = None,
):
    """Write an audit log row."""
    db.add(
        models.AuditLog(
            actor_email=actor_email,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_ref=entity_ref,
            details=details,
        )
    )
    db.commit()


def seed_default_admin(db: Session) -> None:
    """Create the bootstrap admin account on first run (AUTH_SEED_ADMIN).

    The initial password comes from ADMIN_INITIAL_PASSWORD (env) so the very
    first admin can sign in with email/password; the account forces a password
    change on first login. If a legacy admin exists without a password hash
    (pre-hardening seed), it is retrofitted with the initial password instead.
    """
    initial_pw = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip() or "Admin@12345"
    existing = db.query(models.User).filter(models.User.email == "admin@gov.in").first()
    if existing:
        if not existing.password_hash:
            existing.password_hash = hash_password(initial_pw)
            existing.password_must_change = 1
            existing.failed_attempts = 0
            existing.account_locked_until = None
            db.commit()
        return
    admin = models.User(
        email="admin@gov.in",
        name="Platform Administrator",
        role="admin",
        status="active",
        password_hash=hash_password(initial_pw),
        password_must_change=1,
        created_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(admin)
    db.commit()
    log_audit(db, "admin@gov.in", admin.id, "admin_bootstrapped", "user", str(admin.id),
              {"note": "Default admin created. Force password change on first login."})

# cache JWT_SECRET hash to avoid schema drift
_JWT_KID = hashlib.sha256(JWT_SECRET.encode("utf-8")).hexdigest()[:8]
