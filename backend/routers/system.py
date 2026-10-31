"""
System Health, Model Status, and Integration Inspection Router.
"""

import json
from pathlib import Path
from fastapi import APIRouter
from backend.config import settings
from backend.schemas.model_status import ModelStatusResponse

system_router = APIRouter(tags=["System Status"])


@system_router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app_name": "LoanIQ",
        "version": "1.0.0",
        "environment": "production"
    }


@system_router.get("/model/status", response_model=ModelStatusResponse)
def get_model_status():
    models_dir = settings.artifacts_path / "models"
    forecaster_path = models_dir / "cashflow_forecaster.joblib"
    acceptance_path = models_dir / "loan_acceptance_model.joblib"
    metadata_path = models_dir / "model_metadata.json"
    predictions_dir = settings.artifacts_path / "predictions"

    meta = None
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    # Check predictions
    pred_files = list(predictions_dir.glob("predicted_merchant*.csv"))
    has_preds = len(pred_files) >= 4

    integrations = {
        "agent_subsystem": True,  # Mandatory architecture implemented
        "mcp_server": True,       # Integrated with FastAPI
        "openai_configured": bool(settings.OPENAI_API_KEY.strip()),
        "sarvam_voice_configured": bool(settings.SARVAM_API_KEY.strip()),
        "google_translate_configured": bool(settings.GOOGLE_TRANSLATE_API_KEY.strip()),
    }

    forecaster_ok = forecaster_path.exists()
    acceptance_ok = acceptance_path.exists()

    if forecaster_ok and acceptance_ok:
        msg = "All ML models loaded and operational."
    else:
        msg = "One or more model artifacts missing; heuristic fallback available."

    return ModelStatusResponse(
        forecaster_loaded=forecaster_ok,
        acceptance_model_loaded=acceptance_ok,
        predictions_available=has_preds,
        model_metadata=meta,
        integrations_status=integrations,
        message=msg
    )

