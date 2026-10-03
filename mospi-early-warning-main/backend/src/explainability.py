"""
Module 5: Model Explainability Layer (SHAP)
Provides project-specific risk breakdown by delegating to TreeSHAPEngine.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from .config import PipelineConfig
from .tree_shap_engine import TreeSHAPEngine


class SHAPExplainer:
    """
    Wraps TreeSHAPEngine for Cost and Delay models to analyze feature importance
    and generate project-specific risk explanations.
    """

    def __init__(
        self,
        cost_model: Any,
        delay_model: Any,
        feature_names: List[str],
        cost_weight: float = 0.5,
        delay_weight: float = 0.5
    ):
        self.engine = TreeSHAPEngine(
            cost_model=cost_model,
            delay_model=delay_model,
            feature_names=feature_names,
            cost_weight=cost_weight,
            delay_weight=delay_weight
        )
        self.cost_model = cost_model
        self.delay_model = delay_model
        self.feature_names = feature_names

    def get_project_risk_explanation(
        self,
        project_id: str,
        snapshot_month: int,
        df_full: pd.DataFrame,
        X_features: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Retrieves project risk explanation for a specific project snapshot.
        """
        mask = (df_full["project_id"] == project_id) & (df_full["snapshot_month"] == snapshot_month)
        matching_indices = df_full[mask].index

        if len(matching_indices) == 0:
            p_mask = (df_full["project_id"] == project_id)
            if not p_mask.any():
                raise ValueError(f"Project ID '{project_id}' not found in dataset.")
            latest_month = df_full[p_mask]["snapshot_month"].max()
            mask = (df_full["project_id"] == project_id) & (df_full["snapshot_month"] == latest_month)
            matching_indices = df_full[mask].index

        row_idx = matching_indices[0]
        instance_features = X_features.iloc[[row_idx]]
        row_meta = df_full.iloc[row_idx].to_dict()

        explanation = self.engine.explain_instance(instance_features, row_meta)

        # Attach metadata metrics
        explanation["composite_risk_score"] = float(row_meta.get("composite_risk_score", 0.0))
        explanation["risk_tier"] = str(row_meta.get("risk_tier", "Unknown"))
        explanation["calibrated_cost_prob"] = float(row_meta.get("calibrated_cost_prob", 0.0))
        explanation["calibrated_delay_prob"] = float(row_meta.get("calibrated_delay_prob", 0.0))

        return explanation
