"""
Router for Public / Viewer Role.
No authentication. IMPORTANT: the read endpoints below ONLY read the
pre-filtered 'public-safe' projection table (project_public) — never the raw
projects, snapshots, predictions, remarks, documents, or communications
tables.

The single exception is POST /complaints, which is an anonymous *write*.
It exists so a visitor can report that the published data looks wrong, and
it is the only way any user-supplied value reaches the database from this
router. It therefore touches no table other than project_complaints, and it
is rate limited, category-whitelisted and honeypot-guarded.
"""

import hashlib
import os
import re
from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..geo import entity_type

# --- Satellite vegetation constants -----------------------------------------
# Kept here rather than imported from the measurement module so the read
# endpoint does not pull numpy, Pillow and the network client into a request
# path that only ever reads rows already written to the database.
VEG_LAYER = "MODIS_Terra_L3_EVI_16Day"
VEG_SOURCE_URL = "https://gibs.earthdata.nasa.gov"
VEG_RESOLUTION_M = 250

# Stated on every response and rendered by the client. A vegetation number
# with no stated resolution invites a reader to assume a precision the
# measurement does not have.
VEG_LIMITATIONS = [
    "State-level only. These are not project-level measurements: a project is "
    "located at an administrative centroid, and a ~300 m pixel around that "
    "point cannot describe a highway corridor or a site footprint.",
    "MODIS Terra EVI is a 250 m product rendered by NASA GIBS at roughly "
    "300 m per pixel. It is a genuine measurement but a coarse one.",
    "GIBS serves these layers at tile zoom 9 only, so imagery is stretched "
    "beyond that point when zoomed in further.",
    "The composites are not cloud-masked. An observation flagged as a low "
    "outlier may be cloud rather than a change on the ground; the flag marks "
    "the value for caution and does not decide the cause.",
    "Water pixels are included in the statistics, which makes coastal and "
    "island states read conservatively low. No land/water mask is applied.",
    "Lakshadweep is too small to measure at this resolution and is reported as "
    "unavailable rather than estimated.",
]
from ..auth_security import rate_limit_allowed

router = APIRouter(prefix="/public", tags=["Public"])

# The single source of truth for what a visitor may complain about. Exposed
# over GET /complaint-categories so the form cannot drift out of step with
# what this router will actually accept.
COMPLAINT_CATEGORIES = [
    {"value": "timeline", "label": "Timeline or delay looks wrong"},
    {"value": "cost", "label": "Cost or budget figure looks wrong"},
    {"value": "status", "label": "Status or milestone is out of date"},
    {"value": "location", "label": "State, sector or agency is wrong"},
    {"value": "data_quality", "label": "Typo or garbled value"},
    {"value": "funds", "label": "Fund not released or wrongly shown"},
    {"value": "other", "label": "Something else"},
]
COMPLAINT_CATEGORY_VALUES = {c["value"] for c in COMPLAINT_CATEGORIES}

# Per-process sliding window shared with the login limiter's globals, so this
# only picks the key. Keyed separately from login attempts.
COMPLAINT_RATE_KEY = "complaint"

# Deliberately lightweight: `EmailStr` would need email-validator, which is
# used by the auth router but is missing from requirements.txt. A wrong
# address here costs a single follow-up email, so a shape check is enough.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


