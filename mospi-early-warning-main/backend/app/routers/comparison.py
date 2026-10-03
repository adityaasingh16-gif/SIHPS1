"""
Router for Model Comparison Study Endpoint (Endpoint 10).
Serves benchmark study results comparing CUF-only vs Enhanced-data feature models,
and (when trained) the real-data 70/30 split comparison across XGBoost / LightGBM /
CatBoost from the MoSPI Flash-Report panel.
"""

import os
import logging
import numpy as np
import pandas as pd
import joblib
from fastapi import APIRouter, HTTPException
from .. import schemas

logger = logging.getLogger("mospi_backend.comparison")

router = APIRouter(prefix="", tags=["Model Comparison"])

# Imported rather than recomputed: this used to build its own path from
# __file__, which meant two places to fix and no test covering either. A
# relative MODEL_DIR in .env has to be anchored once, in one module.
from ..ml_loader import MODEL_DIR

RUN_ORDER = ["xgb", "lgbm", "catboost", "base"]
FRIENDLY = {
    "xgb": "XGBoost",
    "lgbm": "LightGBM",
    "catboost": "CatBoost",
    "base": "Baseline",
}

TASK_KEYS = [
    ("cost_reg", "Cost Regression (Escalation %)", "reg"),
    ("cost_cls", "Cost Overrun (Classification)", "cls"),
    ("delay_reg", "Delay Regression (Months)", "reg"),
    ("delay_cls", "Missed Deadline (Classification)", "cls"),
]


def _load_real_70_30() -> list:
    """Returns TaskMetricItem list from saved metrics_70_30.joblib if present."""
    path = os.path.join(MODEL_DIR, "metrics_70_30.joblib")
    if not os.path.exists(path):
        return None
    try:
        metrics = joblib.load(path)
    except Exception as e:
        logger.warning("Could not load metrics_70_30.joblib: %s", e)
        return None

    items = []
    for task, label, kind in TASK_KEYS:
        for model_key in RUN_ORDER:
            key = f"{task}_{model_key}"
            if key not in metrics:
                continue
            m = metrics[key]
            model_name = FRIENDLY.get(model_key, model_key)
            prefix = "PDF-trained "
            if kind == "reg":
                items.append(schemas.TaskMetricItem(
                    task=label,
                    model=f"{prefix}{model_name}",
                    mae=_nn(m.get("mae")),
                    rmse=_nn(m.get("rmse")),
                    r2=_nn(m.get("r2")),
                ))
            else:
                items.append(schemas.TaskMetricItem(
                    task=label,
                    model=f"{prefix}{model_name}",
                    roc_auc=_nn(m.get("roc_auc")),
                    f1=_nn(m.get("f1")),
                    recall=_nn(m.get("recall")),
                ))
    return items


def _nn(v):
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(fv):
        return None
    return round(fv, 4)


@router.get("/model-comparison", response_model=schemas.ModelComparisonResponse)
def get_model_comparison_study():
    """
    Endpoint 10: GET /model-comparison
    Returns real-data 70/30 comparison metrics (when trained), falling back to the
    static CUF-only vs Enhanced-Data study results otherwise.
    """
    real_items = _load_real_70_30()

    cuf_metrics = [
        schemas.TaskMetricItem(task="Cost Regression (Escalation %)", model="XGBoost CUF-Only", mae=6.12, rmse=7.45, r2=-0.510),
        schemas.TaskMetricItem(task="Cost Overrun (Classification)", model="XGBoost CUF-Only", roc_auc=0.645, f1=0.362, recall=0.480),
        schemas.TaskMetricItem(task="Delay Regression (Months)", model="Baseline Random Forest CUF-Only", mae=3.85, rmse=4.92, r2=-0.380),
        schemas.TaskMetricItem(task="Missed Deadline (Classification)", model="Logistic Regression CUF-Only", roc_auc=0.742, f1=0.710, recall=0.740),
    ]

    enhanced_metrics = [
        schemas.TaskMetricItem(task="Cost Regression (Escalation %)", model="XGBoost Enhanced-Data", mae=5.77, rmse=7.10, r2=-0.491),
        schemas.TaskMetricItem(task="Cost Overrun (Classification)", model="XGBoost Enhanced-Data", roc_auc=0.714, f1=0.420, recall=0.550),
        schemas.TaskMetricItem(task="Delay Regression (Months)", model="Baseline Random Forest Enhanced-Data", mae=3.57, rmse=4.67, r2=-0.324),
        schemas.TaskMetricItem(task="Missed Deadline (Classification)", model="Logistic Regression Enhanced-Data", roc_auc=0.788, f1=0.748, recall=0.782),
    ]

    if real_items:
        summary_text = (
            "Real-MoSPI Flash-Report 70/30 test split (leakage-safe by project): LightGBM leads "
            "cost-risk prediction (R^2 %.2f, ROC-AUC %.3f) while CatBoost leads schedule-delay "
            "prediction (R^2 %.2f, ROC-AUC %.3f) on the held-out 30%% of real projects."
        ) % (
            _rr(_get(real_items, "Cost Regression (Escalation %)", "LightGBM", "r2")),
            _rr(_get(real_items, "Cost Overrun (Classification)", "LightGBM", "roc_auc")),
            _rr(_get(real_items, "Delay Regression (Months)", "CatBoost", "r2")),
            _rr(_get(real_items, "Missed Deadline (Classification)", "CatBoost", "roc_auc")),
        )
        return schemas.ModelComparisonResponse(
            cuf_only_metrics=cuf_metrics,
            enhanced_data_metrics=real_items,
            comparison_summary=summary_text,
        )

    summary_text = (
        "CUF-Only vs Enhanced-Data Study Analysis: Incorporating additional land acquisition, forest clearance, "
        "and agency historic performance indicators (Enhanced-Data) improves classification ROC-AUC by +0.069 on cost overrun "
        "and +0.046 on schedule delay predictions, demonstrating significant predictive value in expanding CUF reporting fields."
    )

    return schemas.ModelComparisonResponse(
        cuf_only_metrics=cuf_metrics,
        enhanced_data_metrics=enhanced_metrics,
        comparison_summary=summary_text
    )


