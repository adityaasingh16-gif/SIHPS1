"""
SQLAlchemy ORM Table Definitions for MoSPI Dhrishti Early-Warning Platform.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, Date, DateTime,
    ForeignKey, UniqueConstraint, JSON, Boolean
)
from sqlalchemy.orm import relationship
from .database import Base

class Project(Base):
    """Primary Project entity table."""
    __tablename__ = "projects"

    project_id = Column(String(50), primary_key=True, index=True)
    sector = Column(String(100), nullable=False, index=True)
    ministry = Column(String(150), nullable=False, index=True)
    implementing_agency = Column(String(100), nullable=False)
    original_cost_crore = Column(Float, nullable=False)
    original_duration_months = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    planned_completion_date = Column(Date, nullable=False)
    status = Column(String(50), nullable=False, default="Ongoing", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    snapshots = relationship("Snapshot", back_populates="project", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="project", cascade="all, delete-orphan")
    remarks_signals = relationship("RemarkSignal", back_populates="project", cascade="all, delete-orphan")
    dependencies = relationship("ProjectDependency", foreign_keys="ProjectDependency.project_id", back_populates="project", cascade="all, delete-orphan")


class Snapshot(Base):
    """Point-in-time monthly project snapshot table."""
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_month = Column(Integer, nullable=False)
    reporting_date = Column(Date, nullable=False)
    physical_progress_pct = Column(Float, nullable=False)
    financial_progress_pct = Column(Float, nullable=False)
    cumulative_expenditure_crore = Column(Float, nullable=False)
    latest_revised_cost_crore = Column(Float, nullable=False)
    milestones_planned = Column(Integer, nullable=False)
    milestones_achieved = Column(Integer, nullable=False)
    remarks_text = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_month", name="uq_snapshot_project_month"),
    )

    project = relationship("Project", back_populates="snapshots")


class Prediction(Base):
    """ML model output prediction record for a specific project snapshot."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_month = Column(Integer, nullable=False)
    cost_risk_pct = Column(Float, nullable=False)              # predicted % cost escalation
    cost_overrun_probability = Column(Float, nullable=False)   # calibrated probability
    delay_risk_months = Column(Float, nullable=False)          # predicted delay in months
    delay_probability = Column(Float, nullable=False)         # calibrated probability
    composite_risk_score = Column(Float, nullable=False, index=True)  # 0-100 scale
    risk_tier = Column(String(20), nullable=False, index=True) # Critical | High | Medium | Low
    risk_trend = Column(String(20), nullable=False, default="stable") # increasing | stable | decreasing
    model_version = Column(String(50), nullable=False, default="v1.0.0")
    predicted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_month", name="uq_prediction_project_month"),
    )

    project = relationship("Project", back_populates="predictions")
    shap_explanations = relationship("SHAPExplanation", back_populates="prediction", cascade="all, delete-orphan")


class SHAPExplanation(Base):
    """Feature attribution drivers per prediction."""
    __tablename__ = "shap_explanations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    factor_name = Column(String(100), nullable=False)
    impact_value = Column(Float, nullable=False)              # positive = increases risk, negative = decreases
    direction = Column(String(30), nullable=False)             # "increases_risk" | "decreases_risk"
    rank = Column(Integer, nullable=False)                     # 1 = most important

    prediction = relationship("Prediction", back_populates="shap_explanations")


class RemarkSignal(Base):
    """Structured NLP warning tags extracted from remarks_text."""
    __tablename__ = "remarks_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_month = Column(Integer, nullable=False)
    tag = Column(String(100), nullable=False)                  # e.g. "Land Issue", "Approval Pending"
    confidence = Column(Float, nullable=True, default=0.9)

    project = relationship("Project", back_populates="remarks_signals")


class ProjectDependency(Base):
    """Project cascade and dependency relations graph table."""
    __tablename__ = "project_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    related_project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(50), nullable=False)        # e.g. "shared_contractor", "shared_agency"

    project = relationship("Project", foreign_keys=[project_id], back_populates="dependencies")


class OfficerOptimizationRun(Base):
    """Audit log table for officer capacity optimization runs."""
    __tablename__ = "officer_optimization_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    available_hours = Column(Float, nullable=False)
    selected_project_ids = Column(JSON, nullable=False)        # JSON array of project_ids
    total_risk_mitigated = Column(Float, nullable=False)