@router.get("/projects", response_model=list[schemas.PublicProjectOut])
def public_projects(
    response: Response,
    ministry: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    on_track: Optional[int] = Query(None, description="1 = on-track, 0 = delayed"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0, description="Row offset for paging."),
    db: Session = Depends(get_db),
):
    """Public: searchable/filterable project directory (public-safe fields only).

    Paged with limit/offset, ordered by project_id so paging is stable. The
    number of rows matching the filters is returned in the ``X-Total-Count``
    header, since the body is only the current page.
    """
    q = db.query(models.ProjectPublicRow).filter(models.ProjectPublicRow.is_public_visible == 1)
    if ministry:
        q = q.filter(models.ProjectPublicRow.ministry.ilike(f"%{ministry}%"))
    if sector:
        q = q.filter(models.ProjectPublicRow.sector.ilike(f"%{sector}%"))
    if status:
        q = q.filter(models.ProjectPublicRow.status.ilike(f"%{status}%"))
    if on_track is not None:
        q = q.filter(models.ProjectPublicRow.on_track == (1 if on_track else 0))
    if search:
        pat = f"%{search}%"
        q = q.filter(
            (models.ProjectPublicRow.project_id.ilike(pat))
            | (models.ProjectPublicRow.sector.ilike(pat))
            | (models.ProjectPublicRow.ministry.ilike(pat))
        )
    response.headers["X-Total-Count"] = str(q.count())
    rows = q.order_by(models.ProjectPublicRow.project_id).limit(limit).offset(offset).all()
    return [
        schemas.PublicProjectOut(
            project_id=r.project_id,
            sector=r.sector,
            ministry=r.ministry,
            status=r.status,
            completion_percent=r.completion_percent,
            on_track=bool(r.on_track),
            risk_tier_label=r.risk_tier_label,
            public_summary=r.public_summary,
        )
        for r in rows
    ]


