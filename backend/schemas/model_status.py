from typing import Dict, Any, Optional
from pydantic import BaseModel


class ModelStatusResponse(BaseModel):
    forecaster_loaded: bool
    acceptance_model_loaded: bool
    predictions_available: bool
    model_metadata: Optional[Dict[str, Any]] = None
    integrations_status: Dict[str, bool]
    message: str

