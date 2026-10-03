"""
Module 3: Dual ML Risk Engines (Cost & Delay)
Trains and evaluates regression and classification models for Cost Escalation and Schedule Delay using GroupKFold on project_id.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    roc_auc_score, f1_score, precision_score, recall_score
)
import xgboost as xgb
from .mlp_engine import MLPDropoutClassifier
from .config import PipelineConfig

class DualRiskEngine:
    """
    Dual Machine Learning Risk Engine managing Cost and Delay modeling pipelines.
    Runs time-aware / grouped cross-validation to prevent duplicate project leakage.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        
        # Production model instances (trained on full dataset)
        self.cost_reg_xgb = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=self.config.random_seed)
        self.cost_cls_xgb = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, eval_metric="logloss", random_state=self.config.random_seed)
        self.delay_reg_xgb = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=self.config.random_seed)
        self.delay_cls_xgb = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, eval_metric="logloss", random_state=self.config.random_seed)

        # MLP-with-dropout production classifiers (trained on full dataset alongside XGBoost)
        self.cost_cls_mlp = MLPDropoutClassifier(
            hidden_sizes=(64, 32), dropout_rate=0.3,
            learning_rate=0.01, epochs=25, batch_size=64,
            random_state=self.config.random_seed,
        )
        self.delay_cls_mlp = MLPDropoutClassifier(
            hidden_sizes=(64, 32), dropout_rate=0.3,
            learning_rate=0.01, epochs=25, batch_size=64,
            random_state=self.config.random_seed,
        )

    def train_and_evaluate(
        self, 
        X: pd.DataFrame, 
        df_full: pd.DataFrame, 
        n_splits: int = 5
    ) -> Dict[str, Any]:
        """
        Executes GroupKFold cross-validation on project_id and returns model performance metrics.
        """
        groups = df_full["project_id"]
        # Ensure n_splits does not exceed unique project count
        actual_splits = min(n_splits, groups.nunique())
        gkf = GroupKFold(n_splits=actual_splits)
        
        y_cost_reg = df_full[self.config.features.TARGET_COST_REG].values
        y_cost_cls = df_full[self.config.features.TARGET_COST_CLASS].values
        y_delay_reg = df_full[self.config.features.TARGET_DELAY_REG].values
        y_delay_cls = df_full[self.config.features.TARGET_DELAY_CLASS].values
        
        metrics = {
            "cost_reg_xgb": {"mae": [], "rmse": [], "r2": []},
            "cost_reg_base": {"mae": [], "rmse": [], "r2": []},
            "cost_cls_xgb": {"roc_auc": [], "f1": [], "precision": [], "recall": []},
            "cost_cls_base": {"roc_auc": [], "f1": [], "precision": [], "recall": []},
            "delay_reg_xgb": {"mae": [], "rmse": [], "r2": []},
            "delay_reg_base": {"mae": [], "rmse": [], "r2": []},
            "delay_cls_xgb": {"roc_auc": [], "f1": [], "precision": [], "recall": []},
            "delay_cls_base": {"roc_auc": [], "f1": [], "precision": [], "recall": []},
            "cost_cls_mlp": {"roc_auc": [], "f1": [], "precision": [], "recall": []},
            "delay_cls_mlp": {"roc_auc": [], "f1": [], "precision": [], "recall": []},
        }
        
        for train_idx, val_idx in gkf.split(X, y_cost_reg, groups=groups):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            
            # --- 1. Cost Regression ---
            cr_xgb = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=self.config.random_seed)
            cr_xgb.fit(X_tr, y_cost_reg[train_idx])
            pred_cr_xgb = cr_xgb.predict(X_val)
            metrics["cost_reg_xgb"]["mae"].append(mean_absolute_error(y_cost_reg[val_idx], pred_cr_xgb))
            metrics["cost_reg_xgb"]["rmse"].append(np.sqrt(mean_squared_error(y_cost_reg[val_idx], pred_cr_xgb)))
            metrics["cost_reg_xgb"]["r2"].append(r2_score(y_cost_reg[val_idx], pred_cr_xgb))
            
            cr_base = RandomForestRegressor(n_estimators=100, random_state=self.config.random_seed)
            cr_base.fit(X_tr, y_cost_reg[train_idx])
            pred_cr_base = cr_base.predict(X_val)
            metrics["cost_reg_base"]["mae"].append(mean_absolute_error(y_cost_reg[val_idx], pred_cr_base))
            metrics["cost_reg_base"]["rmse"].append(np.sqrt(mean_squared_error(y_cost_reg[val_idx], pred_cr_base)))
            metrics["cost_reg_base"]["r2"].append(r2_score(y_cost_reg[val_idx], pred_cr_base))
            
            # --- 2. Cost Classification ---
            y_cc_tr, y_cc_val = y_cost_cls[train_idx], y_cost_cls[val_idx]
            if len(np.unique(y_cc_tr)) > 1:
                cc_xgb = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, eval_metric="logloss", random_state=self.config.random_seed)
                cc_xgb.fit(X_tr, y_cc_tr)
                prob_cc_xgb = cc_xgb.predict_proba(X_val)[:, 1]
                pred_cc_xgb = (prob_cc_xgb >= 0.5).astype(int)
                
                if len(np.unique(y_cc_val)) > 1:
                    metrics["cost_cls_xgb"]["roc_auc"].append(roc_auc_score(y_cc_val, prob_cc_xgb))
                metrics["cost_cls_xgb"]["f1"].append(f1_score(y_cc_val, pred_cc_xgb, zero_division=0))
                metrics["cost_cls_xgb"]["precision"].append(precision_score(y_cc_val, pred_cc_xgb, zero_division=0))
                metrics["cost_cls_xgb"]["recall"].append(recall_score(y_cc_val, pred_cc_xgb, zero_division=0))
                
                cc_base = LogisticRegression(max_iter=1000, random_state=self.config.random_seed)
                cc_base.fit(X_tr, y_cc_tr)
                prob_cc_base = cc_base.predict_proba(X_val)[:, 1]
                pred_cc_base = (prob_cc_base >= 0.5).astype(int)
                if len(np.unique(y_cc_val)) > 1:
                    metrics["cost_cls_base"]["roc_auc"].append(roc_auc_score(y_cc_val, prob_cc_base))
                metrics["cost_cls_base"]["f1"].append(f1_score(y_cc_val, pred_cc_base, zero_division=0))
                metrics["cost_cls_base"]["precision"].append(precision_score(y_cc_val, pred_cc_base, zero_division=0))
                metrics["cost_cls_base"]["recall"].append(recall_score(y_cc_val, pred_cc_base, zero_division=0))
            
            # --- 3. Delay Regression ---
            dr_xgb = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=self.config.random_seed)
            dr_xgb.fit(X_tr, y_delay_reg[train_idx])
            pred_dr_xgb = dr_xgb.predict(X_val)
            metrics["delay_reg_xgb"]["mae"].append(mean_absolute_error(y_delay_reg[val_idx], pred_dr_xgb))
            metrics["delay_reg_xgb"]["rmse"].append(np.sqrt(mean_squared_error(y_delay_reg[val_idx], pred_dr_xgb)))
            metrics["delay_reg_xgb"]["r2"].append(r2_score(y_delay_reg[val_idx], pred_dr_xgb))
            
            dr_base = RandomForestRegressor(n_estimators=100, random_state=self.config.random_seed)
            dr_base.fit(X_tr, y_delay_reg[train_idx])
            pred_dr_base = dr_base.predict(X_val)
            metrics["delay_reg_base"]["mae"].append(mean_absolute_error(y_delay_reg[val_idx], pred_dr_base))
            metrics["delay_reg_base"]["rmse"].append(np.sqrt(mean_squared_error(y_delay_reg[val_idx], pred_dr_base)))
            metrics["delay_reg_base"]["r2"].append(r2_score(y_delay_reg[val_idx], pred_dr_base))
            
            # --- 4. Delay Classification ---
            y_dc_tr, y_dc_val = y_delay_cls[train_idx], y_delay_cls[val_idx]
            if len(np.unique(y_dc_tr)) > 1:
                dc_xgb = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, eval_metric="logloss", random_state=self.config.random_seed)
                dc_xgb.fit(X_tr, y_dc_tr)
                prob_dc_xgb = dc_xgb.predict_proba(X_val)[:, 1]
                pred_dc_xgb = (prob_dc_xgb >= 0.5).astype(int)
                
                if len(np.unique(y_dc_val)) > 1:
                    metrics["delay_cls_xgb"]["roc_auc"].append(roc_auc_score(y_dc_val, prob_dc_xgb))
                metrics["delay_cls_xgb"]["f1"].append(f1_score(y_dc_val, pred_dc_xgb, zero_division=0))
                metrics["delay_cls_xgb"]["precision"].append(precision_score(y_dc_val, pred_dc_xgb, zero_division=0))
                metrics["delay_cls_xgb"]["recall"].append(recall_score(y_dc_val, pred_dc_xgb, zero_division=0))
                
                dc_base = LogisticRegression(max_iter=1000, random_state=self.config.random_seed)
                dc_base.fit(X_tr, y_dc_tr)
                prob_dc_base = dc_base.predict_proba(X_val)[:, 1]
                pred_dc_base = (prob_dc_base >= 0.5).astype(int)
                if len(np.unique(y_dc_val)) > 1:
                    metrics["delay_cls_base"]["roc_auc"].append(roc_auc_score(y_dc_val, prob_dc_base))
                metrics["delay_cls_base"]["f1"].append(f1_score(y_dc_val, pred_dc_base, zero_division=0))
                metrics["delay_cls_base"]["precision"].append(precision_score(y_dc_val, pred_dc_base, zero_division=0))
                metrics["delay_cls_base"]["recall"].append(recall_score(y_dc_val, pred_dc_base, zero_division=0))

            # --- 5. MLP with Dropout Classifiers (comparison baselines) ---
            if len(np.unique(y_cc_tr)) > 1:
                mlp_cost = MLPDropoutClassifier(
                    hidden_sizes=(64, 32), dropout_rate=0.3,
                    learning_rate=0.01, epochs=25, batch_size=64,
                    random_state=self.config.random_seed,
                )
                mlp_cost.fit(X_tr.values, y_cc_tr)
                prob_mlp_cost = mlp_cost.predict_proba(X_val.values)
                pred_mlp_cost = (prob_mlp_cost >= 0.5).astype(int)
                if len(np.unique(y_cc_val)) > 1:
                    metrics["cost_cls_mlp"]["roc_auc"].append(roc_auc_score(y_cc_val, prob_mlp_cost))
                metrics["cost_cls_mlp"]["f1"].append(f1_score(y_cc_val, pred_mlp_cost, zero_division=0))
                metrics["cost_cls_mlp"]["precision"].append(precision_score(y_cc_val, pred_mlp_cost, zero_division=0))
                metrics["cost_cls_mlp"]["recall"].append(recall_score(y_cc_val, pred_mlp_cost, zero_division=0))

            if len(np.unique(y_dc_tr)) > 1:
                mlp_delay = MLPDropoutClassifier(
                    hidden_sizes=(64, 32), dropout_rate=0.3,
                    learning_rate=0.01, epochs=25, batch_size=64,
                    random_state=self.config.random_seed,
                )
                mlp_delay.fit(X_tr.values, y_dc_tr)
                prob_mlp_delay = mlp_delay.predict_proba(X_val.values)
                pred_mlp_delay = (prob_mlp_delay >= 0.5).astype(int)
                if len(np.unique(y_dc_val)) > 1:
                    metrics["delay_cls_mlp"]["roc_auc"].append(roc_auc_score(y_dc_val, prob_mlp_delay))
                metrics["delay_cls_mlp"]["f1"].append(f1_score(y_dc_val, pred_mlp_delay, zero_division=0))
                metrics["delay_cls_mlp"]["precision"].append(precision_score(y_dc_val, pred_mlp_delay, zero_division=0))
                metrics["delay_cls_mlp"]["recall"].append(recall_score(y_dc_val, pred_mlp_delay, zero_division=0))

        # Fit final production models on full dataset
        self.cost_reg_xgb.fit(X, y_cost_reg)
        self.cost_cls_xgb.fit(X, y_cost_cls)
        self.delay_reg_xgb.fit(X, y_delay_reg)
        self.delay_cls_xgb.fit(X, y_delay_cls)

        # Fit final production MLP classifiers on full dataset
        print("\n  [MLP] Training production cost classifier with dropout...")
        self.cost_cls_mlp.fit(X.values, y_cost_cls)
        print("  [MLP] Training production delay classifier with dropout...")
        self.delay_cls_mlp.fit(X.values, y_delay_cls)
        
        # Aggregate mean CV scores safely
        cv_summary = {}
        for k, v in metrics.items():
            cv_summary[k] = {metric: float(np.mean(vals)) if len(vals) > 0 else 0.0 for metric, vals in v.items()}
            
        return cv_summary

    def rolling_origin_evaluate(
        self,
        X: pd.DataFrame,
        df_full: pd.DataFrame,
        min_history_months: int = 6,
        step_months: int = 3,
    ) -> Dict[str, Any]:
        """
        Genuine time-aware / rolling-origin validation, in addition to GroupKFold.

        GroupKFold (used in train_and_evaluate) prevents the SAME project from appearing
        in both train and test, but it does not test whether the model can predict a
        LATER outcome using only EARLIER snapshot information. This method does exactly
        that: it repeatedly trains on all snapshots up to month T (across all projects)
        and evaluates on snapshots from month T+1 onward, mimicking how the system would
        actually be used month-by-month as an early-warning tool.
        """
        if "snapshot_month" not in df_full.columns:
            return {
                "method": "rolling_origin_time_aware_validation",
                "description": "Skipped: snapshot_month column not present in dataframe.",
                "per_cutoff_results": [],
            }

        months = sorted(df_full["snapshot_month"].unique())
        max_month = max(months)
        cutoffs = [m for m in range(min_history_months, max_month, step_months)]

        results = []
        for cutoff in cutoffs:
            train_mask = df_full["snapshot_month"] <= cutoff
            test_mask = df_full["snapshot_month"] > cutoff

            if train_mask.sum() < 20 or test_mask.sum() < 20:
                continue

            X_tr, X_te = X[train_mask], X[test_mask]
            y_cost_tr = df_full.loc[train_mask, self.config.features.TARGET_COST_REG].values
            y_cost_te = df_full.loc[test_mask, self.config.features.TARGET_COST_REG].values
            y_delay_tr = df_full.loc[train_mask, self.config.features.TARGET_DELAY_REG].values
            y_delay_te = df_full.loc[test_mask, self.config.features.TARGET_DELAY_REG].values
            y_cost_cls_tr = df_full.loc[train_mask, self.config.features.TARGET_COST_CLASS].values
            y_cost_cls_te = df_full.loc[test_mask, self.config.features.TARGET_COST_CLASS].values
            y_delay_cls_tr = df_full.loc[train_mask, self.config.features.TARGET_DELAY_CLASS].values
            y_delay_cls_te = df_full.loc[test_mask, self.config.features.TARGET_DELAY_CLASS].values

            row = {"cutoff_month": cutoff, "n_train": int(train_mask.sum()), "n_test": int(test_mask.sum())}

            cr = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=self.config.random_seed)
            cr.fit(X_tr, y_cost_tr)
            pred = cr.predict(X_te)
            row["cost_mae"] = float(mean_absolute_error(y_cost_te, pred))
            row["cost_r2"] = float(r2_score(y_cost_te, pred))

            dr = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=self.config.random_seed)
            dr.fit(X_tr, y_delay_tr)
            pred_d = dr.predict(X_te)
            row["delay_mae"] = float(mean_absolute_error(y_delay_te, pred_d))
            row["delay_r2"] = float(r2_score(y_delay_te, pred_d))

            if len(np.unique(y_cost_cls_tr)) > 1 and len(np.unique(y_cost_cls_te)) > 1:
                cc = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, eval_metric="logloss", random_state=self.config.random_seed)
                cc.fit(X_tr, y_cost_cls_tr)
                prob = cc.predict_proba(X_te)[:, 1]
                row["cost_cls_roc_auc"] = float(roc_auc_score(y_cost_cls_te, prob))

            if len(np.unique(y_delay_cls_tr)) > 1 and len(np.unique(y_delay_cls_te)) > 1:
                dc = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, eval_metric="logloss", random_state=self.config.random_seed)
                dc.fit(X_tr, y_delay_cls_tr)
                prob_d = dc.predict_proba(X_te)[:, 1]
                row["delay_cls_roc_auc"] = float(roc_auc_score(y_delay_cls_te, prob_d))

            results.append(row)

        return {
            "method": "rolling_origin_time_aware_validation",
            "description": (
                "At each cutoff month T, the model is trained ONLY on snapshots with "
                "snapshot_month <= T and evaluated on snapshots with snapshot_month > T. "
                "This directly tests the early-warning claim: predicting a later outcome "
                "using only information available at or before the prediction time."
            ),
            "per_cutoff_results": results,
        }
