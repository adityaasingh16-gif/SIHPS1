"""Lightweight, real Isolation Forest anomaly detector for request telemetry."""
import os
import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_COUNT = 5

class RequestAnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(
            n_estimators=int(os.getenv("IDS_IFOREST_ESTIMATORS", "120")),
            contamination=float(os.getenv("IDS_IFOREST_CONTAMINATION", "0.05")),
            random_state=42,
        )
        self.fitted = False
        self.threshold = float(os.getenv("IDS_ANOMALY_THRESHOLD", "85"))

    def fit_baseline(self, traffic=None):
        if traffic is None:
            rng = np.random.default_rng(42)
            traffic = np.column_stack([
                rng.normal(24, 8, 500).clip(1, 120),
                rng.normal(6, 2, 500).clip(1, 30),
                rng.normal(450, 180, 500).clip(0, 1800),
                rng.normal(0.03, 0.02, 500).clip(0, 0.25),
                rng.binomial(1, 0.08, 500),
            ])
        x = np.asarray(traffic, dtype=float).reshape(-1, FEATURE_COUNT)
        self.model.fit(x)
        self.fitted = True
        return self

    def score_request(self, feature_vector):
        if not self.fitted:
            self.fit_baseline()
        x = np.asarray(feature_vector, dtype=float).reshape(1, FEATURE_COUNT)
        # IsolationForest decision_function: higher is more normal. Convert to 0..100 anomaly score.
        raw = float(self.model.decision_function(x)[0])
        score = max(0.0, min(100.0, 50.0 - raw * 100.0))
        return score

anomaly_detector = RequestAnomalyDetector()
