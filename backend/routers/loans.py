"""
Loan Products, Eligibility, Comparison, and Simulator Router.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from backend.schemas.loan import (
    LoanProduct,
    EligibilityCheckRequest,
    EligibilityResult,
    AcceptanceProbabilityRequest,
    AcceptanceProbabilityResult,
    LoanComparisonRequest,
    LoanComparisonSummary,
    LoanSimulationRequest,
    LoanSimulationResult
)
from backend.services.merchant_service import get_loan_products, get_all_merchant_ids
from backend.services.recommendation import check_product_eligibility, compare_loans
from backend.services.acceptance_model import predict_loan_acceptance_probability
from backend.services.loan_optimizer import simulate_loan

loans_router = APIRouter(prefix="/loans", tags=["Loan Products & Calculations"])


@loans_router.get("/products", response_model=List[LoanProduct])
def list_products():
    return get_loan_products()


@loans_router.post("/eligibility", response_model=EligibilityResult)
def check_eligibility(req: EligibilityCheckRequest):
    valid_ids = get_all_merchant_ids()
    if req.merchant_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Merchant {req.merchant_id} not found.")
    return check_product_eligibility(
        merchant_id=req.merchant_id,
        loan_id=req.loan_id,
        requested_amount=req.requested_amount,
        tenure_days=req.tenure_days
    )


@loans_router.post("/acceptance-probability", response_model=AcceptanceProbabilityResult)
def get_acceptance_prob(req: AcceptanceProbabilityRequest):
    valid_ids = get_all_merchant_ids()
    if req.merchant_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Merchant {req.merchant_id} not found.")
    proba, proba_str, is_fb = predict_loan_acceptance_probability(
        merchant_id=req.merchant_id,
        loan_id=req.loan_id,
        requested_amount=req.requested_amount,
        tenure_days=req.tenure_days
    )
    return AcceptanceProbabilityResult(
        loan_id=req.loan_id,
        estimated_probability=proba,
        probability_percentage=proba_str
    )


@loans_router.post("/compare", response_model=LoanComparisonSummary)
def compare_products(req: LoanComparisonRequest):
    valid_ids = get_all_merchant_ids()
    if req.merchant_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Merchant {req.merchant_id} not found.")
    return compare_loans(
        merchant_id=req.merchant_id,
        loan_ids=req.loan_ids,
        requested_amount=req.requested_amount or 100000.0,
        tenure_days=req.tenure_days or 365
    )


@loans_router.post("/simulate", response_model=LoanSimulationResult)
def run_simulation(req: LoanSimulationRequest):
    valid_ids = get_all_merchant_ids()
    if req.merchant_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Merchant {req.merchant_id} not found.")
    return simulate_loan(
        merchant_id=req.merchant_id,
        loan_amount=req.loan_amount,
        tenure_days=req.tenure_days,
        annual_interest_rate=req.annual_interest_rate,
        processing_fee_pct=req.processing_fee_pct,
        prepayment_fee_pct=req.prepayment_fee_pct,
        safety_buffer=req.safety_buffer or 5000.0
    )

