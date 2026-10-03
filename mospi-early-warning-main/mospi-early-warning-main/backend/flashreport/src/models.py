"""Pydantic models for the Flash Report domain.

The single source of truth is a validated :class:`InputReport`, which wraps the
raw JSON/CSV payload.  All KPIs, charts and table rows in the report are derived
exclusively from these models - nothing is hard-coded at render time.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Project(BaseModel):
    """One monitored central-sector infrastructure project."""

    project_id: str
    project_name: str
    agency: str
    ministry: str
    sector: str
    category: str = Field(description="Grouping such as 'Transport & Logistics'")
    state: str
    is_north_east: bool = False
    approval_date: str = Field(description="MM/YYYY")
    start_date: str = Field(description="MM/YYYY")
    original_doc: str = Field(description="Original date of completion, MM/YYYY")
    revised_doc: str = Field(description="Revised date of completion, MM/YYYY")
    actual_completion_date: str = Field(
        default="", description="MM/YYYY, empty when not completed"
    )
    original_cost: float
    revised_cost: float
    cumulative_expenditure: float
    physical_progress_pct: float
    financial_progress_pct: float
    legacy_code: str = ""
    pmgid: str = ""
    status: str = Field(description="ongoing | completed_this_month | newly_added_this_month")

    @field_validator(
        "original_cost", "revised_cost", "cumulative_expenditure",
        "physical_progress_pct", "financial_progress_pct",
        mode="before",
    )
    @classmethod
    def _coerce_numeric(cls, v):
        if isinstance(v, str):
            v = v.replace(",", "").replace(" ", "")
            if v in {"", "-", "--", "nil", "N/A", "na"}:
                return 0.0
            return float(v)
        return v

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, v):
        v = str(v).strip().lower()
        allowed = {"ongoing", "completed_this_month", "newly_added_this_month"}
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}, got {v!r}")
        return v

    @property
    def is_mega(self) -> bool:
        """Mega = original cost >= ₹1000 crore (threshold lives in theme.yaml)."""
        return self.original_cost >= 1000.0


class Assets(BaseModel):
    emblem: str = ""
    org_logo: str = ""
    cover_art: str = ""
    skyline_art: str = ""
    qr_image: str = ""


class Meta(BaseModel):
    edition_no: int
    month_label: str = Field(description="e.g. 'JULY 2026'")
    month: str = Field(description="ISO month, e.g. '2026-07'")
    cost_threshold_text: str = Field(default="₹150 crore & above")
    portal_url: str = "https://oms.mospi.gov.in"
    data_cutoff_note: str = ""
    assets: Assets = Assets()
    report_title: str = ""
    program_name: str = "Infrastructure and Project Monitoring Division"
    ministry_name: str = "Ministry of Statistics and Programme Implementation"


class InputReport(BaseModel):
    """Validated payload: everything the generator needs."""

    meta: Meta
    projects: list[Project] = Field(min_length=1, description="1,600+ real rows")
    previous: "InputReport | None" = None

    @property
    def ongoing(self) -> list[Project]:
        return [p for p in self.projects if p.status == "ongoing"]

    @property
    def completed(self) -> list[Project]:
        return [p for p in self.projects if p.status == "completed_this_month"]

    @property
    def newly_added(self) -> list[Project]:
        return [p for p in self.projects if p.status == "newly_added_this_month"]

    @property
    def north_east(self) -> list[Project]:
        return [p for p in self.projects if p.is_north_east]

    @property
    def categories(self) -> list[str]:
        order = [
            "Transport & Logistics", "Energy", "Water & Sanitation",
            "Communication", "Social & Commercial", "Other Sectors",
        ]
        present = sorted({p.category for p in self.projects})
        return [c for c in order if c in present] + [c for c in present if c not in order]


InputReport.model_rebuild()