# ---------------------------------------------------------------------------
# Identity & Access Management (Google OAuth-backed RBAC)
# ---------------------------------------------------------------------------

class User(Base):
    """Platform user created after Google sign-in; role assigned by an Admin."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_sub = Column(String(200), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    avatar_url = Column(String(512), nullable=True)
    password_hash = Column(String(255), nullable=True)  # PBKDF2 for public self-registration
    role = Column(String(30), nullable=False, default="pending")  # admin|ministry|agency|viewer|pending
    status = Column(String(30), nullable=False, default="pending")  # pending|active|revoked
    ministry = Column(String(150), nullable=True)                # scoping for ministry role
    agency = Column(String(150), nullable=True)                  # scoping for agency role
    project_id = Column(String(50), nullable=True)               # scoping for agency role
    password_must_change = Column(Integer, nullable=False, default=0)  # force password change on next login
    failed_attempts = Column(Integer, nullable=False, default=0)       # consecutive failed logins
    account_locked_until = Column(DateTime, nullable=True)             # lockout expiry timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """System-wide audit trail for administrative and role actions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    actor_email = Column(String(255), nullable=True)
    action = Column(String(120), nullable=False)                 # e.g. role_assigned, user_revoked
    entity_type = Column(String(60), nullable=True)              # user|project|milestone|approval
    entity_ref = Column(String(120), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MilestoneSubmission(Base):
    """Agency-submitted milestone/budget update awaiting ministry approval."""
    __tablename__ = "milestone_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    budget_spent_crore = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending|approved|rejected
    flagged_delay = Column(Integer, nullable=False, default=0)   # anticipated delay months (0 = none)
    delay_note = Column(Text, nullable=True)
    submitted_by = Column(Integer, nullable=True)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    decided_by = Column(Integer, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(Text, nullable=True)

    project = relationship("Project")


class ProofDocument(Base):
    """Uploaded proof/document attached by an agency user."""
    __tablename__ = "proof_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id = Column(Integer, nullable=True)
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=True)
    url = Column(String(512), nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project")


class SystemMeta(Base):
    """Key/value system metadata (e.g. live risk-sync bookkeeping)."""
    __tablename__ = "system_meta"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self):  # pragma: no cover
        return f"<SystemMeta {self.key}={self.value!r}>"


class ProjectPublicRow(Base):
    """PUBLIC-SAFE projection of project data. Public routes ONLY read this table,
    never the raw projects/snapshots/predictions tables."""
    __tablename__ = "project_public"

    project_id = Column(String(50), primary_key=True, index=True)
    is_public_visible = Column(Integer, nullable=False, default=1)
    sector = Column(String(100), nullable=False)
    ministry = Column(String(150), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="Ongoing")
    completion_percent = Column(Float, nullable=False, default=0.0)
    on_track = Column(Integer, nullable=False, default=1)        # 1 = on-track, 0 = delayed
    risk_tier_label = Column(String(30), nullable=True)          # derived, coarse label only
    public_summary = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MessageNote(Base):
    """Project-scoped communication thread between ministry and agency users."""
    __tablename__ = "message_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, nullable=True)
    sender_role = Column(String(30), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project")


class ProjectComplaint(Base):
    """Public report of a suspected data problem against a project listing.

    Deliberately has NO foreign key to `projects`. Every other project-scoped
    table cascades from it, but a re-seed clears the project tables
    (`_clear_project_tables`) and the public projection is rebuilt on every
    boot, so a cascade would silently destroy the very reports an
    administrator needs in order to correct the underlying data. A complaint
    that outlives the row it disputes is the point.

    `reporter_email` is optional: the portal must accept an anonymous report,
    and requiring an address would depress submission for no benefit.
    `reporter_ip_hash` is a salted SHA-256, never the raw address, so repeated
    submissions from one source can be spotted during abuse triage without
    storing the address itself.
    """
    __tablename__ = "project_complaints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), nullable=False, index=True)
    category = Column(String(50), nullable=False)   # whitelisted in public.py
    subject = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    reporter_email = Column(String(255), nullable=True)
    reporter_ip_hash = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="new", index=True)  # new|reviewing|resolved|rejected
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


class ProjectGeo(Base):
    """Where a project sits, at the only resolution the source data supports.

    Kept in its own table instead of as a column on `Project` for three
    reasons. `create_all` creates missing tables but never alters an existing
    one, so a new column would silently not appear on a deployed database. The
    public projection is rebuilt on every boot and a re-seed rebuilds
    `Project`, so location belongs with the seedable reference data rather
    than on the row it would be wiped with. And geography is genuinely
    optional here: 225 of 2,185 projects name no single state, and those rows
    must be representable without pretending they have a point.

    `lat`/`lon` are an administrative centroid, never a project site. The
    source data carries no coordinates, so a point here positions a
    state-level figure on a map. `precision` records which, and the map reads
    it rather than hardcoding a zoom level.

    `footprint_geojson` is reserved for the next step: once a project has a
    real boundary, per-site satellite comparison becomes meaningful. It is
    NULL for every project today.
    """
    __tablename__ = "project_geo"

    project_id = Column(String(50), primary_key=True, index=True)
    # Canonical name from `geo.STATE_REFERENCE`, or one of the explicit
    # non-place buckets: "Multi-State", "Offshore", "PAN India", "Unspecified".
    state = Column(String(60), nullable=False, index=True)
    state_code = Column(String(2), nullable=True, index=True)   # ISO 3166-2:IN
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    # "state" = administrative centroid, the only level available today.
    precision = Column(String(20), nullable=False, default="state")
    # Number of states a Multi-State project spans, for honest disclosure.
    member_count = Column(Integer, nullable=True)
    footprint_geojson = Column(Text, nullable=True)
    geo_source = Column(String(30), nullable=False, default="panel_csv")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class StateVegetation(Base):
    """Satellite vegetation index per state, per acquisition.

    This is the honest extent of satellite monitoring this platform can
    currently claim. It is a real measurement from a real instrument, taken
    from the NASA GIBS keyless service: MODIS Terra EVI, a 16-day composite of
    the Enhanced Vegetation Index at roughly 250 m.

    It is measured per *state*, not per project. A project's location is a
    single administrative centroid, and a 250 m pixel around that point says
    nothing about a highway corridor or a mine. The values here are reported
    as regional context and are deliberately never joined to a project row as
    though they described it.

    `valid_pixel_fraction` is stored because it is the number a reader needs in
    order to judge the measurement. A mean taken over 20% of a tile is a much
    weaker observation than one taken over 95%, and a cloud-obscured state
    that still shows a confident-looking average is the failure mode this
    column exists to prevent.

    `tiles_sampled` records how many GIBS tiles contributed, because a state
    assembled from one tile and one assembled from nine are not equally
    reliable and the figure should be visible rather than implied.
    """
    __tablename__ = "state_vegetation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String(60), nullable=False, index=True)
    acquisition_date = Column(Date, nullable=False, index=True)
    # Mean and median over valid pixels. Median is used for the headline
    # figure because a 250 m EVI field is heavily skewed by a single water
    # body or bare patch, which drags a mean around.
    evi_mean = Column(Float, nullable=True)
    evi_median = Column(Float, nullable=True)
    evi_p10 = Column(Float, nullable=True)
    evi_p90 = Column(Float, nullable=True)
    # Second index from the same instrument and date. Its purpose is to give
    # the cloud check something independent to disagree with.
    ndvi_median = Column(Float, nullable=True)
    valid_pixel_fraction = Column(Float, nullable=True)
    tiles_sampled = Column(Integer, nullable=True)
    # "MODIS_Terra_L3_EVI_16Day" or whatever served the observation.
    source_layer = Column(String(60), nullable=False)
    resolution_m = Column(Integer, nullable=True)   # nominal, metres
    # Set when a state could not be measured, with the reason. A gap is
    # reported rather than filled.
    status = Column(String(20), nullable=False, default="ok")  # ok|no_data|error
    # Set by a robust cross-state check. This never removes an observation; it
    # records that the value sits far below every other state on the same
    # date. The cause is deliberately left undecided - a low outlier may be
    # cloud, or it may be a genuinely arid state such as Ladakh, and this
    # table cannot tell the two apart.
    low_outlier = Column(Boolean, nullable=False, default=False)
    outlier_z = Column(Float, nullable=True)
    outlier_note = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("state", "acquisition_date", "source_layer",
                         name="uq_state_veg_state_date_layer"),
    )
