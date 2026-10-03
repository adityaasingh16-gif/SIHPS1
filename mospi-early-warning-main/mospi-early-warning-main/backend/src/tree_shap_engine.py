"""
TreeSHAP Explainability Engine for MoSPI Dhrishti Early Warning Platform.

Provides exact polynomial-time Shapley Value calculations for tree ensemble models (XGBoost),
multi-objective risk attribution (Cost Escalation + Schedule Delay), and dashboard-ready payloads.
"""

import numpy as np
import pandas as pd
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional, Tuple


class TreeSHAPEngine:
    """
    Dedicated TreeSHAP Engine providing exact additive feature attributions for
    XGBoost Cost and Delay models in polynomial time O(TLD^2).
    """

    def __init__(
        self,
        cost_model: Any,
        delay_model: Any,
        feature_names: List[str],
        cost_weight: float = 0.5,
        delay_weight: float = 0.5
    ):
        """
        Initializes TreeExplainers for Cost and Delay models.

        Args:
            cost_model: Trained tree-based model for Cost Overrun risk.
            delay_model: Trained tree-based model for Missed Deadline / Schedule Delay risk.
            feature_names: List of feature names in exact column order used during training.
            cost_weight: Weight assigned to cost risk attribution (default: 0.5).
            delay_weight: Weight assigned to delay risk attribution (default: 0.5).
        """
        self.cost_model = cost_model
        self.delay_model = delay_model
        self.feature_names = list(feature_names)
        self.cost_weight = cost_weight
        self.delay_weight = delay_weight

        # Initialize SHAP TreeExplainers
        self.cost_explainer = shap.TreeExplainer(self.cost_model)
        self.delay_explainer = shap.TreeExplainer(self.delay_model)

        # Baseline expected values (E[f(x)])
        def _get_scalar_ev(explainer):
            ev = explainer.expected_value
            if isinstance(ev, (list, np.ndarray)):
                arr = np.asarray(ev)
                if arr.ndim > 0:
                    return float(arr[1] if len(arr) > 1 else arr[0])
            return float(ev)

        self.cost_expected_value = _get_scalar_ev(self.cost_explainer)
        self.delay_expected_value = _get_scalar_ev(self.delay_explainer)
        self.composite_expected_value = (
            self.cost_weight * self.cost_expected_value + self.delay_weight * self.delay_expected_value
        )

    def _extract_shap_matrix(self, explainer: shap.TreeExplainer, X: pd.DataFrame) -> np.ndarray:
        """Helper to extract correct SHAP matrix regardless of binary/regression output format."""
        raw_values = explainer.shap_values(X)
        if isinstance(raw_values, list):
            # Binary classification list format [class_0, class_1] -> take class_1
            return np.array(raw_values[1] if len(raw_values) > 1 else raw_values[0])
        elif isinstance(raw_values, np.ndarray) and raw_values.ndim == 3:
            # Shape (N, features, classes)
            return raw_values[:, :, 1]
        return np.array(raw_values)

    def compute_shap_values(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Computes SHAP value matrices for Cost, Delay, and Composite Risk.

        Returns:
            Dict containing 'cost_shap', 'delay_shap', and 'composite_shap' arrays of shape (N, M).
        """
        cost_shap = self._extract_shap_matrix(self.cost_explainer, X)
        delay_shap = self._extract_shap_matrix(self.delay_explainer, X)
        composite_shap = self.cost_weight * cost_shap + self.delay_weight * delay_shap

        return {
            "cost_shap": cost_shap,
            "delay_shap": delay_shap,
            "composite_shap": composite_shap
        }

    def explain_instance(
        self,
        instance_features: pd.DataFrame,
        meta_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generates local explanation for a single project instance snapshot.

        Returns structured payload containing:
            - Composite, Cost, and Delay SHAP values
            - Top risk drivers (pushing risk UP, positive SHAP)
            - Top mitigating factors (damping risk DOWN, negative SHAP)
            - Waterfall step items for interactive dashboard rendering
        """
        if len(instance_features) != 1:
            instance_features = instance_features.iloc[[0]]

        shap_dict = self.compute_shap_values(instance_features)
        cost_vals = shap_dict["cost_shap"][0]
        delay_vals = shap_dict["delay_shap"][0]
        comp_vals = shap_dict["composite_shap"][0]

        feature_series = instance_features.iloc[0]
        contributions = []
        for name, val, c_s, d_s, comp_s in zip(
            self.feature_names,
            feature_series.values,
            cost_vals,
            delay_vals,
            comp_vals
        ):
            try:
                f_val = float(val) if pd.notnull(val) else 0.0
            except (ValueError, TypeError):
                f_val = 0.0

            contributions.append({
                "feature": name,
                "feature_value": f_val,
                "cost_shap": float(c_s),
                "delay_shap": float(d_s),
                "shap_impact": float(comp_s),
                "direction": "increases_risk" if comp_s > 0 else "decreases_risk"
            })

        positive_drivers = sorted(
            [c for c in contributions if c["shap_impact"] > 0],
            key=lambda x: x["shap_impact"],
            reverse=True
        )
        mitigating_factors = sorted(
            [c for c in contributions if c["shap_impact"] < 0],
            key=lambda x: x["shap_impact"]
        )

        # Build waterfall sequence for frontend dashboard chart
        sorted_by_abs = sorted(contributions, key=lambda x: abs(x["shap_impact"]), reverse=True)
        top_waterfall_factors = sorted_by_abs[:8]

        current_base = self.composite_expected_value
        waterfall_steps = [{
            "step": "Baseline Expected Risk",
            "feature": "base_value",
            "delta": round(current_base, 4),
            "running_total": round(current_base, 4)
        }]

        for item in top_waterfall_factors:
            current_base += item["shap_impact"]
            waterfall_steps.append({
                "step": item["feature"],
                "feature": item["feature"],
                "feature_value": item["feature_value"],
                "delta": round(item["shap_impact"], 4),
                "running_total": round(current_base, 4),
                "direction": item["direction"]
            })

        meta = meta_info or {}
        project_id = meta.get("project_id", "Unknown")
        snapshot_month = meta.get("snapshot_month", 0)

        # Build human-readable synthesis text
        summary_lines = [
            f"=== TreeSHAP Explanation for Project {project_id} (Month {snapshot_month}) ===",
            f"Expected Base Risk Logit: {self.composite_expected_value:.3f}",
            f"Final Predicted Margin: {current_base:.3f}",
            "\nTop Positive Risk Drivers (Accelerating Risk):"
        ]
        for idx, item in enumerate(positive_drivers[:3], 1):
            summary_lines.append(
                f"  {idx}. {item['feature']} = {item['feature_value']:.2f} (Impact: +{item['shap_impact']:.4f})"
            )
        summary_lines.append("\nTop Mitigating Factors (Damping Risk):")
        for idx, item in enumerate(mitigating_factors[:2], 1):
            summary_lines.append(
                f"  {idx}. {item['feature']} = {item['feature_value']:.2f} (Impact: {item['shap_impact']:.4f})"
            )

        return {
            "project_id": project_id,
            "snapshot_month": snapshot_month,
            "base_expected_value": round(self.composite_expected_value, 4),
            "cost_expected_value": round(self.cost_expected_value, 4),
            "delay_expected_value": round(self.delay_expected_value, 4),
            "top_3_positive_contributors": positive_drivers[:3],
            "top_2_mitigating_factors": mitigating_factors[:2],
            "all_contributions": contributions,
            "waterfall_steps": waterfall_steps,
            "explanation_summary": "\n".join(summary_lines)
        }

    def generate_waterfall_plot(
        self,
        instance_features: pd.DataFrame,
        project_id: str = "Project",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """Generates a publication-grade Waterfall chart for a single project instance."""
        explanation = self.explain_instance(instance_features, {"project_id": project_id})
        steps = explanation["waterfall_steps"][1:]  # skip baseline for bar steps
        
        features = [s["feature"] for s in steps]
        deltas = [s["delta"] for s in steps]
        colors = ["#e63946" if d > 0 else "#2a9d8f" for d in deltas]

        fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
        y_pos = np.arange(len(features))
        
        bars = ax.barh(y_pos, deltas, color=colors, height=0.6, edgecolor="black", alpha=0.85)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(features, fontsize=10, fontweight="bold")
        ax.axvline(0, color="gray", linestyle="--", linewidth=1.2)
        ax.set_xlabel(r"SHAP Impact on Composite Risk ($\phi_i$)", fontsize=11, fontweight="bold")
        ax.set_title(f"TreeSHAP Risk Attribution: {project_id}", fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, axis="x", alpha=0.3, linestyle=":")
        
        # Add value labels
        for bar, d in zip(bars, deltas):
            sign = "+" if d > 0 else ""
            ax.text(
                bar.get_width() + (0.01 if d >= 0 else -0.01),
                bar.get_y() + bar.get_height() / 2,
                f"{sign}{d:.3f}",
                va="center",
                ha="left" if d >= 0 else "right",
                fontsize=9,
                fontweight="bold"
            )

        ax.invert_yaxis()
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            plt.close(fig)

        return fig

    def generate_summary_plot(
        self,
        X: pd.DataFrame,
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """Generates a global feature importance bar plot across all projects."""
        shap_dict = self.compute_shap_values(X)
        mean_abs_shap = np.mean(np.abs(shap_dict["composite_shap"]), axis=0)
        
        sorted_indices = np.argsort(mean_abs_shap)[::-1][:10]
        top_features = [self.feature_names[i] for i in sorted_indices]
        top_scores = mean_abs_shap[sorted_indices]

        fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
        y_pos = np.arange(len(top_features))
        
        ax.barh(y_pos, top_scores, color="#1d3557", height=0.6, edgecolor="black", alpha=0.85)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(top_features, fontsize=10, fontweight="bold")
        ax.set_xlabel(r"Mean Absolute SHAP Value: $E[|\phi_i|]$", fontsize=11, fontweight="bold")
        ax.set_title("Global Feature Importance (TreeSHAP Risk Impact)", fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, axis="x", alpha=0.3, linestyle=":")
        ax.invert_yaxis()
        
        for idx, score in enumerate(top_scores):
            ax.text(score + 0.005, idx, f"{score:.3f}", va="center", fontsize=9, fontweight="bold")

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            plt.close(fig)

        return fig
