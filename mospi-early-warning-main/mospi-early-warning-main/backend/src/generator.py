"""
Module 1: Synthetic Data & Snapshot Generator
Generates realistic panel/time-series data for MoSPI Dhrishti infrastructure projects.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any
from .config import PipelineConfig, RiskThresholds

class MoSPIDataGenerator:
    """
    Generates synthetic panel dataset for MoSPI infrastructure projects over monthly snapshots.
    Ensures realistic correlation between dynamic execution indicators and final project outcomes.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        np.random.seed(self.config.random_seed)

    def generate_dataset(self) -> pd.DataFrame:
        """
        Generates full synthetic dataset containing multiple monthly snapshots for N projects.
        Returns DataFrame with static, dynamic, and final ground-truth target columns.
        """
        records = []
        
        for p_idx in range(1, self.config.n_projects + 1):
            project_id = f"PRJ_{p_idx:03d}"
            sector = np.random.choice(self.config.SECTORS)
            ministry = np.random.choice(self.config.MINISTRIES)
            agency = np.random.choice(self.config.AGENCIES)
            
            # Static attributes
            original_cost = float(np.random.uniform(200.0, 15000.0))  # Rs Crores
            original_duration = int(np.random.randint(18, 60))        # Months
            
            # Latent project risk profile (0.0 = smooth execution, 1.0 = high risk)
            sector_risk = 0.15 if sector in ["Highways", "Railways"] else 0.05
            latent_risk = float(np.clip(np.random.beta(1.5, 3.5) + sector_risk, 0.02, 0.95))
            
            # Final Outcomes (Ground Truth at project completion)
            # Escalation centered around ~8% with spread up to 50%
            final_cost_escalation = float(np.clip(
                (latent_risk * 32.0 - 5.0) + np.random.normal(0, 4.0), 
                -5.0, 65.0
            ))
            # Delay centered around ~3-4 months with spread up to 36 months
            final_delay_months = float(np.clip(
                (latent_risk * 24.0 - 4.0) + np.random.normal(0, 3.0), 
                0.0, 42.0
            ))
            
            is_material_cost_overrun = int(final_cost_escalation > self.config.thresholds.MATERIAL_COST_OVERRUN_PCT)
            is_deadline_missed = int(final_delay_months > self.config.thresholds.MISSED_DEADLINE_MONTHS)
            
            # Generate monthly snapshots for this project
            n_snapshots = np.random.randint(self.config.min_snapshots, min(original_duration, self.config.max_snapshots) + 1)
            
            cum_expenditure = 0.0
            completed_milestones = 0
            missed_milestones = 0
            land_issue = 1 if np.random.rand() < (latent_risk * 0.6) else 0
            approval_issue = 1 if np.random.rand() < (latent_risk * 0.5) else 0
            
            for m in range(1, n_snapshots + 1):
                # Planned progress curve (linear / mild S-curve)
                planned_pct = min(100.0, (m / original_duration) * 100.0)
                
                # Physical progress lags behind planned if high latent risk / issues present
                lag_factor = 1.0 - (latent_risk * 0.35) - (0.1 if land_issue else 0.0) - (0.1 if approval_issue else 0.0)
                lag_factor = max(0.2, lag_factor)
                physical_pct = min(100.0, planned_pct * lag_factor + np.random.normal(0, 1.5))
                physical_pct = max(0.0, physical_pct)
                
                # Financial progress
                overspend_factor = 1.0 + (latent_risk * 0.25)
                financial_pct = min(100.0, physical_pct * overspend_factor + np.random.normal(0, 1.0))
                financial_pct = max(0.0, financial_pct)
                
                # Cumulative Expenditure in Crores
                cum_expenditure = float(np.clip(original_cost * (financial_pct / 100.0), 0.0, original_cost * 1.8))
                
                # Milestones tracking
                expected_milestones = int(m / 3)
                if expected_milestones > (completed_milestones + missed_milestones):
                    if np.random.rand() > latent_risk:
                        completed_milestones += 1
                    else:
                        missed_milestones += 1
                        
                # Dynamic land and approval issues
                current_land_issue = land_issue if m < (n_snapshots * 0.7) else 0
                current_approval_issue = approval_issue if m < (n_snapshots * 0.8) else 0
                
                # Remarks text generation
                remarks = self._generate_remarks(physical_pct, planned_pct, current_land_issue, current_approval_issue, missed_milestones)
                
                records.append({
                    "project_id": project_id,
                    "sector": sector,
                    "ministry": ministry,
                    "implementing_agency": agency,
                    "original_cost": round(original_cost, 2),
                    "original_duration_months": original_duration,
                    "snapshot_month": m,
                    "physical_progress_pct": round(physical_pct, 2),
                    "financial_progress_pct": round(financial_pct, 2),
                    "cumulative_expenditure": round(cum_expenditure, 2),
                    "planned_progress_pct": round(planned_pct, 2),
                    "missed_milestones_count": missed_milestones,
                    "completed_milestones_count": completed_milestones,
                    "unresolved_land_issues": current_land_issue,
                    "unresolved_approval_issues": current_approval_issue,
                    "remarks_text": remarks,
                    # Target Outcomes (Hidden from feature calculations)
                    "final_cost_escalation_pct": round(final_cost_escalation, 2),
                    "is_material_cost_overrun": is_material_cost_overrun,
                    "final_delay_months": round(final_delay_months, 1),
                    "is_deadline_missed": is_deadline_missed
                })
                
        df = pd.DataFrame(records)
        return df

    def _generate_remarks(self, physical: float, planned: float, land_issue: int, approval_issue: int, missed: int) -> str:
        """Generates realistic free-text CUF status notes."""
        gap = planned - physical
        notes = []
        if gap > 15.0:
            notes.append("Severe physical progress lag observed.")
        elif gap > 5.0:
            notes.append("Minor physical progress slippage.")
        else:
            notes.append("Work progressing as per schedule.")
            
        if land_issue:
            notes.append("Land acquisition bottleneck pending local authority clearance.")
        if approval_issue:
            notes.append("Forest/environmental clearance pending approval.")
        if missed > 2:
            notes.append("Multiple key milestone deadlines missed.")
            
        return " ".join(notes)
