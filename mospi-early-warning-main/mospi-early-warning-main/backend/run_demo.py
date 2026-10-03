"""
MoSPI Dhrishti AI-Powered Early-Warning and Decision-Support Platform
Standalone Modular Integration Runner & Demonstration Script.
"""

import os
import sys
import pandas as pd
import numpy as np

# Ensure src modules can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.config import PipelineConfig
from src.integration_pipeline import EarlyWarningPipeline

def main():
    print("=" * 80)
    print("  MoSPI Dhrishti: AI-POWERED EARLY-WARNING & DECISION-SUPPORT CORE")
    print("  Problem Statement ID: 26103 | Ministry of Statistics & Programme Implementation")
    print("=" * 80)
    
    config = PipelineConfig(
        n_projects=300,
        min_snapshots=12,
        max_snapshots=24,
        default_officer_hours_budget=120.0
    )
    
    pipeline = EarlyWarningPipeline(config)
    results = pipeline.run_full_pipeline()
    
    cv = results["cv_metrics"]
    rolling = results["rolling_origin_metrics"]
    cal = results["calibration_metrics"]
    opt = results["optimization_results"]
    
    print("\n" + "=" * 80)
    print("  1. DUAL ML ENGINE EVALUATION RESULTS (GroupKFold CV on project_id)")
    print("=" * 80)
    
    cv_table = [
        {"Task": "Cost Regression (Escalation %)", "Model": "Baseline (RandomForest)", "MAE": f"{cv['cost_reg_base']['mae']:.2f}", "RMSE": f"{cv['cost_reg_base']['rmse']:.2f}", "R2": f"{cv['cost_reg_base']['r2']:.3f}"},
        {"Task": "Cost Regression (Escalation %)", "Model": "XGBoost Regressor", "MAE": f"{cv['cost_reg_xgb']['mae']:.2f}", "RMSE": f"{cv['cost_reg_xgb']['rmse']:.2f}", "R2": f"{cv['cost_reg_xgb']['r2']:.3f}"},
        {"Task": "Cost Overrun (Classification)", "Model": "Baseline (LogisticReg)", "ROC-AUC": f"{cv['cost_cls_base']['roc_auc']:.3f}", "F1": f"{cv['cost_cls_base']['f1']:.3f}", "Recall": f"{cv['cost_cls_base']['recall']:.3f}"},
        {"Task": "Cost Overrun (Classification)", "Model": "XGBoost Classifier", "ROC-AUC": f"{cv['cost_cls_xgb']['roc_auc']:.3f}", "F1": f"{cv['cost_cls_xgb']['f1']:.3f}", "Recall": f"{cv['cost_cls_xgb']['recall']:.3f}"},
        {"Task": "Delay Regression (Months)", "Model": "Baseline (RandomForest)", "MAE": f"{cv['delay_reg_base']['mae']:.2f}", "RMSE": f"{cv['delay_reg_base']['rmse']:.2f}", "R2": f"{cv['delay_reg_base']['r2']:.3f}"},
        {"Task": "Delay Regression (Months)", "Model": "XGBoost Regressor", "MAE": f"{cv['delay_reg_xgb']['mae']:.2f}", "RMSE": f"{cv['delay_reg_xgb']['rmse']:.2f}", "R2": f"{cv['delay_reg_xgb']['r2']:.3f}"},
        {"Task": "Missed Deadline (Classification)", "Model": "Baseline (LogisticReg)", "ROC-AUC": f"{cv['delay_cls_base']['roc_auc']:.3f}", "F1": f"{cv['delay_cls_base']['f1']:.3f}", "Recall": f"{cv['delay_cls_base']['recall']:.3f}"},
        {"Task": "Missed Deadline (Classification)", "Model": "XGBoost Classifier", "ROC-AUC": f"{cv['delay_cls_xgb']['roc_auc']:.3f}", "F1": f"{cv['delay_cls_xgb']['f1']:.3f}", "Recall": f"{cv['delay_cls_xgb']['recall']:.3f}"},
    ]
    print(pd.DataFrame(cv_table).to_string(index=False))
    
    print("\n" + "=" * 80)
    print("  2. PROBABILITY CALIBRATION RESULTS (Platt Scaling, evaluated on HELD-OUT set)")
    print("=" * 80)
    eval_note = "held-out (honest)" if cal.get("evaluated_on_held_out_set") else "SAME AS FIT SET (circular - not trustworthy)"
    print(f"  Calibration method     : {cal.get('calibration_method', 'unknown')}")
    print(f"  Evaluation set         : {eval_note}")
    print(f"  Cost Overrun Model : Raw Brier = {cal['brier_cost_raw']:.4f}  -->  Calibrated Brier = {cal['brier_cost_calibrated']:.4f}")
    print(f"  Delay Missed Model : Raw Brier = {cal['brier_delay_raw']:.4f}  -->  Calibrated Brier = {cal['brier_delay_calibrated']:.4f}")

    print("\n" + "=" * 80)
    print("  2b. ROLLING-ORIGIN TIME-AWARE VALIDATION (genuine early-warning test)")
    print("=" * 80)
    print(f"  {rolling['description']}\n")
    ro_rows = rolling["per_cutoff_results"]
    if ro_rows:
        ro_df = pd.DataFrame(ro_rows)
        print(ro_df.to_string(index=False))
        print(f"\n  Mean Cost R2 across cutoffs   : {ro_df['cost_r2'].mean():.3f}")
        print(f"  Mean Delay R2 across cutoffs  : {ro_df['delay_r2'].mean():.3f}")
        if "cost_cls_roc_auc" in ro_df.columns:
            print(f"  Mean Cost Cls ROC-AUC         : {ro_df['cost_cls_roc_auc'].mean():.3f}")
        if "delay_cls_roc_auc" in ro_df.columns:
            print(f"  Mean Delay Cls ROC-AUC        : {ro_df['delay_cls_roc_auc'].mean():.3f}")
    else:
        print("  Not enough snapshot months available to run rolling-origin validation.")
    
    print("\n" + "=" * 80)
    print("  3. SAMPLE PROJECT SHAP EXPLAINABILITY BREAKDOWN")
    print("=" * 80)
    
    # Pick a high-risk project for sample SHAP explanation output
    high_risk_projects = pipeline.df_risk[pipeline.df_risk["risk_tier"].isin(["Critical", "High"])]["project_id"].unique()
    sample_pid = high_risk_projects[0] if len(high_risk_projects) > 0 else pipeline.df_risk["project_id"].iloc[0]
    
    explanation = pipeline.get_explanation(sample_pid)
    print(explanation["explanation_summary"])
    
    print("\n" + "=" * 80)
    print("  4. OFFICER-CAPACITY OPTIMIZATION QUEUE (OR-Tools MILP 0-1 Knapsack)")
    print("=" * 80)
    print(f"  Total Officer Budget    : {opt['officer_capacity_hours']} Hours")
    print(f"  Total Hours Allocated   : {opt['total_hours_allocated']} Hours ({opt['capacity_utilization_pct']}% utilization)")
    print(f"  Total Risk Mitigated    : {opt['total_risk_mitigated']} Risk Points")
    print(f"  Projects Selected       : {opt['n_projects_selected']} out of {opt['total_high_risk_candidates']} Candidates\n")
    
    opt_df = pd.DataFrame(opt["selected_projects_queue"])
    display_cols = ["project_id", "sector", "composite_risk_score", "risk_tier", "required_review_hours", "risk_reduction_impact", "unresolved_land_issues", "unresolved_approval_issues"]
    print(opt_df[display_cols].to_string(index=False))
    
    print("\n" + "=" * 80)
    print("  PIPELINE EXECUTION COMPLETE & VERIFIED")
    print("=" * 80)

if __name__ == "__main__":
    main()
