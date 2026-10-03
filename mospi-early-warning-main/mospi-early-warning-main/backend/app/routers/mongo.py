"""
Router for optional MongoDB mirror endpoints (storage + compression layer).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..mongo_store import mongo_status, mirror_snapshot

router = APIRouter(prefix="/mongo", tags=["MongoDB Mirror"])


@router.get("/status")
def get_mongo_status():
    """GET /mongo/status — whether the MongoDB mirror is configured and connected."""
    return mongo_status()


@router.post("/mirror")
def post_mongo_mirror(db: Session = Depends(get_db)):
    """POST /mongo/mirror — copy the current SQLite data snapshot into MongoDB."""
    return mirror_snapshot(db)