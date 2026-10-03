"""
Unit Test Suite for MoSPI Dhrishti Early-Warning Platform Core.
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.config import PipelineConfig
from src.generator import MoSPIDataGenerator
from src.feature_pipeline import TemporalFeatureExtractor, assert_zero_leakage
from src.ml_engine import DualRiskEngine
from src.risk_calibration import RiskCalibrator
from src.explainability import SHAPExplainer
from src.optimization import OfficerCapacityOptimizer
from src.integration_pipeline import EarlyWarningPipeline

def test_data_generator():
    config = PipelineConfig(n_projects=10, min_snapshots=6, max_snapshots=12)
    generator = MoSPIDataGenerator(config)
    df = generator.generate_dataset()
    
    assert len(df) > 0
    assert df["project_id"].nunique() == 10
    required_cols = [
        "project_id", "sector", "ministry", "implementing_agency", "original_cost",
        "original_duration_months", "snapshot_month", "physical_progress_pct",
        "financial_progress_pct", "cumulative_expenditure", "planned_progress_pct",
        "missed_milestones_count", "completed_milestones_count", "unresolved_land_issues",
        "unresolved_approval_issues", "remarks_text", "final_cost_escalation_pct",
        "is_material_cost_overrun", "final_delay_months", "is_deadline_missed"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"

def test_zero_leakage_assertion():
    df_clean = pd.DataFrame({"feature1": [1, 2], "feature2": [3, 4]})
    target_cols = ["final_cost_escalation_pct", "is_material_cost_overrun"]
    
    # Should pass cleanly
    assert assert_zero_leakage(df_clean, target_cols) is True
    
    # Should raise ValueError when target leaks into feature space
    df_leaked = df_clean.copy()
    df_leaked["final_cost_escalation_pct"] = [10.5, 20.1]
    with pytest.raises(ValueError, match="CRITICAL TEMPORAL LEAKAGE DETECTED"):
        assert_zero_leakage(df_leaked, target_cols)

def test_feature_engineering():
    config = PipelineConfig(n_projects=5, min_snapshots=6, max_snapshots=10)
    df_raw = MoSPIDataGenerator(config).generate_dataset()
    
    extractor = TemporalFeatureExtractor(config)
    extractor.fit(df_raw)
    X_features = extractor.transform(df_raw)
    
    derived_cols = [
        "progress_gap", "expenditure_ratio", "physical_financial_gap",
        "milestone_completion_rate", "cost_burn_rate", "schedule_utilization"
    ]
    for col in derived_cols:
        assert col in X_features.columns, f"Derived feature missing: {col}"
        assert not X_features[col].isnull().any(), f"NaNs found in derived feature: {col}"
        assert not np.isinf(X_features[col]).any(), f"Infs found in derived feature: {col}"

def test_end_to_end_pipeline():
    config = PipelineConfig(n_projects=15, min_snapshots=6, max_snapshots=12)
    pipeline = EarlyWarningPipeline(config)
    results = pipeline.run_full_pipeline()
    
    assert "cv_metrics" in results
    assert "calibration_metrics" in results
    assert "optimization_results" in results
    
    opt_res = results["optimization_results"]
    assert opt_res["total_hours_allocated"] <= opt_res["officer_capacity_hours"]
    assert len(opt_res["selected_projects_queue"]) > 0
    
    # Check SHAP explanation output
    p_id = pipeline.df_risk["project_id"].iloc[0]
    explanation = pipeline.get_explanation(p_id)
    assert explanation["project_id"] == p_id
    assert len(explanation["top_3_positive_contributors"]) <= 3
    assert len(explanation["top_2_mitigating_factors"]) <= 2
    assert "explanation_summary" in explanation

if __name__ == "__main__":
    pytest.main(["-v", __file__])