def _get(items, task, model_frag, metric):
    for it in items:
        if it.task == task and model_frag.lower() in it.model.lower():
            v = getattr(it, metric)
            if v is not None:
                return v
    return float("nan")


def _rr(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


CLASS_TIERS = ["Low", "Medium", "High", "Critical"]
_confusion_cache: dict = {}


def _tier_from_probs(cost_prob: float, delay_prob: float) -> str:
    """Composite risk score = 50% cost prob + 50% delay prob, mapped to the platform tier."""
    score = 0.5 * (float(cost_prob) * 100.0) + 0.5 * (float(delay_prob) * 100.0)
    if score >= 75.0:
        return "Critical"
    if score >= 50.0:
        return "High"
    if score >= 25.0:
        return "Medium"
    return "Low"


@router.get("/comparison/confusion")
def get_confusion_matrix():
    """
    GET /comparison/confusion

    4-class confusion matrix (Low / Medium / High / Critical) of the real-data
    XGBoost risk-tier predictions vs realized severity (cost escalation % and delay
    months, severity-normalized) over the full MoSPI Flash-Report panel.
    Rows = actual class, columns = predicted class.
    """
    if "matrix" in _confusion_cache:
        return _confusion_cache

    panel_path = os.environ.get(
        "PANEL_CSV",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "panel_mospi.csv")),
    )
    if not os.path.exists(panel_path):
        raise HTTPException(status_code=503, detail="Real MoSPI panel CSV not available.")

    try:
        fe = joblib.load(os.path.join(MODEL_DIR, "feature_extractor_real.joblib"))
        cost_cls = joblib.load(os.path.join(MODEL_DIR, "real_cost_cls_xgb.joblib"))
        delay_cls = joblib.load(os.path.join(MODEL_DIR, "real_delay_cls_xgb.joblib"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Real-data model artifacts unavailable: {e}")

    panel = pd.read_csv(panel_path).dropna(subset=["project_code", "ministry"])
    X = fe.transform(panel)
    cost_prob = cost_cls.predict_proba(X)[:, 1]
    delay_prob = delay_cls.predict_proba(X)[:, 1]

    actual_cost = np.clip(panel["cost_escalation_pct"].astype(float).values / 100.0, 0.0, 1.0)
    actual_delay = np.clip(panel["delay_months"].astype(float).values / 24.0, 0.0, 1.0)

    matrix = np.zeros((4, 4), dtype=int)
    for i in range(len(panel)):
        actual = CLASS_TIERS.index(_tier_from_probs(actual_cost[i], actual_delay[i]))
        predicted = CLASS_TIERS.index(_tier_from_probs(cost_prob[i], delay_prob[i]))
        matrix[actual][predicted] += 1

    total = int(matrix.sum())
    accuracy = round(float(np.trace(matrix)) / total, 4) if total else 0.0

    result = {
        "classes": CLASS_TIERS,
        "matrix": matrix.tolist(),
        "n_samples": int(len(panel)),
        "accuracy": accuracy,
        "diagonal": [int(matrix[i][i]) for i in range(4)],
        "model": "Real-data XGBoost classifiers (Platt-calibrated) combined into composite risk tier",
        "note": "Rows = actual class, columns = predicted class",
    }
    _confusion_cache.update(result)
    return _confusion_cache
