"""ML inference engine (XGBoost depth-correction + confidence)."""
from typing import List, Optional

import numpy as np

from ...models import RainfallCell
from ...logging_conf import log
from ...config import settings


class InferenceEngine:
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self._features_order = [
            "rainfall_mm_hr", "cumulative_rain_mm", "elevation_m", "slope",
            "imperviousness", "distance_to_drain_m", "drain_capacity",
            "drain_utilization", "blockage_percent", "previous_water_depth_cm",
            "surface_runoff_m3",
        ]
        self._load_model()

    def _load_model(self):
        try:
            import xgboost as xgb
            import joblib
            import os
            path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "xgb_flood_correction.joblib")
            path = os.path.abspath(path)
            if os.path.exists(path):
                self.model = joblib.load(path)
                self.model_loaded = True
                log.info("Loaded XGBoost flood correction model")
            else:
                self.model = xgb.XGBRegressor(n_estimators=50, max_depth=4, random_state=42)
                self.model_loaded = False
                log.info("No pre-trained model found; using default XGBoost (fit synthetic data)")
                self._fit_synthetic()
        except ImportError:
            log.warning("XGBoost not installed; ML correction unavailable")
            self.model_loaded = False

    def _fit_synthetic(self):
        if self.model is None:
            return
        rng = np.random.RandomState(42)
        n = 2000
        X = rng.uniform(0, 1, (n, len(self._features_order)))
        X[:, 0] = rng.uniform(0, 100, n)
        X[:, 1] = rng.uniform(0, 200, n)
        X[:, 2] = rng.uniform(0, 15, n)
        X[:, 3] = rng.uniform(0, 0.05, n)
        X[:, 4] = rng.uniform(0.1, 0.95, n)
        X[:, 9] = rng.uniform(0, 50, n)
        X[:, 10] = rng.uniform(0, 500, n)
        y = 2.0 * X[:, 0] / 100 - 1.0 * X[:, 2] / 15 - 0.5 * X[:, 4] + rng.normal(0, 2.5, n)
        y = np.clip(y, -10, 30)
        self.model.fit(X, y)
        self.model_loaded = True

    def features_for_road(self, road: dict, cell: dict, drainage, previous_depth: float,
                          edge_info=None, storage=None) -> List[float]:
        edge_id, dist_deg = edge_info if edge_info else (None, 999.0)
        drain_cap = 0.0
        drain_util = 0.0
        blockage = 0.0
        if edge_id is not None and hasattr(drainage, "graph") and edge_id in drainage.graph.edges:
            e = drainage.graph.edges[edge_id]
            drain_cap = e.get("capacity_m3s", 0)
            blockage = e.get("blockage_percent", 0)
        dist_m = dist_deg * 111000.0
        return [
            0.0, 0.0, cell.get("elevation_m", 0), cell.get("slope", 0),
            cell.get("imperviousness", 0.5), dist_m, drain_cap,
            drain_util, blockage, previous_depth, 0.0,
        ]

    def predict_correction(self, features: List[float]) -> float:
        if not self.model_loaded or self.model is None:
            return 0.0
        X = np.array([features], dtype=float)
        if X.shape[1] != len(self._features_order):
            return 0.0
        try:
            pred = self.model.predict(X)[0]
            return float(pred)
        except Exception as e:
            log.debug(f"ML prediction error: {e}")
            return 0.0

    def predict_batch(self, feature_rows: List[List[float]]) -> List[float]:
        if not self.model_loaded or self.model is None or not feature_rows:
            return [0.0] * len(feature_rows)
        try:
            X = np.array(feature_rows, dtype=float)
            if X.shape[1] != len(self._features_order):
                return [0.0] * len(feature_rows)
            preds = self.model.predict(X)
            return [float(v) for v in preds]
        except Exception as e:
            log.debug(f"ML batch prediction error: {e}")
            return [0.0] * len(feature_rows)

    def confidence_for(self, road, cell, nowcast, storage) -> "Confidence":
        from ...simulation.risk.classifier import Severity
        from ...models import Confidence
        score = 2
        if nowcast.rainfall_mm_hr.get(0, 0) > 20:
            score -= 1
        if nowcast.confidence == "MEDIUM":
            score -= 0.5
        if abs(cell.get("elevation_m", 5)) < 2:
            score -= 0.5
        if score > 1.5:
            return Confidence.HIGH
        if score > 0.5:
            return Confidence.MEDIUM
        return Confidence.LOW