@router.get("/projects/{project_id}", response_model=schemas.PublicProjectOut)
def public_project_detail(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Public: single public-safe project record."""
    row = db.query(models.ProjectPublicRow).filter(
        models.ProjectPublicRow.project_id == project_id,
        models.ProjectPublicRow.is_public_visible == 1,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found in the public directory.")
    return schemas.PublicProjectOut(
        project_id=row.project_id,
        sector=row.sector,
        ministry=row.ministry,
        status=row.status,
        completion_percent=row.completion_percent,
        on_track=bool(row.on_track),
        risk_tier_label=row.risk_tier_label,
        public_summary=row.public_summary,
    )


@router.get("/summary", response_model=schemas.PublicSummaryResponse)
def public_summary(db: Session = Depends(get_db)):
    """Public: aggregate metrics derived ONLY from the public-safe table.

    Counted in SQL rather than by pulling the table into Python: the counters
    and the average are plain aggregates, so the row data itself never needs to
    leave the database.
    """
    P = models.ProjectPublicRow
    visible = P.is_public_visible == 1

    total = db.query(func.count()).select_from(P).filter(visible).scalar() or 0
    on_track = (
        db.query(func.count()).select_from(P).filter(visible, P.on_track == 1).scalar() or 0
    )
    avg_comp = db.query(func.avg(P.completion_percent)).filter(visible).scalar() or 0.0

    def counts_by(column):
        rows = (
            db.query(column, func.count())
            .filter(visible)
            .group_by(column)
            .all()
        )
        return {name: n for name, n in rows if name is not None}

    return schemas.PublicSummaryResponse(
        total_projects=total,
        on_track_count=on_track,
        delayed_count=total - on_track,
        avg_completion_percent=round(float(avg_comp), 1),
        ministry_counts=counts_by(P.ministry),
        sector_counts=counts_by(P.sector),
        status_counts=counts_by(P.status),
    )


@router.get("/ministries", response_model=schemas.MinistrySectorResponse)
def public_ministries_sectors(db: Session = Depends(get_db)):
    """Public: every ministry and sector present in the monitored portfolio.

    Counts, on-track splits and completion come from the public projection
    table, so nothing here can include a project the directory is withholding.

    Cost is the one exception: `project_public` carries no cost column, so
    `projects` is joined on `project_id` purely to read
    `original_cost_crore`. The join re-applies `is_public_visible` on the
    projection row, so a hidden project cannot contribute cost here even though
    its row is joined. The alternative -- dropping cost entirely -- would leave
    the page unable to show portfolio size at all.

    The join is an outer join on purpose. An inner join would silently drop any
    public project with no matching `projects` row, so the group counts would
    stop summing to `total_projects` without any error. There are no such rows
    today; the outer join keeps that true if one ever appears, and reports its
    cost as null.

    There is deliberately no "health" score. The source has no such measure, and
    any single number implying one would be invented.
    """
    P = models.ProjectPublicRow
    Prj = models.Project
    visible = P.is_public_visible == 1

    def _agg(column):
        """Aggregate the same population, grouped by one dimension."""
        rows = (
            db.execute(
                select(
                    column,
                    func.count(P.project_id),
                    func.sum(case((P.on_track == 1, 1), else_=0)),
                    func.avg(P.completion_percent),
                    func.sum(Prj.original_cost_crore),
                    func.count(Prj.original_cost_crore),
                )
                .select_from(P)
                .outerjoin(Prj, Prj.project_id == P.project_id)
                .filter(visible)
                .where(column.isnot(None), column != "")
                .group_by(column)
            )
            .all()
        )
        out = []
        for name, n, on_track, avg_comp, cost, cost_n in rows:
            n = int(n or 0)
            out.append(
                {
                    "name": name,
                    "project_count": n,
                    "on_track_count": int(on_track or 0),
                    "delayed_count": n - int(on_track or 0),
                    "on_track_share_percent": round(100.0 * int(on_track or 0) / n, 1)
                    if n
                    else 0.0,
                    # Null, not 0.0, when no project in the group reports a cost:
                    # "no cost data" and "costs nothing" are different claims.
                    "total_original_cost_crore": round(float(cost), 1)
                    if cost_n
                    else None,
                    "avg_completion_percent": round(float(avg_comp), 1)
                    if avg_comp is not None
                    else None,
                }
            )
        return out

    ministries = _agg(P.ministry)
    sectors = _agg(P.sector)

    # Composition of each ministry, so a card can name the sectors it spans.
    pairs = (
        db.execute(
            select(P.ministry, P.sector, func.count(P.project_id))
            .select_from(P)
            .filter(visible)
            .where(P.ministry.isnot(None), P.sector.isnot(None))
            .group_by(P.ministry, P.sector)
        )
        .all()
    )
    children: dict[str, set] = {}
    for ministry, sector, _n in pairs:
        if ministry and sector:
            children.setdefault(ministry, set()).add(sector)
    for m in ministries:
        m["child_sectors"] = sorted(children.get(m["name"], set()))

    # Sort by portfolio size, then name, so the order is stable across requests
    # and the biggest portfolio is first without hardcoding a rank.
    for item in ministries:
        item["kind"] = "ministry"
    for item in sectors:
        item["kind"] = "sector"
    ministries.sort(key=lambda m: (-m["project_count"], m["name"]))
    sectors.sort(key=lambda s: (-s["project_count"], s["name"]))

    total = db.query(func.count()).select_from(P).filter(visible).scalar() or 0
    grouped = sum(m["project_count"] for m in ministries)
    costed_projects = (
        db.execute(
            select(func.count(Prj.original_cost_crore))
            .select_from(P)
            .outerjoin(Prj, Prj.project_id == P.project_id)
            .filter(visible)
        ).scalar()
        or 0
    )

    return schemas.MinistrySectorResponse(
        ministries=[schemas.MinistrySectorOut(**m) for m in ministries],
        sectors=[schemas.MinistrySectorOut(**s) for s in sectors],
        total_projects=int(total),
        total_ministries=len(ministries),
        total_sectors=len(sectors),
        # Projects with no ministry or sector named. Zero in the current data,
        # but returned so the page can prove the group counts account for
        # everything instead of assuming they do.
        unattributed_projects=int(total) - grouped,
        cost_coverage_percent=round(100.0 * int(costed_projects) / int(total), 1)
        if total
        else 0.0,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/geo/states", response_model=schemas.StateGeoResponse)
def public_state_geo(db: Session = Depends(get_db)):
    """Public: state-level figures for the map, from the public projection.

    Reads through `ProjectPublicRow` on the same `is_public_visible` filter as
    every other public endpoint, so a state count can never include a project
    the directory is withholding.

    The figures are per state because that is the resolution the source data
    supports. 225 of 2,185 projects name no single state, and they are returned
    in `unplaced` rather than dropped: silently omitting them would understate
    every state's share of the portfolio and make the choropleth look complete
    when it covers about 89% of it.
    """
    P = models.ProjectPublicRow
    G = models.ProjectGeo
    visible = P.is_public_visible == 1

    rows = (
        db.query(
            G.state,
            G.state_code,
            G.lat,
            G.lon,
            G.precision,
            func.count(P.project_id),
            func.sum(case((P.on_track == 1, 1), else_=0)),
            func.avg(P.completion_percent),
        )
        .select_from(P)
        .join(G, G.project_id == P.project_id)
        .filter(visible)
        .group_by(G.state, G.state_code, G.lat, G.lon, G.precision)
        .all()
    )

    states = [
        schemas.StateGeoOut(
            state=state,
            state_code=code,
            entity_type=entity_type(state),
            lat=lat,
            lon=lon,
            precision=precision or "none",
            project_count=int(count or 0),
            on_track_count=int(on_track or 0),
            delayed_count=int(count or 0) - int(on_track or 0),
            avg_completion_percent=round(float(avg_comp or 0.0), 1),
        )
        for state, code, lat, lon, precision, count, on_track, avg_comp in rows
        if lat is not None
    ]
    states.sort(key=lambda s: (-s.project_count, s.state))

    unplaced = [
        schemas.StateGeoBucketOut(bucket=bucket, project_count=int(n or 0))
        for bucket, n in db.query(G.state, func.count(P.project_id))
        .select_from(P)
        .join(G, G.project_id == P.project_id)
        .filter(visible, G.lat.is_(None))
        .group_by(G.state)
        .all()
    ]
    unplaced.sort(key=lambda b: -b.project_count)

    total = db.query(func.count()).select_from(P).filter(visible).scalar() or 0
    # Sum of the per-state buckets: every project with a single-state
    # attribution. Named to match the response field so the arithmetic cannot
    # be misread as counting real project locations.
    attributed = sum(s.project_count for s in states)

    return schemas.StateGeoResponse(
        states=states,
        unplaced=unplaced,
        total_projects=total,
        state_attributed_projects=attributed,
        state_attributed_share_percent=(
            round(100.0 * attributed / total, 1) if total else 0.0
        ),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/geo/vegetation", response_model=schemas.VegetationResponse)
def state_vegetation(
    date: str | None = Query(
        None,
        description="Acquisition date as YYYY-MM-DD. Defaults to the most "
                    "recent acquisition held locally.",
    ),
    trend: bool = Query(
        True,
        description="Include each state's series across all held acquisitions.",
    ),
    db: Session = Depends(get_db),
):
    """Per-state satellite vegetation, one row per acquisition.

    This is a real measurement, and it is deliberately kept at state
    resolution. Nothing here is joined to a project: a project's location is a
    single administrative centroid, and a 300 m pixel around that point cannot
    describe a highway corridor or a mine footprint. The endpoint is shaped so
    that a client cannot present it as per-project monitoring by accident.

    An unknown or unavailable date falls back to the most recent acquisition
    that exists locally, and the date actually used is returned as
    ``selected_date``. Silently returning a different date than the one asked
    for would be the kind of quiet substitution that makes a time series
    untrustworthy.
    """
    from ..models import StateVegetation

    available = db.execute(
        select(
            StateVegetation.acquisition_date,
            func.count(StateVegetation.id),
            func.sum(case((StateVegetation.low_outlier.is_(True), 1), else_=0)),
        )
        .where(StateVegetation.status == "ok")
        .group_by(StateVegetation.acquisition_date)
        .order_by(StateVegetation.acquisition_date)
    ).all()

    date_list = [
        schemas.VegetationDateOut(
            acquisition_date=r[0],
            states_measured=r[1],
            low_outlier_count=int(r[2] or 0),
            is_latest=(idx == len(available) - 1),
        )
        for idx, r in enumerate(available)
    ]

    if not date_list:
        return schemas.VegetationResponse(
            source_layer=VEG_LAYER,
            source_url=VEG_SOURCE_URL,
            resolution_m=VEG_RESOLUTION_M,
            dates=[],
            selected_date=None,
            states=[],
            trends=[],
            limitations=VEG_LIMITATIONS,
            generated_at=datetime.now(timezone.utc),
        )

    # Resolve the requested date against what is actually held.
    selected = None
    requested_note = None
    if date:
        try:
            parsed = date_cls.fromisoformat(date)
        except ValueError:
            parsed = None
        if parsed is not None and any(d.acquisition_date == parsed for d in date_list):
            selected = parsed
        else:
            requested_note = (
                f"no observation held for {date}; showing the most recent "
                f"acquisition instead"
            )
    if selected is None:
        selected = date_list[-1].acquisition_date

    rows = db.execute(
        select(StateVegetation, models.ProjectGeo.state_code)
        .outerjoin(
            models.ProjectGeo,
            (models.ProjectGeo.state == StateVegetation.state)
            & (models.ProjectGeo.state.isnot(None)),
        )
        .where(
            StateVegetation.acquisition_date == selected,
            StateVegetation.status == "ok",
        )
        .distinct()
    ).all()

    state_codes = {
        g.state: g.state_code
        for g in db.execute(
            select(models.ProjectGeo.state, models.ProjectGeo.state_code)
        ).all()
        if g.state
    }

    states = []
    for veg, _ in rows:
        states.append(schemas.StateVegetationOut(
            state=veg.state,
            state_code=state_codes.get(veg.state),
            entity_type=entity_type(veg.state),
            acquisition_date=veg.acquisition_date,
            evi_median=veg.evi_median,
            evi_mean=veg.evi_mean,
            evi_p10=veg.evi_p10,
            evi_p90=veg.evi_p90,
            ndvi_median=veg.ndvi_median,
            valid_pixel_fraction=veg.valid_pixel_fraction,
            tiles_sampled=veg.tiles_sampled,
            low_outlier=bool(veg.low_outlier),
            outlier_z=veg.outlier_z,
            # Fall back to a derived explanation when the row carries none, so
            # a flagged observation can never reach a reader as a bare warning
            # badge with no reason attached.
            outlier_note=veg.outlier_note or (
                f"{veg.evi_median:.3f} is far below the national figure for "
                f"{veg.acquisition_date}. Cause not determined: could be cloud, "
                f"or genuinely sparse vegetation."
                if veg.low_outlier and veg.evi_median is not None else None
            ),
            resolution_m=veg.resolution_m,
            source_layer=veg.source_layer,
        ))

    # Guard against one state appearing twice if it has several project rows.
    seen = set()
    states = [s for s in states
              if not (s.state in seen or seen.add(s.state))]
    states.sort(key=lambda s: (-(s.evi_median if s.evi_median is not None else -9),
                               s.state))

    trends: list[schemas.StateVegetationTrendOut] = []
    if trend and len(date_list) > 1:
        series = db.execute(
            select(StateVegetation)
            .where(StateVegetation.status == "ok")
            .order_by(StateVegetation.state, StateVegetation.acquisition_date)
        ).scalars().all()
        by_state: dict[str, list] = {}
        for row in series:
            by_state.setdefault(row.state, []).append(row)

        for state_name, items in by_state.items():
            pts = [
                schemas.VegetationTrendPoint(
                    acquisition_date=i.acquisition_date,
                    evi_median=i.evi_median,
                    ndvi_median=i.ndvi_median,
                    low_outlier=bool(i.low_outlier),
                )
                for i in items
            ]
            usable = [p.evi_median for p in pts if p.evi_median is not None]
            change = round(usable[-1] - usable[0], 4) if len(usable) > 1 else None
            per_month = None
            if len(usable) > 1 and len(pts) > 1:
                days = (pts[-1].acquisition_date - pts[0].acquisition_date).days
                if days > 0:
                    per_month = round(change * 30.0 / days, 4)
            trends.append(schemas.StateVegetationTrendOut(
                state=state_name,
                points=pts,
                change_over_series=change,
                change_per_month=per_month,
            ))
        trends.sort(key=lambda t: (t.change_per_month
                                   if t.change_per_month is not None else 0.0))

    limitations = list(VEG_LIMITATIONS)
    if requested_note:
        limitations.insert(0, requested_note)
    if len(date_list) < 3:
        limitations.append(
            f"only {len(date_list)} acquisition(s) held locally; trends are "
            f"indicative and will firm up as more dates are measured"
        )

    return schemas.VegetationResponse(
        source_layer=VEG_LAYER,
        source_url=VEG_SOURCE_URL,
        resolution_m=VEG_RESOLUTION_M,
        dates=date_list,
        selected_date=selected,
        states=states,
        trends=trends,
        limitations=limitations,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/ministries", response_model=list[str])
def public_ministries(db: Session = Depends(get_db)):
    """Public: list of ministries visible in the public directory.

    Filtered on ``is_public_visible`` like every other public read. Without it
    this leaks the ministries of unpublished projects, which the projection
    table exists specifically to withhold.
    """
    rows = (
        db.query(models.ProjectPublicRow.ministry)
        .filter(models.ProjectPublicRow.is_public_visible == 1)
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0]})


@router.get("/sectors", response_model=list[str])
def public_sectors(db: Session = Depends(get_db)):
    """Public: list of sectors visible in the public directory."""
    rows = (
        db.query(models.ProjectPublicRow.sector)
        .filter(models.ProjectPublicRow.is_public_visible == 1)
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0]})


@router.get("/complaint-categories")
def public_complaint_categories():
    """Public: the category list the report form renders.

    Served from the backend rather than hardcoded in the frontend so the form
    can never offer a category this router would then reject.
    """
    return COMPLAINT_CATEGORIES


@router.post("/complaints", response_model=schemas.ComplaintReceipt, status_code=201)
def submit_public_complaint(
    payload: schemas.ComplaintIn,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Public: report that a project's published data looks wrong.

    The only anonymous write in the API. Three defences, because an endpoint
    anyone can post to is a spam target:

    - rate limited per source address, reusing the login limiter's sliding
      window under its own key so the two cannot exhaust each other;
    - category and project both checked against what the portal actually
      publishes, so the endpoint cannot be used to attach invented project
      ids to the table;
    - a honeypot field. A filled honeypot is discarded and still answered
      201, so an automated submitter learns nothing from the response.
    """
    ip = request.client.host if request and request.client else "unknown"

    if not rate_limit_allowed(f"{COMPLAINT_RATE_KEY}|{ip}"):
        raise HTTPException(
            status_code=429,
            detail="Too many reports sent. Please wait a minute and try again.",
        )

    # Honeypot: answer as though it worked, store nothing.
    if payload.website:
        return schemas.ComplaintReceipt(reference="MOSPI-000000")

    if payload.category not in COMPLAINT_CATEGORY_VALUES:
        raise HTTPException(
            status_code=400,
            detail="Choose one of the listed categories.",
        )

    email = (payload.reporter_email or "").strip() or None
    if email and not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="That email address does not look valid.")

    # Only projects the portal actually publishes can be complained about, so
    # the endpoint cannot be used to invent project references.
    project = (
        db.query(models.ProjectPublicRow)
        .filter(
            models.ProjectPublicRow.project_id == payload.project_id,
            models.ProjectPublicRow.is_public_visible == 1,
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail="That project is not in the public directory.",
        )

    complaint = models.ProjectComplaint(
        project_id=project.project_id,
        category=payload.category,
        subject=(payload.subject or "").strip() or None,
        description=payload.description.strip(),
        reporter_email=email.lower() if email else None,
        # Salted so the same address cannot be recovered by hashing the
        # digest again; the raw address is never stored.
        reporter_ip_hash=hashlib.sha256(
            f"{os.getenv('JWT_SECRET', 'mospi')}|{ip}".encode("utf-8")
        ).hexdigest(),
        status="new",
    )
    db.add(complaint)
    db.commit()

    # No audit row: the audit trail is an administrative record of who did
    # what, and an anonymous report has no actor to attribute. The complaint
    # row itself is the record, and admin actions on it are audited.
    return schemas.ComplaintReceipt(reference=f"MOSPI-{complaint.id:06d}")