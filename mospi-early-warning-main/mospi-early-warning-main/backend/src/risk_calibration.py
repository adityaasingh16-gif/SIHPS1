"""
Module 4: Probability Calibration & Risk Aggregation Pipeline
Calibrates raw classification probabilities using Platt Scaling (sigmoid, via Logistic
Regression) and aggregates cost & delay risk signals into a composite 0-100 risk score
and risk tier.

NOTE ON CALIBRATION METHOD: Isotonic Regression was evaluated first but was dropped in
favor of Platt/sigmoid scaling for this project. On a modestly sized dataset (dozens to
low hundreds of projects), Isotonic Regression tends to produce a step function that
collapses many distinct raw probabilities into a small number of exact output values
(e.g. many projects landing on an identical risk score such as exactly 100.0, 50.0, or
0.0). Platt scaling fits a smooth sigmoid instead, which produces a continuous spread of
risk scores that is both more realistic and more useful for ranking/prioritization.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, List, Optional
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from .config import PipelineConfig

class RiskCalibrator:
    """
    Fits probability calibration (Platt Scaling by default, Isotonic Regression available
    as an alternative) and aggregates cost & delay risk signals into a composite 0-100
    risk score and risk tier.
    """
    
    def __init__(self, config: PipelineConfig = None, method: str = "platt"):
        self.config = config or PipelineConfig()
        self.method = method  # "platt" (default, smooth) or "isotonic" (step function)
        if method == "isotonic":
            self.cost_calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            self.delay_calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        else:
            # Platt scaling: fit a 1-D logistic regression on the raw probability score
            self.cost_calibrator = LogisticRegression()
            self.delay_calibrator = LogisticRegression()
        self.is_fitted = False
        # Per-target flags: set to False if calibration had to be skipped (e.g. a fit
        # split contained only one class, which LogisticRegression/Isotonic cannot fit).
        # When False, predict_calibrated_probabilities falls back to the model's raw
        # (uncalibrated) probability for that target instead of raising an error.
        self._cost_calibration_active = False
        self._delay_calibration_active = False

    def _fit_one(self, calibrator, raw_probs: np.ndarray, y: np.ndarray) -> bool:
        """Fits one calibrator. Returns True on success, False if it had to be skipped
        (e.g. only one class present in y, which a calibrator cannot be fit on)."""
        if len(np.unique(y)) < 2:
            return False
        try:
            if self.method == "isotonic":
                calibrator.fit(raw_probs, y)
            else:
                calibrator.fit(raw_probs.reshape(-1, 1), y)
            return True
        except ValueError:
            return False

    def _predict_one(self, calibrator, raw_probs: np.ndarray, active: bool) -> np.ndarray:
        if not active:
            return raw_probs
        if self.method == "isotonic":
            return calibrator.predict(raw_probs)
        else:
            return calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]

    def fit_calibrators(
        self, 
        cost_cls_model: Any, 
        delay_cls_model: Any, 
        X_val: pd.DataFrame, 
        y_cost_val: np.ndarray, 
        y_delay_val: np.ndarray,
        X_eval: Optional[pd.DataFrame] = None,
        y_cost_eval: Optional[np.ndarray] = None,
        y_delay_eval: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Fits calibrators on (X_val, y_val).

        IMPORTANT: Brier scores are reported on a SEPARATE (X_eval, y_eval) set whenever
        it is provided. Evaluating calibration quality on the same data used to fit the
        calibrator is circular and produces artificially near-zero Brier scores that do
        not reflect real generalization. If no eval set is passed, this falls back to
        evaluating on the fit set itself and `evaluated_on_held_out_set` is False so the
        caller cannot mistake it for an honest out-of-sample estimate.
        """
        raw_cost_probs_fit = cost_cls_model.predict_proba(X_val)[:, 1]
        raw_delay_probs_fit = delay_cls_model.predict_proba(X_val)[:, 1]

        self._cost_calibration_active = self._fit_one(self.cost_calibrator, raw_cost_probs_fit, y_cost_val)
        self._delay_calibration_active = self._fit_one(self.delay_calibrator, raw_delay_probs_fit, y_delay_val)
        self.is_fitted = True

        honest_eval = X_eval is not None and y_cost_eval is not None and y_delay_eval is not None
        if honest_eval:
            eval_X, eval_y_cost, eval_y_delay = X_eval, y_cost_eval, y_delay_eval
        else:
            eval_X, eval_y_cost, eval_y_delay = X_val, y_cost_val, y_delay_val

        raw_cost_probs_eval = cost_cls_model.predict_proba(eval_X)[:, 1]
        raw_delay_probs_eval = delay_cls_model.predict_proba(eval_X)[:, 1]

        # Brier scores are only meaningful where the eval set itself has both classes
        brier_cost_raw = brier_score_loss(eval_y_cost, raw_cost_probs_eval) if len(np.unique(eval_y_cost)) > 1 else float("nan")
        brier_delay_raw = brier_score_loss(eval_y_delay, raw_delay_probs_eval) if len(np.unique(eval_y_delay)) > 1 else float("nan")

        cal_cost_probs_eval = self._predict_one(self.cost_calibrator, raw_cost_probs_eval, self._cost_calibration_active)
        cal_delay_probs_eval = self._predict_one(self.delay_calibrator, raw_delay_probs_eval, self._delay_calibration_active)

        brier_cost_cal = brier_score_loss(eval_y_cost, cal_cost_probs_eval) if len(np.unique(eval_y_cost)) > 1 else float("nan")
        brier_delay_cal = brier_score_loss(eval_y_delay, cal_delay_probs_eval) if len(np.unique(eval_y_delay)) > 1 else float("nan")

        return {
            "calibration_method": self.method,
            "cost_calibration_active": self._cost_calibration_active,
            "delay_calibration_active": self._delay_calibration_active,
            "brier_cost_raw": float(brier_cost_raw),
            "brier_cost_calibrated": float(brier_cost_cal),
            "brier_delay_raw": float(brier_delay_raw),
            "brier_delay_calibrated": float(brier_delay_cal),
            "evaluated_on_held_out_set": bool(honest_eval),
        }

    def predict_calibrated_probabilities(
        self, 
        X: pd.DataFrame, 
        cost_cls_model: Any, 
        delay_cls_model: Any
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predicts calibrated probability of material cost overrun and missed deadline.
        """
        raw_cost_probs = cost_cls_model.predict_proba(X)[:, 1]
        raw_delay_probs = delay_cls_model.predict_proba(X)[:, 1]
        
        if self.is_fitted:
            cost_probs = self._predict_one(self.cost_calibrator, raw_cost_probs, self._cost_calibration_active)
            delay_probs = self._predict_one(self.delay_calibrator, raw_delay_probs, self._delay_calibration_active)
        else:
            cost_probs = raw_cost_probs
            delay_probs = raw_delay_probs
            
        return cost_probs, delay_probs

    def compute_composite_risk_score(
        self, 
        cost_prob: float, 
        delay_prob: float
    ) -> Tuple[float, str]:
        """
        Computes composite risk score (0 to 100 scale):
        Composite Risk = 0.5 * (Cost Prob * 100) + 0.5 * (Delay Prob * 100)
        Returns (score, risk_tier).
        """
        score = 0.5 * (cost_prob * 100.0) + 0.5 * (delay_prob * 100.0)
        score = float(np.clip(score, 0.0, 100.0))
        
        if score >= self.config.thresholds.CRITICAL_MIN:
            tier = "Critical"
        elif score >= self.config.thresholds.HIGH_MIN:
            tier = "High"
        elif score >= self.config.thresholds.MEDIUM_MIN:
            tier = "Medium"
        else:
            tier = "Low"
            
        return round(score, 1), tier

    def annotate_dataframe_with_risk(
        self, 
        df: pd.DataFrame, 
        X_features: pd.DataFrame, 
        cost_cls_model: Any, 
        delay_cls_model: Any
    ) -> pd.DataFrame:
        """
        Adds calibrated cost prob, calibrated delay prob, composite risk score, and risk tier to DataFrame.
        """
        cost_probs, delay_probs = self.predict_calibrated_probabilities(
            X_features, cost_cls_model, delay_cls_model
        )
        
        scores = []
        tiers = []
        for cp, dp in zip(cost_probs, delay_probs):
            sc, tr = self.compute_composite_risk_score(cp, dp)
            scores.append(sc)
            tiers.append(tr)
            
        res_df = df.copy()
        res_df["calibrated_cost_prob"] = np.round(cost_probs, 4)
        res_df["calibrated_delay_prob"] = np.round(delay_probs, 4)
        res_df["composite_risk_score"] = scores
        res_df["risk_tier"] = tiers
        return res_df
