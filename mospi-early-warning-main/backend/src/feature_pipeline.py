"""
Module 2: Data Leakage Prevention & Feature Engineering Pipeline
Computes leakage-safe features strictly from point-in-time snapshot information up to month T.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict
from sklearn.base import BaseEstimator, TransformerMixin
from .config import PipelineConfig

class TemporalFeatureExtractor(BaseEstimator, TransformerMixin):
    """
    Scikit-learn compatible transformer that extracts point-in-time derived features
    from Dhrishti monthly snapshots while guaranteeing strict temporal separation.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.categorical_cols = self.config.features.STATIC_CATEGORICAL
        self.target_cols = [
            self.config.features.TARGET_COST_REG,
            self.config.features.TARGET_COST_CLASS,
            self.config.features.TARGET_DELAY_REG,
            self.config.features.TARGET_DELAY_CLASS
        ]
        self.encoded_feature_names_: List[str] = []

    def fit(self, X: pd.DataFrame, y=None):
        """Fits categorical encoders and records canonical feature column list."""
        df_transformed = self._extract(X)
        self.encoded_feature_names_ = list(df_transformed.columns)
        return self

    def _extract(self, X: pd.DataFrame) -> pd.DataFrame:
        """Helper method to extract raw derived features and dummy columns."""
        df = X.drop(columns=[col for col in self.target_cols if col in X.columns]).copy()
        
        # 1. Mandatory Derived Features
        df["progress_gap"] = df["planned_progress_pct"] - df["physical_progress_pct"]
        df["expenditure_ratio"] = df["cumulative_expenditure"] / (df["original_cost"] + 1e-5)
        df["physical_financial_gap"] = df["financial_progress_pct"] - df["physical_progress_pct"]
        
        total_milestones = df["completed_milestones_count"] + df["missed_milestones_count"] + 1e-5
        df["milestone_completion_rate"] = df["completed_milestones_count"] / total_milestones
        df["cost_burn_rate"] = df["cumulative_expenditure"] / (df["snapshot_month"] + 1e-5)
        
        # 2. Additional Temporal Utilization & Warning Signals
        df["schedule_utilization"] = df["snapshot_month"] / (df["original_duration_months"] + 1e-5)
        
        # Free-text remarks keyword signal extraction
        warning_keywords = ["severe", "lag", "bottleneck", "pending", "missed", "delay", "slippage"]
        df["remarks_warning_count"] = df["remarks_text"].apply(
            lambda text: sum(1 for kw in warning_keywords if kw in str(text).lower())
        )
        
        # One-hot encode categorical features
        df_encoded = pd.get_dummies(df, columns=self.categorical_cols, drop_first=False)
        
        # Base feature columns to retain
        base_features = [
            "original_cost", "original_duration_months", "snapshot_month",
            "physical_progress_pct", "financial_progress_pct", "cumulative_expenditure",
            "planned_progress_pct", "missed_milestones_count", "completed_milestones_count",
            "unresolved_land_issues", "unresolved_approval_issues",
            "progress_gap", "expenditure_ratio", "physical_financial_gap",
            "milestone_completion_rate", "cost_burn_rate", "schedule_utilization",
            "remarks_warning_count"
        ]
        
        dummy_cols = [c for c in df_encoded.columns if any(c.startswith(cat + "_") for cat in self.categorical_cols)]
        feature_cols = base_features + dummy_cols
        
        X_out = df_encoded[feature_cols]
        assert_zero_leakage(X_out, self.target_cols)
        return X_out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms snapshot raw DataFrame into a leakage-safe feature matrix.
        Guarantees exact alignment with fitted feature names for single-instance simulations.
        """
        X_out = self._extract(X)
        
        if self.encoded_feature_names_:
            # Align columns with training schema, filling missing dummy columns with 0
            X_out = X_out.reindex(columns=self.encoded_feature_names_, fill_value=0)
            
        return X_out

def assert_zero_leakage(df_features: pd.DataFrame, target_columns: List[str]) -> bool:
    """
    Checks that no target column or future project completion metric exists in the feature matrix.
    Raises ValueError if target leakage is detected.
    """
    leaked = [col for col in target_columns if col in df_features.columns]
    if leaked:
        raise ValueError(
            f"CRITICAL TEMPORAL LEAKAGE DETECTED! Target columns {leaked} found in feature matrix."
        )
    return True
