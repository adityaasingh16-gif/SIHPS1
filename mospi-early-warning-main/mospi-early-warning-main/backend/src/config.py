"""
Configuration and Schema Definitions for MoSPI Dhrishti Early-Warning Platform.
"""

from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class RiskThresholds:
    """Risk tier cutoffs and target outcome thresholds."""
    MATERIAL_COST_OVERRUN_PCT: float = 10.0  # Cost escalation > 10% is material overrun
    MISSED_DEADLINE_MONTHS: float = 3.0      # Delay > 3 months is deadline missed
    
    # Composite Risk Tier Cutoffs (0 to 100 scale)
    CRITICAL_MIN: float = 75.0
    HIGH_MIN: float = 50.0
    MEDIUM_MIN: float = 25.0

@dataclass
class FeatureConfig:
    """Feature names and schema groupings."""
    STATIC_NUMERIC: List[str] = field(default_factory=lambda: [
        "original_cost",
        "original_duration_months"
    ])
    
    STATIC_CATEGORICAL: List[str] = field(default_factory=lambda: [
        "sector",
        "ministry",
        "implementing_agency"
    ])
    
    DYNAMIC_RAW: List[str] = field(default_factory=lambda: [
        "snapshot_month",
        "physical_progress_pct",
        "financial_progress_pct",
        "cumulative_expenditure",
        "planned_progress_pct",
        "missed_milestones_count",
        "completed_milestones_count",
        "unresolved_land_issues",
        "unresolved_approval_issues"
    ])
    
    DERIVED_FEATURES: List[str] = field(default_factory=lambda: [
        "progress_gap",
        "expenditure_ratio",
        "physical_financial_gap",
        "milestone_completion_rate",
        "cost_burn_rate"
    ])
    
    TEXT_FEATURE: str = "remarks_text"
    
    TARGET_COST_REG: str = "final_cost_escalation_pct"
    TARGET_COST_CLASS: str = "is_material_cost_overrun"
    TARGET_DELAY_REG: str = "final_delay_months"
    TARGET_DELAY_CLASS: str = "is_deadline_missed"

@dataclass
class PipelineConfig:
    """Global configuration for simulation and modeling."""
    random_seed: int = 42
    n_projects: int = 80
    min_snapshots: int = 12
    max_snapshots: int = 36
    
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    
    # Officer Capacity Allocation Defaults
    default_officer_hours_budget: float = 120.0
    
    # Sector list based on Dhrishti domain
    SECTORS: List[str] = field(default_factory=lambda: [
        "Railways", "Highways", "Power", "Petroleum", "Telecom", 
        "Civil Aviation", "Ports & Shipping", "Urban Development"
    ])
    
    MINISTRIES: List[str] = field(default_factory=lambda: [
        "Ministry of Railways",
        "Ministry of Road Transport and Highways",
        "Ministry of Power",
        "Ministry of Petroleum and Natural Gas",
        "Ministry of Communications",
        "Ministry of Civil Aviation"
    ])
    
    AGENCIES: List[str] = field(default_factory=lambda: [
        "NHAI", "RVNL", "NTPC", "IOCL", "AAI", "BSNL", "PGCIL"
    ])
