"""
Unit and Property Tests for Dedicated TreeSHAP Engine.
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.config import PipelineConfig
from src.generator import MoSPIDataGenerator
from src.feature_pipeline import TemporalFeatureExtractor
from src.tree_shap_engine import TreeSHAPEngine


@pytest.fixture
def trained_sample_setup():
    """Generates a small dataset, fits feature extractor, and trains sample XGBoost models."""
    config = PipelineConfig(n_projects=10, min_snapshots=6, max_snapshots=12, random_seed=42)
    generator = MoSPIDataGenerator(config)
    df_raw = generator.generate_dataset()

    extractor = TemporalFeatureExtractor(config)
    extractor.fit(df_raw)
    X_features = extractor.transform(df_raw)

    y_cost = df_raw[config.features.TARGET_COST_CLASS].values
    y_delay = df_raw[config.features.TARGET_DELAY_CLASS].values

    cost_model = xgb.XGBClassifier(n_estimators=15, max_depth=3, random_state=42, eval_metric="logloss")
    delay_model = xgb.XGBClassifier(n_estimators=15, max_depth=3, random_state=42, eval_metric="logloss")

    cost_model.fit(X_features, y_cost)
    delay_model.fit(X_features, y_delay)

    engine = TreeSHAPEngine(
        cost_model=cost_model,
        delay_model=delay_model,
        feature_names=list(X_features.columns)
    )

    return {
        "engine": engine,
        "X_features": X_features,
        "df_raw": df_raw,
        "cost_model": cost_model,
        "delay_model": delay_model
    }


def test_treeshap_additivity_axiom(trained_sample_setup):
    """
    Validates Shapley Additivity / Efficiency Axiom:
    For any pair of samples x_a, x_b: sum(phi_i(x_a)) - sum(phi_i(x_b)) == margin(x_a) - margin(x_b).
    """
    engine = trained_sample_setup["engine"]
    X = trained_sample_setup["X_features"].iloc[:10]

    shap_dict = engine.compute_shap_values(X)
    cost_shap = shap_dict["cost_shap"]

    margin_preds = engine.cost_model.predict(X, output_margin=True)
    shap_sums = np.sum(cost_shap, axis=1)

    base_shap_sum = shap_sums[0]
    base_margin = margin_preds[0]

    for i in range(1, len(X)):
        shap_delta = shap_sums[i] - base_shap_sum
        margin_delta = margin_preds[i] - base_margin
        np.testing.assert_almost_equal(
            shap_delta,
            margin_delta,
            decimal=4,
            err_msg=f"Shapley delta additivity violated at sample {i}"
        )


def test_treeshap_instance_explanation(trained_sample_setup):
    """Validates explain_instance payload structure and directional sorting."""
    engine = trained_sample_setup["engine"]
    X = trained_sample_setup["X_features"]
    df = trained_sample_setup["df_raw"]

    first_instance = X.iloc[[0]]
    meta = {
        "project_id": df["project_id"].iloc[0],
        "snapshot_month": int(df["snapshot_month"].iloc[0])
    }

    explanation = engine.explain_instance(first_instance, meta)

    assert explanation["project_id"] == meta["project_id"]
    assert explanation["snapshot_month"] == meta["snapshot_month"]
    assert "top_3_positive_contributors" in explanation
    assert "top_2_mitigating_factors" in explanation
    assert "waterfall_steps" in explanation
    assert len(explanation["waterfall_steps"]) > 1

    # Verify positive contributors have positive impact
    for item in explanation["top_3_positive_contributors"]:
        assert item["shap_impact"] > 0
        assert item["direction"] == "increases_risk"

    # Verify mitigating factors have negative impact
    for item in explanation["top_2_mitigating_factors"]:
        assert item["shap_impact"] < 0
        assert item["direction"] == "decreases_risk"


def test_treeshap_plot_generation(trained_sample_setup, tmp_path):
    """Validates generation of publication-grade Waterfall and Summary charts."""
    engine = trained_sample_setup["engine"]
    X = trained_sample_setup["X_features"]

    waterfall_file = os.path.join(tmp_path, "waterfall_test.png")
    summary_file = os.path.join(tmp_path, "summary_test.png")

    engine.generate_waterfall_plot(X.iloc[[0]], project_id="PROJ-TEST", save_path=waterfall_file)
    engine.generate_summary_plot(X, save_path=summary_file)

    assert os.path.exists(waterfall_file)
    assert os.path.getsize(waterfall_file) > 1000
    assert os.path.exists(summary_file)
    assert os.path.getsize(summary_file) > 1000


if __name__ == "__main__":
    pytest.main(["-v", __file__])
