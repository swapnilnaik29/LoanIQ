"""
Merchant Data and Operations Router for LoanIQ.
Protects merchant isolation and provides profile, loan history, forecasts, recommendations, and optimization.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from backend.schemas.merchant import MerchantProfile, MerchantLoanAccount
from backend.schemas.forecast import MerchantForecastResponse
from backend.schemas.loan import LoanRecommendationItem, RecommendationRequest, OptimizationSummary
from backend.services.merchant_service import get_merchant_profile, get_merchant_loans, get_all_merchant_ids
from backend.services.forecasting import get_merchant_forecast, refresh_merchant_forecast
from backend.services.recommendation import recommend_loans
from backend.services.loan_optimizer import get_merchant_optimization

merchants_router = APIRouter(prefix="/merchants", tags=["Merchants"])


def _validate_merchant(merchant_id: str):
    valid_ids = get_all_merchant_ids()
    if merchant_id not in valid_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Merchant '{merchant_id}' not found. Available merchants: {', '.join(valid_ids)}"
        )


@merchants_router.get("/{merchant_id}/profile", response_model=MerchantProfile)
def get_profile(merchant_id: str):
    _validate_merchant(merchant_id)
    profile = get_merchant_profile(merchant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@merchants_router.get("/{merchant_id}/loans", response_model=List[MerchantLoanAccount])
def get_loans(merchant_id: str, status: str = Query("all")):
    _validate_merchant(merchant_id)
    return get_merchant_loans(merchant_id, status=status)


@merchants_router.get("/{merchant_id}/forecast", response_model=MerchantForecastResponse)
def get_forecast(merchant_id: str, horizon: int = Query(30)):
    _validate_merchant(merchant_id)
    return get_merchant_forecast(merchant_id, horizon_days=horizon)


@merchants_router.post("/{merchant_id}/forecast/refresh", response_model=MerchantForecastResponse)
def refresh_forecast(merchant_id: str):
    _validate_merchant(merchant_id)
    return refresh_merchant_forecast(merchant_id)


@merchants_router.get("/{merchant_id}/optimization", response_model=OptimizationSummary)
def get_optimization(merchant_id: str):
    _validate_merchant(merchant_id)
    return get_merchant_optimization(merchant_id)


@merchants_router.get("/{merchant_id}/recommendations", response_model=List[LoanRecommendationItem])
def get_recommendations(
    merchant_id: str,
    requested_amount: float = 100000.0,
    max_daily_emi: Optional[float] = None,
    tenure_days: int = 365
):
    _validate_merchant(merchant_id)
    return recommend_loans(
        merchant_id=merchant_id,
        requested_amount=requested_amount,
        max_daily_emi=max_daily_emi,
        tenure_days=tenure_days
    )


@merchants_router.post("/{merchant_id}/recommendations", response_model=List[LoanRecommendationItem])
def post_recommendations(merchant_id: str, req: RecommendationRequest):
    _validate_merchant(merchant_id)
    return recommend_loans(
        merchant_id=merchant_id,
        requested_amount=req.requested_amount or 100000.0,
        max_daily_emi=req.max_daily_emi,
        tenure_days=req.tenure_days or 365
    )
