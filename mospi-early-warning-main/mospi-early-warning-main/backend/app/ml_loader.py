"""
ML Model Loader & Registry for FastAPI.
Loads pre-trained joblib models at server startup for zero-latency inference.
"""

import os
import sys
import logging
import joblib
from typing import Dict, Any, Optional

logger = logging.getLogger("mospi_backend.ml_loader")

# Ensure backend directory is on sys.path so src imports succeed
PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)


def resolve_model_dir(raw: Optional[str]) -> str:
    """Anchor a relative MODEL_DIR to the backend directory.

    The shipped `.env` sets `MODEL_DIR=./models`, which SQLAlchemy's own
    path handling never touches, so it is resolved against the process working
    directory. Launching pytest or uvicorn from the repo root therefore writes a
    second, empty-of-everything-else copy of the model directory at the root
    while the trained artifacts stay in backend/models -- so the server then
    loads nothing and every prediction silently degrades. Same reasoning, and
    the same fix, as `_resolve_sqlite_path` in database.py.

    An unset or empty value uses backend/models, and an absolute value is
    returned unchanged.
    """
    if not raw or not raw.strip():
        return os.path.join(PARENT_DIR, "models")
    return raw if os.path.isabs(raw) else os.path.abspath(os.path.join(PARENT_DIR, raw))


MODEL_DIR = resolve_model_dir(os.getenv("MODEL_DIR"))

class ModelRegistry:
    """Global registry holding loaded ML models in memory."""
    
    def __init__(self):
        self.cost_reg_xgb = None
        self.cost_cls_xgb = None
        self.delay_reg_xgb = None
        self.delay_cls_xgb = None
        self.cost_cls_mlp = None
        self.delay_cls_mlp = None
        self.calibrator = None
        self.feature_extractor = None
        # Optional real-data artifacts (LightGBM / CatBoost, PDF-sourced models)
        self.cost_reg_lgbm = None
        self.cost_cls_lgbm = None
        self.delay_reg_lgbm = None
        self.delay_cls_lgbm = None
        self.cost_reg_catboost = None
        self.cost_cls_catboost = None
        self.delay_reg_catboost = None
        self.delay_cls_catboost = None
        self.extra_models_loaded = False
        self.is_loaded = False

    def load_models(self, model_dir: str = MODEL_DIR) -> bool:
        """Loads joblib model files from disk."""
        os.makedirs(model_dir, exist_ok=True)
        
        required_files = {
            "cost_reg_xgb": os.path.join(model_dir, "cost_reg_xgb.joblib"),
            "cost_cls_xgb": os.path.join(model_dir, "cost_cls_xgb.joblib"),
            "delay_reg_xgb": os.path.join(model_dir, "delay_reg_xgb.joblib"),
            "delay_cls_xgb": os.path.join(model_dir, "delay_cls_xgb.joblib"),
            "calibrator": os.path.join(model_dir, "calibrator.joblib"),
            "feature_extractor": os.path.join(model_dir, "feature_extractor.joblib"),
            "cost_cls_mlp": os.path.join(model_dir, "cost_cls_mlp.joblib"),
            "delay_cls_mlp": os.path.join(model_dir, "delay_cls_mlp.joblib"),
        }
        
        missing = [name for name, path in required_files.items() if not os.path.exists(path)]
        
        if missing:
            logger.warning(
                f"Model files missing in '{model_dir}': {missing}. "
                "Run POST /admin/seed-database to train and save models."
            )
            self.is_loaded = False
            return False

        try:
            self.cost_reg_xgb = joblib.load(required_files["cost_reg_xgb"])
            self.cost_cls_xgb = joblib.load(required_files["cost_cls_xgb"])
            self.delay_reg_xgb = joblib.load(required_files["delay_reg_xgb"])
            self.delay_cls_xgb = joblib.load(required_files["delay_cls_xgb"])
            self.calibrator = joblib.load(required_files["calibrator"])
            self.feature_extractor = joblib.load(required_files["feature_extractor"])
            self.cost_cls_mlp = joblib.load(required_files["cost_cls_mlp"])
            self.delay_cls_mlp = joblib.load(required_files["delay_cls_mlp"])
            self.is_loaded = True
            logger.info("Successfully loaded all ML model artifacts into memory.")
        except Exception as e:
            logger.error(f"Error loading model artifacts: {e}")
            self.is_loaded = False

        self._load_extra_models(model_dir)
        return self.is_loaded

    def _load_extra_models(self, model_dir: str):
        """Loads optional LightGBM / CatBoost artifacts (from real-data training)
        without failing startup when they are absent."""
        extra = {
            "cost_reg_lgbm": "cost_reg_lgbm.joblib",
            "cost_cls_lgbm": "cost_cls_lgbm.joblib",
            "delay_reg_lgbm": "delay_reg_lgbm.joblib",
            "delay_cls_lgbm": "delay_cls_lgbm.joblib",
            "cost_reg_catboost": "cost_reg_catboost.joblib",
            "cost_cls_catboost": "cost_cls_catboost.joblib",
            "delay_reg_catboost": "delay_reg_catboost.joblib",
            "delay_cls_catboost": "delay_cls_catboost.joblib",
        }
        present = 0
        for attr, fname in extra.items():
            path = os.path.join(model_dir, fname)
            if not os.path.exists(path):
                continue
            try:
                setattr(self, attr, joblib.load(path))
                present += 1
            except Exception as e:
                logger.warning(f"Failed to load optional artifact {fname}: {e}")
        self.extra_models_loaded = present > 0
        if present:
            logger.info(f"Loaded {present} optional real-data model artifact(s) (LightGBM/CatBoost).")

    def save_models(self, models_dict: Dict[str, Any], model_dir: str = MODEL_DIR):
        """Saves trained model objects to disk as joblib files."""
        os.makedirs(model_dir, exist_ok=True)
        for name, obj in models_dict.items():
            path = os.path.join(model_dir, f"{name}.joblib")
            joblib.dump(obj, path)
            logger.info(f"Saved model artifact: {path}")
            
        # Re-load updated models into memory
        self.load_models(model_dir)

# Global Singleton Registry Instance
ml_registry = ModelRegistry()
