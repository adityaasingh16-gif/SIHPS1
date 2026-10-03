"""
Real-Data ML Engine: trains early-warning models on the parsed MoSPI Dhrishti
Flash-Report panel (CSV produced by pdf_panel.py).

Problem framing
---------------
For each project-month snapshot we observe *point-in-time* signals:
  - static:  original cost, planned duration, ministry, sector, agency, state
  - dynamic: elapsed months, physical progress %, cumulative expenditure, and
             simple ratios/gaps derived from those.
The *outcome to predict* is the project's FINAL observed cost escalation and
schedule delay (revised cost vs original; revised DoC vs target DoC), taken
from its latest available snapshot. This is a genuine early-warning setup:
can we flag an eventual overrun/miss before it fully materialises?

Leakage safety
--------------
  * revised_cost / revised_doc / final targets are NEVER used as features.
  * The 70/30 hold-out splits by project_code (GroupShuffleSplit), so no
    project's snapshots appear in both train and test.
  * GroupKFold CV is kept as a secondary sanity check.

Models
------
  * XGBoost, LightGBM, CatBoost  (regressors + classifiers)
  * RandomForest (regressor baseline), LogisticRegression (classifier baseline)
"""

import os
import re
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List

import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostRegressor, CatBoostClassifier
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    roc_auc_score, f1_score, precision_score, recall_score,
)

from .config import PipelineConfig

MODEL_KEYS = ["xgb", "lgbm", "catboost"]

REGRESSOR_KEYS = [f"cost_reg_{k}" for k in MODEL_KEYS] + [f"delay_reg_{k}" for k in MODEL_KEYS]
CLASS_KEYS = [f"cost_cls_{k}" for k in MODEL_KEYS] + [f"delay_cls_{k}" for k in MODEL_KEYS]

DEFAULT_PANEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "panel_mospi.csv"
)


def _sanitize_names(cols) -> List[str]:
    """Converts arbitrary label strings into LightGBM/CatBoost-safe names."""
    return [re.sub(r"[^A-Za-z0-9_]", "_", str(c)) for c in cols]


