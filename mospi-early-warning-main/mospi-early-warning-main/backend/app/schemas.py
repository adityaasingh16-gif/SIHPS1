"""
Pydantic Schemas for Request Validation and Response Serialization.
Matches exact shape expected by the frontend components.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- SHAP & Explainability Schemas ---
class SHAPItem(BaseModel):
    factor_name: str
    impact_value: float
    direction: str  # "increases_risk" | "decreases_risk"
    rank: int
    feature_name: Optional[str] = None
    shap_value: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context: Any) -> None:
        if self.feature_name is None:
            self.feature_name = self.factor_name
        if self.shap_value is None:
            self.shap_value = self.impact_value

class ProjectExplanationResponse(BaseModel):
    project_id: str
    snapshot_month: int
    composite_risk_score: float
    risk_tier: str
    top_risk_drivers: List[SHAPItem]
    mitigating_factors: List[SHAPItem]
    explanation_summary: str

# --- Dependency & Similar Projects Schemas ---
class DependencyItem(BaseModel):
    related_project_id: str
    relation_type: str
    risk_tier: str
    composite_risk_score: float

    model_config = ConfigDict(from_attributes=True)

class SimilarProjectItem(BaseModel):
    project_id: str
    sector: str
    original_cost_crore: float
    original_duration_months: int
    composite_risk_score: float
    risk_tier: str
    similarity_score: float

    model_config = ConfigDict(from_attributes=True)

# --- Project Summary & Detail Schemas ---
_MISSING_SENTINELS = {"nan", "none", "null", "na", "n/a", "-", "unknown"}

def normalize_agency(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    """Coerce a raw implementing-agency value into a real agency name.

    Upstream sources (pandas/CSV exports) leak missing-value sentinels such as
    the string "nan" or a float NaN, which would otherwise be persisted and
    served to the UI as a literal "nan" agency. Falls back to `fallback`
    (normally the parent ministry) whenever the value is effectively missing.
    """
    if value is None:
        candidate = None
    elif isinstance(value, float):
        # float('nan') is the only float that is not equal to itself
        candidate = None if value != value else str(value)
    else:
        candidate = str(value)
    if candidate is not None:
        candidate = candidate.strip()
        if not candidate or candidate.lower() in _MISSING_SENTINELS:
            candidate = None
    if candidate is not None:
        return candidate
    if fallback is not None:
        fallback = str(fallback).strip()
        if fallback and fallback.lower() not in _MISSING_SENTINELS:
            return fallback
    return None

class ProjectSummary(BaseModel):
    project_id: str
    sector: str
    ministry: str
    implementing_agency: str

    @field_validator("implementing_agency", mode="before")
    @classmethod
    def _clean_agency(cls, v: Any, info) -> str:
        # `ministry` is declared above, so it is available in info.data for the fallback
        cleaned = normalize_agency(v, (info.data or {}).get("ministry"))
        return cleaned or "Unknown"
    original_cost_crore: float
    original_duration_months: int
    start_date: str
    planned_completion_date: str
    status: str
    composite_risk_score: float
    risk_tier: str
    cost_risk_pct: float
    cost_overrun_probability: float
    delay_risk_months: float
    delay_probability: float
    risk_trend: str
    latest_snapshot_month: Optional[int] = None
    cumulative_expenditure_crore: Optional[float] = None
    latest_revised_cost_crore: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class ProjectDetail(ProjectSummary):
    latest_snapshot_month: int
    physical_progress_pct: float
    financial_progress_pct: float
    cumulative_expenditure_crore: float
    milestones_planned: int
    milestones_achieved: int
    schedule_pressure_score: Optional[float] = None
    remarks_text: Optional[str] = None
    top_risk_drivers: List[SHAPItem] = []
    mitigating_factors: List[SHAPItem] = []
    extracted_tags: List[str] = []
    suggested_review: str = ""
    similar_projects: List[SimilarProjectItem] = []
    dependencies: List[DependencyItem] = []

    model_config = ConfigDict(from_attributes=True)

# --- History Trajectory Schema ---
class RiskHistoryPoint(BaseModel):
    snapshot_month: int
    reporting_date: str
    composite_risk_score: float
    cost_risk_pct: float
    delay_risk_months: float
    physical_progress_pct: float
    planned_progress_pct: float

    model_config = ConfigDict(from_attributes=True)

# --- What-If Simulation Schemas ---
class SimulationRequest(BaseModel):
    resolve_land_issue: bool = False
    resolve_approval_bottleneck: bool = False
    milestones_to_close: int = Field(0, ge=0, le=100, description="Number of milestones to close")

class SimulationResponse(BaseModel):
    project_id: str
    current_risk_score: float
    simulated_risk_score: float
    delta: float
    current_risk_tier: str
    simulated_risk_tier: str
    simulation_notes: str

# --- Officer Optimization Schemas ---
class OptimizeQueueRequest(BaseModel):
    available_hours: float = Field(..., gt=0, le=100000.0, description="Available officer review hours")

class OptimizedProjectItem(BaseModel):
    project_id: str
    sector: str
    ministry: str
    composite_risk_score: float
    risk_tier: str
    required_review_hours: float
    risk_reduction_impact: float
    unresolved_land_issues: int
    unresolved_approval_issues: int
    remarks_text: str

class OptimizeQueueResponse(BaseModel):
    run_id: str
    run_at: str
    available_hours: float
    total_hours_allocated: float
    capacity_utilization_pct: float
    total_risk_mitigated: float
    n_projects_selected: int
    total_candidates: int
    selected_projects_queue: List[OptimizedProjectItem]

# --- Alerts Schema ---
class AlertItem(BaseModel):
    id: str
    project_id: str
    severity: str  # "Critical" | "High" | "Warning"
    message: str
    alert_type: str  # "trend_increasing" | "tier_boundary_crossed"
    composite_risk_score: float
    risk_tier: str
    timestamp: str

# --- Model Comparison Schema ---
class TaskMetricItem(BaseModel):
    task: str
    model: str
    mae: Optional[float] = None
    rmse: Optional[float] = None
    r2: Optional[float] = None
    roc_auc: Optional[float] = None
    f1: Optional[float] = None
    recall: Optional[float] = None

class ModelComparisonResponse(BaseModel):
    cuf_only_metrics: List[TaskMetricItem]
    enhanced_data_metrics: List[TaskMetricItem]
    comparison_summary: str

# --- Seed Response Schema ---
class SeedDatabaseResponse(BaseModel):
    status: str
    message: str
    projects_seeded: int
    snapshots_seeded: int
    predictions_seeded: int
    shap_records_seeded: int
    models_saved_to: str

# --- Identity & Access Management Schemas ---
class UserOut(BaseModel):
    id: int
    email: str
    name: str
    avatar_url: Optional[str] = None
    role: str
    status: str
    ministry: Optional[str] = None
    agency: Optional[str] = None
    project_id: Optional[str] = None
    password_must_change: bool = False
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

    @field_validator("created_at", "last_login_at", mode="before")
    @classmethod
    def _fmt_dt(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return str(v)

    @field_validator("password_must_change", mode="before")
    @classmethod
    def _fmt_bool(cls, v):
        return bool(v)

    model_config = ConfigDict(from_attributes=True)

class AssignRoleRequest(BaseModel):
    role: str = Field(..., description="admin | ministry | agency | viewer")
    ministry: Optional[str] = None
    agency: Optional[str] = None
    project_id: Optional[str] = None

class RevokeRequest(BaseModel):
    reason: Optional[str] = None

class LoginResponse(BaseModel):
    token: str
    user: UserOut

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)

class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: Optional[UserOut] = None
    pending: bool = False
    message: str = ""

class AuditLogOut(BaseModel):
    id: int
    actor_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_ref: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Milestone / Agency Submission Schemas ---
class MilestoneSubmissionIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    budget_spent_crore: Optional[float] = Field(None, ge=0)
    flagged_delay: int = Field(0, ge=0, le=120, description="Anticipated delay in months")
    delay_note: Optional[str] = Field(None, max_length=1000)

class MilestoneSubmissionOut(BaseModel):
    id: int
    project_id: str
    title: str
    description: Optional[str] = None
    budget_spent_crore: Optional[float] = None
    status: str
    flagged_delay: int
    delay_note: Optional[str] = None
    submitted_at: Optional[str] = None
    decided_at: Optional[str] = None
    decision_note: Optional[str] = None
    submitted_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class DecisionRequest(BaseModel):
    approve: bool
    note: Optional[str] = None

class ProofDocumentOut(BaseModel):
    id: int
    project_id: str
    filename: str
    url: Optional[str] = None
    uploaded_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class MessageNoteIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

class MessageNoteOut(BaseModel):
    id: int
    project_id: str
    sender_role: Optional[str] = None
    sender_id: Optional[int] = None
    text: str
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Public-Safe Schemas (never expose raw project internals) ---
class PublicProjectOut(BaseModel):
    project_id: str
    sector: str
    ministry: str
    status: str
    completion_percent: float
    on_track: bool
    risk_tier_label: Optional[str] = None
    public_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class PublicSummaryResponse(BaseModel):
    total_projects: int
    on_track_count: int
    delayed_count: int
    avg_completion_percent: float
    ministry_counts: Dict[str, int]
    sector_counts: Dict[str, int]
    status_counts: Dict[str, int]


# --- Geography Schemas ---
class StateGeoOut(BaseModel):
    """One state on the map, with figures for the public directory.

    ``lat``/``lon`` are the administrative centroid, never a project site, and
    ``precision`` says so. A client that draws these as project pins would be
    misrepresenting the resolution of the data, which is why the field is
    carried rather than assumed.
    """
    state: str
    state_code: Optional[str] = None
    entity_type: str = "n/a"   # "State" | "Union Territory" | "n/a"
    lat: Optional[float] = None
    lon: Optional[float] = None
    precision: str = "none"
    project_count: int = 0
    on_track_count: int = 0
    delayed_count: int = 0
    avg_completion_percent: float = 0.0


class StateGeoBucketOut(BaseModel):
    """A state-level count of projects that have no single location.

    These are surfaced rather than hidden. A project marked `Multi-State` is
    not missing data to be quietly dropped from a choropleth total; dropping it
    would make the state's share of the portfolio look smaller than it is.
    """
    bucket: str
    project_count: int


class MinistrySectorOut(BaseModel):
    """Aggregated portfolio for one ministry or sector.

    Every figure is computed from the public projection table, so a visitor and
    a signed-in officer see the same numbers. `on_track_share_percent` is the
    share of that group's projects flagged on_track, not a score invented for
    the card; there is no "health" metric in the source data.
    """

    name: str
    kind: str  # "ministry" or "sector"
    project_count: int = 0
    on_track_count: int = 0
    delayed_count: int = 0
    on_track_share_percent: float = 0.0
    # Sum of original cost, in INR crore, from the projects table. Null when the
    # source carries no cost for the group rather than reported as zero.
    total_original_cost_crore: Optional[float] = None
    avg_completion_percent: Optional[float] = None
    # The sectors a ministry spans, so a card can show its own composition.
    # Empty for a sector row.
    child_sectors: List[str] = []


class MinistrySectorResponse(BaseModel):
    ministries: List[MinistrySectorOut]
    sectors: List[MinistrySectorOut]
    # Portfolio-wide totals, so the page can state the denominator instead of
    # leaving the reader to infer it from a column of cards.
    total_projects: int = 0
    total_ministries: int = 0
    total_sectors: int = 0
    # Groups whose project count or cost is unavailable, reported rather than
    # silently dropped.
    unattributed_projects: int = 0
    cost_coverage_percent: float = 0.0
    generated_at: datetime


class StateGeoResponse(BaseModel):
    states: List[StateGeoOut]
    unplaced: List[StateGeoBucketOut]
    total_projects: int
    # Projects attributable to exactly one state. Deliberately not called
    # "located": these carry a state's administrative centroid, not a site.
    # 1,947 attributed projects collapse to 35 distinct points, so a reader
    # must not infer 1,947 known project locations from this number.
    state_attributed_projects: int
    # Share of visible projects with a single-state attribution. This is a
    # choropleth coverage figure, not a survey-completeness figure.
    state_attributed_share_percent: float = 0.0
    generated_at: datetime

# --- Role Dashboard Schemas ---
class MinistryDashboardResponse(BaseModel):
    ministry: str
    total_projects: int
    active_projects: int
    delayed_projects: int
    pending_approvals: int
    avg_composite_risk: float
    budget_total_crore: float
    budget_utilized_pct: float
    projects: List[ProjectSummary] = []
    milestones: List[MilestoneSubmissionOut] = []
    alerts: List[AlertItem] = []
    chart_budget: List[Dict[str, Any]] = []
    chart_risk: List[Dict[str, Any]] = []

class AgencyDashboardResponse(BaseModel):
    project_id: str
    project_detail: Optional[ProjectDetail] = None
    milestones: List[MilestoneSubmissionOut] = []
    uploads: List[ProofDocumentOut] = []
    thread: List[MessageNoteOut] = []

class AdminDashboardResponse(BaseModel):
    total_users: int
    pending_users: int
    active_users: int
    revoked_users: int
    users_by_role: Dict[str, int]
    total_ministries: int
    total_projects: int
    active_projects: int
    delayed_projects: int
    critical_projects: int
    avg_composite_risk: float
    avg_cost_overrun_pct: float
    total_budget_crore: float
    budget_utilized_pct: float
    system_uptime: int = 0

# --- Admin Operations Schemas (platform governance) ---

class PublicRowAdminOut(BaseModel):
    """A public-directory row as an admin sees it: visibility flag included."""
    project_id: str
    sector: str
    ministry: str
    status: str
    completion_percent: float
    on_track: bool
    risk_tier_label: Optional[str] = None
    public_summary: Optional[str] = None
    is_public_visible: bool
    updated_at: Optional[str] = None


class PublicRowUpdate(BaseModel):
    """Partial update. Omitted fields are left untouched."""
    is_public_visible: Optional[bool] = None
    public_summary: Optional[str] = Field(None, max_length=1000)


class SystemMetaOut(BaseModel):
    key: str
    value: Optional[str] = None
    updated_at: Optional[str] = None


class DataOpsStatus(BaseModel):
    models_loaded: bool
    table_counts: Dict[str, int]
    meta: List[SystemMetaOut] = []


class ModelArtifactOut(BaseModel):
    name: str
    size_bytes: int
    modified_at: Optional[str] = None
    loaded_in_memory: bool = False


class ModelHealthOut(BaseModel):
    models_loaded: bool
    extra_models_loaded: bool
    model_dir: str
    artifacts: List[ModelArtifactOut] = []
    comparison_metrics_available: bool = False
    rag_index_available: bool = False


class RemarkSignalOut(BaseModel):
    id: int
    project_id: str
    ministry: Optional[str] = None
    sector: Optional[str] = None
    snapshot_month: int
    tag: str
    confidence: Optional[float] = None


class MessageNoteAdminOut(BaseModel):
    id: int
    project_id: str
    sender_id: Optional[int] = None
    sender_email: Optional[str] = None
    sender_role: Optional[str] = None
    text: str
    created_at: Optional[str] = None


class ProofDocumentAdminOut(BaseModel):
    id: int
    project_id: str
    milestone_id: Optional[int] = None
    filename: str
    url: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[str] = None


# --- Public project complaints (report an issue) ---

class ComplaintIn(BaseModel):
    """A public report of a suspected data problem.

    `website` is a honeypot: it must stay empty, and is never read by a human.
    A value means an automated submitter filled the hidden field, in which
    case the router discards the report and still answers success so the bot
    gets no signal that it was caught.
    """
    project_id: str = Field(..., min_length=1, max_length=50)
    category: str = Field(..., min_length=1, max_length=50)
    subject: Optional[str] = Field(None, max_length=255)
    description: str = Field(..., min_length=10, max_length=4000)
    reporter_email: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=255)


class ComplaintReceipt(BaseModel):
    """What the anonymous submitter is told. Deliberately excludes any detail
    about whether the report was accepted as valid, so it cannot be used to
    probe the moderation rules."""
    reference: str
    received: bool = True


class ComplaintAdminOut(BaseModel):
    id: int
    project_id: str
    ministry: Optional[str] = None
    category: str
    subject: Optional[str] = None
    description: str
    reporter_email: Optional[str] = None
    status: str
    admin_note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None


class ComplaintStatusUpdate(BaseModel):
    """Partial update of a complaint's triage state."""
    status: Optional[str] = Field(None, min_length=1, max_length=20)
    admin_note: Optional[str] = Field(None, max_length=2000)


