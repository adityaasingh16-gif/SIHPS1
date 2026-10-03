"""
Router for Active Alerts Endpoint (Endpoint 9).
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="", tags=["Alerts"])

@router.get("/alerts", response_model=List[schemas.AlertItem])
def get_active_alerts(db: Session = Depends(get_db)):
    """
    Endpoint 9: GET /alerts
    Returns projects with increasing risk trends or tier boundary transitions.
    """
    return crud.get_alerts(db)