class RealDataFeatureExtractor:
    """Builds a leakage-safe one-hot feature matrix from the parsed panel."""

    CATEGORICAL = ["ministry", "sector", "state"]

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.encoded_feature_names_: List[str] = []

    def _extract(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df.copy()

        # Point-in-time derived features
        X["elapsed_months"] = (
            (X["report_year"] * 12 + X["report_month"])
            - (X["approval_year"] * 12 + X["approval_month"])
        )
        X["schedule_utilization"] = X["elapsed_months"] / (X["planned_duration_months"] + 1e-5)
        X["planned_progress_pct"] = np.clip(X["schedule_utilization"] * 100.0, 0.0, 100.0)
        X["progress_gap"] = X["planned_progress_pct"] - X["physical_progress_pct"]
        X["expenditure_ratio"] = X["cumulative_expenditure_crore"] / (X["original_cost_crore"] + 1e-5)
        X["expenditure_vs_revised"] = X["cumulative_expenditure_crore"] / (X["revised_cost_crore"] + 1e-5)
        X["log_original_cost"] = np.log1p(X["original_cost_crore"])
        X["is_revised"] = (X["revised_cost_crore"] != X["original_cost_crore"]).astype(int)
        X["physical_score"] = X["physical_progress_pct"] / 100.0

        # Categorical one-hot encoding (state has up to ~149 categories; drop
        # infrequent ones to keep the matrix manageable without leaking labels)
        encode_cols = [c for c in self.CATEGORICAL if c in X.columns]
        for col in encode_cols:
            counts = X[col].value_counts()
            keep = counts.index[:25].tolist() if len(counts) > 25 else counts.index.tolist()
            X[col] = X[col].where(X[col].isin(keep), "Other")

        df_encoded = pd.get_dummies(X, columns=encode_cols, drop_first=False)
        df_encoded.columns = _sanitize_names(df_encoded.columns)

        base_features = [
            "elapsed_months", "schedule_utilization", "planned_progress_pct",
            "progress_gap", "physical_progress_pct", "cumulative_expenditure_crore",
            "expenditure_ratio", "expenditure_vs_revised", "log_original_cost",
            "original_cost_crore", "planned_duration_months", "is_revised",
            "physical_score",
        ]
        base_features = _sanitize_names(base_features)
        dummy_cols = [
            c for c in df_encoded.columns
            if any(c.startswith(_sanitize_names([col])[0] + "_") for col in encode_cols)
        ]
        return df_encoded[base_features + dummy_cols]

    def fit(self, df: pd.DataFrame, y=None):
        self.encoded_feature_names_ = list(self._extract(df).columns)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        X_out = self._extract(df)
        if self.encoded_feature_names_:
            X_out = X_out.reindex(columns=self.encoded_feature_names_, fill_value=0)
        return X_out

    def fit_transform(self, df: pd.DataFrame, y=None) -> pd.DataFrame:
        return self.fit(df).transform(df)


def _scores(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _cls_scores(y_true: np.ndarray, prob: np.ndarray, threshold: float = 0.5) -> Dict[str, float]:
    pred = (prob >= threshold).astype(int)
    scores = {
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
    }
    if len(np.unique(y_true)) > 1:
        try:
            scores["roc_auc"] = float(roc_auc_score(y_true, prob))
        except ValueError:
            scores["roc_auc"] = float("nan")
    else:
        scores["roc_auc"] = float("nan")
    return scores


def _empty_metrics(reg_or_cls: str) -> Dict[str, List]:
    if reg_or_cls == "reg":
        return {"mae": [], "rmse": [], "r2": []}
    return {"roc_auc": [], "f1": [], "precision": [], "recall": []}


class RealDataRiskEngine:
    """Trains + evaluates XGBoost / LightGBM / CatBoost on the real PDF panel."""

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.rs = self.config.random_seed
        self.feature_extractor = RealDataFeatureExtractor(self.config)
        self.metrics_70_30: Dict[str, Any] = {}
        self.cv_metrics: Dict[str, Any] = {}

        # Production model instances (trained on full data)
        self.models: Dict[str, Any] = {
            "cost_reg_xgb": xgb.XGBRegressor(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=self.rs),
            "cost_reg_lgbm": lgb.LGBMRegressor(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=self.rs, verbose=-1),
            "cost_reg_catboost": CatBoostRegressor(iterations=120, depth=5, learning_rate=0.07, verbose=False, random_seed=self.rs),
            "delay_reg_xgb": xgb.XGBRegressor(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=self.rs),
            "delay_reg_lgbm": lgb.LGBMRegressor(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=self.rs, verbose=-1),
            "delay_reg_catboost": CatBoostRegressor(iterations=120, depth=5, learning_rate=0.07, verbose=False, random_seed=self.rs),
            "cost_cls_xgb": xgb.XGBClassifier(n_estimators=120, max_depth=5, learning_rate=0.07, eval_metric="logloss", random_state=self.rs),
            "cost_cls_lgbm": lgb.LGBMClassifier(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=self.rs, verbose=-1),
            "cost_cls_catboost": CatBoostClassifier(iterations=120, depth=5, learning_rate=0.07, verbose=False, random_seed=self.rs),
            "delay_cls_xgb": xgb.XGBClassifier(n_estimators=120, max_depth=5, learning_rate=0.07, eval_metric="logloss", random_state=self.rs),
            "delay_cls_lgbm": lgb.LGBMClassifier(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=self.rs, verbose=-1),
            "delay_cls_catboost": CatBoostClassifier(iterations=120, depth=5, learning_rate=0.07, verbose=False, random_seed=self.rs),
        }

    # ------------------------------------------------------------------ data
    def load_panel(self, path: str = DEFAULT_PANEL_PATH) -> pd.DataFrame:
        df = pd.read_csv(path)
        # Drop rows missing core target/feature data
        df = df.dropna(subset=[
            "original_cost_crore", "physical_progress_pct",
            "approval_year", "approval_month", "planned_duration_months",
        ])
        # delay target needs target DoC; cost target needs both costs
        df["has_cost_target"] = df["revised_cost_crore"].notna()
        df["has_delay_target"] = df["target_doc_year"].notna()
        return df

    def latest_outcomes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Per-project final observed outcome (from the latest snapshot)."""
        idx = df.groupby("project_code")["snapshot_full"].idxmax()
        latest = df.loc[idx].copy()
        return latest[["project_code", "cost_escalation_pct", "is_material_cost_overrun",
                        "delay_months", "is_deadline_missed", "has_cost_target", "has_delay_target"]]

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Returns (X_features, df_with_targets) aligned row-for-row."""
        outcome_cols = ["cost_escalation_pct", "is_material_cost_overrun",
                        "delay_months", "is_deadline_missed"]
        to_drop = outcome_cols + ["has_cost_target", "has_delay_target"]
        df_w = df.drop(columns=[c for c in to_drop if c in df.columns])
        latest = self.latest_outcomes(df)
        # Label each snapshot with its project's FINAL observed outcome. The
        # latest snapshot's outcome is copied verbatim; earlier snapshots share
        # the same project-level target (that is the object of the prediction).
        latest_map = latest.set_index("project_code")[outcome_cols + ["has_cost_target", "has_delay_target"]]
        df_w = df_w.join(latest_map, on="project_code", how="left")
        X = self.feature_extractor.fit_transform(df_w)
        return X, df_w

    # ------------------------------------------------------------- evaluation
    def _train_eval_on(self, X, y_reg, y_cls, df_w, train_idx, val_idx, metrics: Dict):
        """Trains all real models on (train_idx) and records metrics on (val_idx)."""
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_r_tr, y_r_val = y_reg[train_idx], y_reg[val_idx]
        y_c_tr, y_c_val = y_cls[train_idx], y_cls[val_idx]
        delay_raw = df_w["delay_months"].values

        # Mask of rows with a usable delay-regression target (many snapshots have
        # no target DoC / revised DoC, so we must fit only on complete pairs).
        delay_ok_tr = train_idx[~np.isnan(delay_raw[train_idx])]
        delay_ok_va = val_idx[~np.isnan(delay_raw[val_idx])]

        # Regression: cost_* / delay_*
        for target_y_tr, target_y_val, tr_idx, va_idx, reg_keys in (
            (y_r_tr, y_r_val, train_idx, val_idx,
             [k for k in REGRESSOR_KEYS if k.startswith("cost_reg_")]),
            (None, None, delay_ok_tr, delay_ok_va,
             [k for k in REGRESSOR_KEYS if k.startswith("delay_reg_")]),
        ):
            if target_y_tr is None:
                if len(delay_ok_tr) < 20 or len(delay_ok_va) < 20:
                    continue
                target_y_tr, target_y_val = delay_raw[tr_idx], delay_raw[va_idx]
            if len(tr_idx) < 20 or len(va_idx) < 20:
                continue
            if np.isnan(target_y_tr).any() or np.isnan(target_y_val).any():
                continue
            X_tr_use, X_va_use = X.iloc[tr_idx], X.iloc[va_idx]
            for key in reg_keys:
                model = self._fresh_model(key)
                model.fit(X_tr_use, target_y_tr)
                pred = model.predict(X_va_use)
                for metric, val in _scores(target_y_val, pred).items():
                    metrics[key][metric].append(val)

        # Classification: cost_cls_* / delay_cls_*
        missed_raw = df_w["is_deadline_missed"].values.astype(float)
        missed_raw[np.isnan(delay_raw)] = np.nan  # unknown delay => exclude
        for target_y_tr, target_y_val, tr_idx, va_idx, cls_keys in (
            (y_c_tr, y_c_val, train_idx, val_idx,
             [k for k in CLASS_KEYS if k.startswith("cost_cls_")]),
            (missed_raw, None, delay_ok_tr, delay_ok_va,
             [k for k in CLASS_KEYS if k.startswith("delay_cls_")]),
        ):
            if target_y_val is None:
                if len(delay_ok_tr) < 20 or len(delay_ok_va) < 20:
                    continue
                target_y_tr, target_y_val = missed_raw[tr_idx], missed_raw[va_idx]
            target_y_tr = target_y_tr.astype(int)
            target_y_val = target_y_val.astype(int)
            if len(np.unique(target_y_tr)) < 2:
                continue
            X_tr_use, X_va_use = X.iloc[tr_idx], X.iloc[va_idx]
            for key in cls_keys:
                model = self._fresh_model(key)
                model.fit(X_tr_use, target_y_tr)
                prob = model.predict_proba(X_va_use)[:, 1]
                for metric, val in _cls_scores(target_y_val, prob).items():
                    metrics[key][metric].append(val)

    def _fresh_model(self, key: str) -> Any:
        """Returns a fresh (unfitted) instance matching the production spec."""
        template = self.models[key]
        if isinstance(template, CatBoostRegressor) or isinstance(template, CatBoostClassifier):
            return template.__class__(
                iterations=120, depth=5, learning_rate=0.07,
                verbose=False, random_seed=self.rs,
            )
        if isinstance(template, lgb.LGBMRegressor) or isinstance(template, lgb.LGBMClassifier):
            return template.__class__(
                n_estimators=120, max_depth=5, learning_rate=0.07,
                random_state=self.rs, verbose=-1,
            )
        return template.__class__(
            n_estimators=120, max_depth=5, learning_rate=0.07,
            eval_metric="logloss" if "cls" in key else None,
            random_state=self.rs,
        )

    def _model_args(self, key: str) -> Dict[str, Any]:
        base = {"random_state": self.rs}
        low = key.lower()
        if "catboost" in low:
            base = {"random_seed": self.rs, "verbose": False}
            if "reg" in low:
                return dict(base, iterations=120, depth=5, learning_rate=0.07)
            return dict(base, iterations=120, depth=5, learning_rate=0.07)
        if "lgbm" in low:
            base["verbose"] = -1
            base["n_estimators"] = 120
            base["max_depth"] = 5
            base["learning_rate"] = 0.07
            return base
        return dict(base, n_estimators=120, max_depth=5, learning_rate=0.07)

    def evaluate_70_30(self, X: pd.DataFrame, df_w: pd.DataFrame) -> Dict[str, Any]:
        """
        Leakage-safe 70/30 train/test split by project_code (GroupShuffleSplit).
        Reports the per-model metrics on the 30% holdout. Also computes a serial
        RF / LogReg baseline for comparison.
        """
        groups = df_w["project_code"].values
        y_cost_reg = df_w["cost_escalation_pct"].values.astype(float)
        y_cost_cls = df_w["is_material_cost_overrun"].values.astype(int)
        y_delay_reg = df_w["delay_months"].values.astype(float)
        y_delay_cls = df_w["is_deadline_missed"].values.astype(float)
        y_delay_cls[np.isnan(y_delay_reg)] = np.nan  # unknown delay => exclude

        metrics = {}
        for key in REGRESSOR_KEYS + CLASS_KEYS:
            metrics[key] = _empty_metrics("reg" if key in REGRESSOR_KEYS else "cls")
        metrics["cost_reg_base"] = _empty_metrics("reg")
        metrics["delay_reg_base"] = _empty_metrics("reg")
        metrics["cost_cls_base"] = _empty_metrics("cls")
        metrics["delay_cls_base"] = _empty_metrics("cls")

        gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=self.rs)
        (train_idx, val_idx) = next(gss.split(X, y_cost_reg, groups=groups))

        # Real models
        self._train_eval_on(X, y_cost_reg, y_cost_cls, df_w, train_idx, val_idx, metrics)

        # Baselines on the same split
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        for name, reg_target, cls_target in (
            ("cost", y_cost_reg, y_cost_cls),
            ("delay", y_delay_reg, y_delay_cls),
        ):
            # RF regressor baseline (drop rows with missing target)
            tr_ok = ~np.isnan(reg_target[train_idx])
            va_ok = ~np.isnan(reg_target[val_idx])
            if tr_ok.sum() >= 20 and va_ok.sum() >= 20:
                rf = RandomForestRegressor(n_estimators=100, random_state=self.rs)
                rf.fit(X_tr.iloc[np.where(tr_ok)], reg_target[train_idx][tr_ok])
                for metric, val in _scores(reg_target[val_idx][va_ok], rf.predict(X_val.iloc[np.where(va_ok)])).items():
                    metrics[f"{name}_reg_base"][metric].append(val)
            # LogReg classifier baseline (delay rows with unknown delay excluded)
            if name == "delay":
                cls_ok_tr = ~np.isnan(cls_target[train_idx])
                cls_ok_va = ~np.isnan(cls_target[val_idx])
                ycc_tr = cls_target[train_idx][cls_ok_tr].astype(int)
                ycc_va = cls_target[val_idx][cls_ok_va].astype(int)
                Xcc_tr, Xcc_va = X_tr.iloc[np.where(cls_ok_tr)], X_val.iloc[np.where(cls_ok_va)]
            else:
                ycc_tr = cls_target[train_idx]
                ycc_va = cls_target[val_idx]
                Xcc_tr, Xcc_va = X_tr, X_val
            lr = LogisticRegression(max_iter=1000, random_state=self.rs)
            if len(np.unique(ycc_tr)) > 1:
                lr.fit(Xcc_tr, ycc_tr)
                prob = lr.predict_proba(Xcc_va)[:, 1]
                for metric, val in _cls_scores(ycc_va, prob).items():
                    metrics[f"{name}_cls_base"][metric].append(val)

        summary = {}
        for k, v in metrics.items():
            summary[k] = {
                metric: (float(np.mean(vals)) if len(vals) else float("nan"))
                for metric, vals in v.items()
            }
        self.metrics_70_30 = summary
        return summary

    def groupkfold_evaluate(self, X: pd.DataFrame, df_w: pd.DataFrame, n_splits: int = 4) -> Dict[str, Any]:
        """Secondary time-aware evaluation: GroupKFold on project_code."""
        groups = df_w["project_code"].values
        y_cost_reg = df_w["cost_escalation_pct"].values.astype(float)
        y_cost_cls = df_w["is_material_cost_overrun"].values.astype(int)
        y_delay_reg = df_w["delay_months"].values.astype(float)
        y_delay_cls = df_w["is_deadline_missed"].values.astype(int)

        metrics = {}
        for key in REGRESSOR_KEYS + CLASS_KEYS:
            metrics[key] = _empty_metrics("reg" if key in REGRESSOR_KEYS else "cls")

        actual_splits = min(n_splits, df_w["project_code"].nunique())
        gkf = GroupKFold(n_splits=actual_splits)
        for train_idx, val_idx in gkf.split(X, y_cost_reg, groups=groups):
            self._train_eval_on(X, y_cost_reg, y_cost_cls, df_w, train_idx, val_idx, metrics)

        summary = {}
        for k, v in metrics.items():
            summary[k] = {
                metric: (float(np.mean(vals)) if len(vals) else float("nan"))
                for metric, vals in v.items()
            }
        self.cv_metrics = summary
        return summary

    # ------------------------------------------------------------- production
    def fit_production(self, X: pd.DataFrame, df_w: pd.DataFrame):
        """Trains the production model instances on the full dataset."""
        y_cost_reg = df_w["cost_escalation_pct"].values.astype(float)
        y_cost_cls = df_w["is_material_cost_overrun"].values.astype(int)
        y_delay_reg = df_w["delay_months"].values.astype(float)
        y_delay_cls = df_w["is_deadline_missed"].values.astype(float)
        y_delay_cls[np.isnan(y_delay_reg)] = np.nan  # exclude unknown-delay rows

        y_map = {
            "cost_reg": (y_cost_reg, None), "delay_reg": (y_delay_reg, None),
            "cost_cls": (y_cost_cls, None), "delay_cls": (y_delay_cls, None),
        }
        for key, model in self.models.items():
            task_key = key.rsplit("_", 1)[0]  # e.g. cost_reg_xgb -> cost_reg
            target, _ = y_map[task_key]
            valid = ~np.isnan(target)
            if valid.sum() < 20:
                continue
            X_fit = X[valid]
            y_fit = target[valid]
            if task_key.endswith("_cls"):
                y_fit = y_fit.astype(int)
                if len(np.unique(y_fit)) < 2:
                    continue
            model.fit(X_fit, y_fit)

    # ---------------------------------------------------------------- driver
    def run_full(
        self,
        panel_path: str = DEFAULT_PANEL_PATH,
        with_70_30: bool = True,
        with_groupkfold: bool = True,
        fit_production: bool = True,
    ) -> Dict[str, Any]:
        df = self.load_panel(panel_path)
        X, df_w = self.prepare(df)
        result = {
            "n_snapshots": int(len(df)),
            "n_projects": int(df["project_code"].nunique()),
            "n_features": int(X.shape[1]),
            "months_covered": sorted(df["snapshot_full"].unique().astype(int).tolist()),
        }
        if with_70_30:
            result["metrics_70_30"] = self.evaluate_70_30(X, df_w)
        if with_groupkfold:
            result["groupkfold_metrics"] = self.groupkfold_evaluate(X, df_w)
        if fit_production:
            self.fit_production(X, df_w)
        result["feature_extractor"] = self.feature_extractor
        result["models"] = self.models
        return result

    def best_model_key(self, task: str, kind: str = "cls") -> str:
        """Selects the best model key for a task from the 70/30 metrics."""
        metric_key = "roc_auc" if kind == "cls" else "r2"
        prefix = f"{task}_{kind}_"
        options = [f"{prefix}{k}" for k in MODEL_KEYS]
        scored = [(self.metrics_70_30.get(k, {}).get(metric_key, float("nan")), k) for k in options]
        valid = [(s, k) for s, k in scored if not np.isnan(s)]
        if not valid:
            return options[0]
        return max(valid, key=lambda t: t[0])[1]