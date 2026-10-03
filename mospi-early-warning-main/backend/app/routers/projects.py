"""
Router for Project Retrieval Endpoints (Endpoints 1-6).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=List[schemas.ProjectSummary])
def get_projects(
    response: Response,
    ministry: Optional[str] = Query(None, description="Filter by ministry"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    risk_tier: Optional[List[str]] = Query(None, description="Filter by risk tier (multi)"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    search: Optional[str] = Query(None, description="Search query across ID, sector, ministry, agency"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Page size. Omit to return every match."),
    offset: int = Query(0, ge=0, description="Row offset; use with limit to page."),
    sort: str = Query("risk", pattern="^(risk|cost|project_id)$", description="risk = composite risk desc (default), cost = highest sanctioned-or-revised cost, project_id."),
    db: Session = Depends(get_db)
):
    """
    Endpoint 1: GET /projects
    Returns list of projects joined with their LATEST prediction, ordered by
    composite risk score (highest first) unless `sort` says otherwise.

    Paged with limit/offset, with project_id as a tie-breaker so paging is
    stable when two projects share a score. The total number of matches is
    returned in the ``X-Total-Count`` header. Omitting ``limit`` returns every
    match, which is retained for existing callers but should be avoided by new
    ones.
    """
    projects = crud.get_projects(db, ministry, sector, risk_tier, status, search, limit, offset, sort)
    if limit is not None:
        response.headers["X-Total-Count"] = str(crud.count_projects(db, ministry, sector, risk_tier, status, search))
    return projects

@router.get("/{project_id}", response_model=schemas.ProjectDetail)
def get_project_by_id(project_id: str, db: Session = Depends(get_db)):
    """
    Endpoint 2: GET /projects/{project_id}
    Returns full project detail + latest prediction + SHAP drivers + remarks tags + suggested review text.
    """
    detail = crud.get_project_detail(db, project_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found."
        )
    return detail

@router.get("/{project_id}/history", response_model=List[schemas.RiskHistoryPoint])
def get_project_history(project_id: str, db: Session = Depends(get_db)):
    """
    Endpoint 3: GET /projects/{project_id}/history
    Returns time-series risk trajectory across all snapshots.
    """
    history = crud.get_project_history(db, project_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No snapshot history found for project '{project_id}'."
        )
    return history

@router.get("/{project_id}/explanation", response_model=schemas.ProjectExplanationResponse)
def get_project_explanation(project_id: str, db: Session = Depends(get_db)):
    """
    Endpoint 4: GET /projects/{project_id}/explanation
    Returns top SHAP risk drivers and mitigating factors for the latest snapshot.
    """
    explanation = crud.get_project_explanation(db, project_id)
    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No prediction explanation found for project '{project_id}'."
        )
    return explanation

@router.get("/{project_id}/similar", response_model=List[schemas.SimilarProjectItem])
def get_similar_projects(project_id: str, db: Session = Depends(get_db)):
    """
    Endpoint 5: GET /projects/{project_id}/similar
    Returns 3-5 similar projects based on sector, cost band, and duration.
    """
    similar = crud.get_similar_projects(db, project_id, limit=4)
    return similar

@router.get("/{project_id}/dependencies", response_model=List[schemas.DependencyItem])
def get_project_dependencies(project_id: str, db: Session = Depends(get_db)):
    """
    Endpoint 6: GET /projects/{project_id}/dependencies
    Returns list of related projects with their current risk status.
    """
    deps = crud.get_project_dependencies(db, project_id)
    return deps
