"""
Live Risk Factor status endpoint.

GET /risk/status  -> when the rolling risk-sync last ran, cadence, and a
summary of what changed so the UI can show "risk refreshed X minutes ago".
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..risk_sync import get_sync_status

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status")
def risk_status(db: Session = Depends(get_db)):
    return get_sync_status(db)