# --- Satellite vegetation schemas ---
# These describe MODIS vegetation indices measured per state from the NASA
# GIBS keyless service. They are deliberately structured so a client cannot
# present them as anything project-level: there is no project identifier
# anywhere in this group of schemas, and the scope is stated on every
# response.


class StateVegetationOut(BaseModel):
    """One state's vegetation observation for a single acquisition."""
    state: str
    state_code: Optional[str] = None
    entity_type: str = "n/a"
    acquisition_date: date
    # Headline figure is the median of per-tile medians: robust to a single
    # water body or bare patch inside the state.
    evi_median: Optional[float] = None
    evi_mean: Optional[float] = None
    evi_p10: Optional[float] = None
    evi_p90: Optional[float] = None
    # Second index, same instrument and date, used to cross-check the first.
    ndvi_median: Optional[float] = None
    # Share of sampled pixels that carried a usable value. A state observed
    # through a gap in the mosaic is a weaker measurement and the reader is
    # entitled to know that.
    valid_pixel_fraction: Optional[float] = None
    tiles_sampled: Optional[int] = None
    # Set when the value sits far below every other state on this date. The
    # cause is not determined by these data; it may be cloud or it may be a
    # genuinely arid state.
    low_outlier: bool = False
    outlier_z: Optional[float] = None
    outlier_note: Optional[str] = None
    resolution_m: Optional[int] = None
    source_layer: str


