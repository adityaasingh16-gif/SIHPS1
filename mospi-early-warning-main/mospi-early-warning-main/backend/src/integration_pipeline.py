"""
Module 7: Modular Runner / Integration Pipeline
Orchestrates data generation, leakage-safe feature engineering, dual ML modeling, calibration, SHAP explanations, and OR-Tools decision optimization.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from .config import PipelineConfig
from .generator import MoSPIDataGenerator
from .feature_pipeline import TemporalFeatureExtractor, assert_zero_leakage
from .ml_engine import DualRiskEngine
from .risk_calibration import RiskCalibrator
from .explainability import SHAPExplainer
from .optimization import OfficerCapacityOptimizer

class EarlyWarningPipeline:
    """
    End-to-End Orchestrator for the MoSPI Early-Warning and Decision-Support Core.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.generator = MoSPIDataGenerator(self.config)
        self.feature_extractor = TemporalFeatureExtractor(self.config)
        self.ml_engine = DualRiskEngine(self.config)
        self.calibrator = RiskCalibrator(self.config)
        self.optimizer = OfficerCapacityOptimizer(self.config)
        
        # State variables
        self.df_raw: pd.DataFrame = None
        self.X_features: pd.DataFrame = None
        self.df_risk: pd.DataFrame = None
        self.cv_metrics: Dict[str, Any] = None
        self.rolling_origin_metrics: Dict[str, Any] = None
        self.calibration_metrics: Dict[str, float] = None
        self.explainer: SHAPExplainer = None

    def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Executes the complete early-warning pipeline flow.
        """
        print("Step 1: Generating Synthetic MoSPI Dhrishti Panel Data...")
        self.df_raw = self.generator.generate_dataset()
        print(f"  Generated {len(self.df_raw)} monthly snapshots across {self.df_raw['project_id'].nunique()} projects.")
        
        print("\nStep 2: Extracting Leakage-Safe Derived Features...")
        self.feature_extractor.fit(self.df_raw)
        self.X_features = self.feature_extractor.transform(self.df_raw)
        assert_zero_leakage(self.X_features, [
            self.config.features.TARGET_COST_REG,
            self.config.features.TARGET_COST_CLASS,
            self.config.features.TARGET_DELAY_REG,
            self.config.features.TARGET_DELAY_CLASS
        ])
        print(f"  Extracted {self.X_features.shape[1]} leakage-safe features.")
        
        print("\nStep 3: Training & Evaluating Dual Risk Engines (GroupKFold on project_id)...")
        self.cv_metrics = self.ml_engine.train_and_evaluate(self.X_features, self.df_raw, n_splits=5)
        print("  GroupKFold Cross-Validation complete.")

        print("\nStep 3b: Rolling-Origin Time-Aware Validation (tests genuine early-warning capability)...")
        self.rolling_origin_metrics = self.ml_engine.rolling_origin_evaluate(self.X_features, self.df_raw)
        n_cutoffs = len(self.rolling_origin_metrics.get("per_cutoff_results", []))
        print(f"  Rolling-origin validation complete across {n_cutoffs} time cutoffs.")
        
        print("\nStep 4: Calibrating Classification Probabilities & Aggregating 0-100 Risk Scores...")
        # Split holdout projects into two NON-OVERLAPPING sets:
        #   - calib_fit_ids  (20%): used to FIT the calibrator
        #   - calib_eval_ids (20%): used ONLY to EVALUATE calibration quality (Brier score)
        # This avoids the circularity of testing a calibrator on the same data it was fit
        # on, which would make Brier scores look artificially close to zero.
        rng = np.random.RandomState(self.config.random_seed)
        unique_projects = self.df_raw["project_id"].unique()
        shuffled = rng.permutation(unique_projects)
        n_holdout_each = max(1, int(len(shuffled) * 0.2))

        calib_fit_ids = shuffled[:n_holdout_each]
        calib_eval_ids = shuffled[n_holdout_each: 2 * n_holdout_each]

        fit_mask = self.df_raw["project_id"].isin(calib_fit_ids)
        eval_mask = self.df_raw["project_id"].isin(calib_eval_ids)

        X_calib_fit = self.X_features[fit_mask]
        y_cost_calib_fit = self.df_raw[fit_mask][self.config.features.TARGET_COST_CLASS].values
        y_delay_calib_fit = self.df_raw[fit_mask][self.config.features.TARGET_DELAY_CLASS].values

        X_calib_eval = self.X_features[eval_mask]
        y_cost_calib_eval = self.df_raw[eval_mask][self.config.features.TARGET_COST_CLASS].values
        y_delay_calib_eval = self.df_raw[eval_mask][self.config.features.TARGET_DELAY_CLASS].values

        self.calibration_metrics = self.calibrator.fit_calibrators(
            self.ml_engine.cost_cls_xgb,
            self.ml_engine.delay_cls_xgb,
            X_calib_fit,
            y_cost_calib_fit,
            y_delay_calib_fit,
            X_eval=X_calib_eval,
            y_cost_eval=y_cost_calib_eval,
            y_delay_eval=y_delay_calib_eval,
        )
        
        self.df_risk = self.calibrator.annotate_dataframe_with_risk(
            self.df_raw,
            self.X_features,
            self.ml_engine.cost_cls_xgb,
            self.ml_engine.delay_cls_xgb
        )
        print("  Calibrated risk scores and tiers computed.")
        
        print("\nStep 5: Initializing SHAP TreeExplainer Layer...")
        self.explainer = SHAPExplainer(
            self.ml_engine.cost_cls_xgb,
            self.ml_engine.delay_cls_xgb,
            list(self.X_features.columns)
        )
        print("  SHAP Explainer ready.")
        
        print("\nStep 6: Executing OR-Tools Officer Capacity Allocation Optimization...")
        opt_results = self.optimizer.optimize_review_queue(
            self.df_risk, 
            officer_capacity_hours=self.config.default_officer_hours_budget
        )
        print(f"  Optimization Complete: Allocated {opt_results['total_hours_allocated']} hrs ({opt_results['capacity_utilization_pct']}%) across {opt_results['n_projects_selected']} high-risk projects.")
        
        return {
            "cv_metrics": self.cv_metrics,
            "rolling_origin_metrics": self.rolling_origin_metrics,
            "calibration_metrics": self.calibration_metrics,
            "optimization_results": opt_results
        }

    def get_explanation(self, project_id: str, snapshot_month: int = None) -> Dict[str, Any]:
        """Wrapper method to fetch SHAP risk explanation for a project."""
        if snapshot_month is None:
            p_rows = self.df_risk[self.df_risk["project_id"] == project_id]
            if len(p_rows) == 0:
                raise ValueError(f"Project ID '{project_id}' not found in dataset.")
            snapshot_month = int(p_rows["snapshot_month"].max())
        return self.explainer.get_project_risk_explanation(
            project_id, snapshot_month, self.df_risk, self.X_features
        )