class VegetationDateOut(BaseModel):
    """One available acquisition, for the date selector."""
    acquisition_date: date
    states_measured: int
    low_outlier_count: int
    is_latest: bool = False


class VegetationTrendPoint(BaseModel):
    acquisition_date: date
    evi_median: Optional[float] = None
    ndvi_median: Optional[float] = None
    low_outlier: bool = False


class StateVegetationTrendOut(BaseModel):
    """A state's series across the acquisitions held locally."""
    state: str
    points: List[VegetationTrendPoint]
    # Change in EVI between the first and last acquisition held. Sign is
    # meaningful, magnitude is small at 300 m and should be read as a
    # direction rather than a precise quantity.
    change_over_series: Optional[float] = None
    # Same figure expressed in index points per month, so a 2-point series is
    # not visually comparable with a 6-point one.
    change_per_month: Optional[float] = None


class VegetationResponse(BaseModel):
    source_layer: str
    source_url: str
    instrument: str = "MODIS Terra"
    resolution_m: int
    # GIBS serves these layers at one tile level only, so the imagery is
    # stretched beyond that point. Said here rather than left for a reader to
    # discover when it blurs.
    max_natural_zoom: int = 9
    dates: List[VegetationDateOut]
    selected_date: Optional[date] = None
    states: List[StateVegetationOut] = []
    trends: List[StateVegetationTrendOut] = []
    # The honest limits of this measurement, sent to the client so the
    # interface can state them rather than implying more than is known.
    scope: str = "state"
    limitations: List[str] = []
    generated_at: datetime
