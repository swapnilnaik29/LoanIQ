from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class LoanProduct(BaseModel):
    loan_id: str
    lender_id: str
    lender_name: str
    product_name: str
    min_amount: float
    max_amount: float
    annual_interest_rate: float
    min_tenure_days: int
    max_tenure_days: int
    processing_fee_pct: float
    prepayment_fee_pct: float
    min_monthly_sales: float
    min_business_age_months: int
    min_credit_score: int
    disclaimer: str


class EligibilityCheckRequest(BaseModel):
    merchant_id: str
    loan_id: str
    requested_amount: float
    tenure_days: int


class EligibilityResult(BaseModel):
    loan_id: str
    is_eligible: bool
    failed_reasons: List[str]
    passed_checks: List[str]


class AcceptanceProbabilityRequest(BaseModel):
    merchant_id: str
    loan_id: str
    requested_amount: float
    tenure_days: int


class AcceptanceProbabilityResult(BaseModel):
    loan_id: str
    estimated_probability: float
    probability_percentage: str
    disclaimer: str = "Estimated historical acceptance probability based on synthetic demo data; does NOT constitute loan approval."


class RecommendationRequest(BaseModel):
    merchant_id: str
    requested_amount: Optional[float] = 100000.0
    max_daily_emi: Optional[float] = None
    tenure_days: Optional[int] = 365


class LoanRecommendationItem(BaseModel):
    loan_id: str
    product_name: str
    lender_name: str
    annual_interest_rate: float
    min_amount: float
    max_amount: float
    min_tenure_days: int
    max_tenure_days: int
    processing_fee_pct: float
    prepayment_fee_pct: float
    estimated_daily_emi: float
    estimated_total_interest: float
    estimated_processing_fee: float
    estimated_total_cost: float
    is_eligible: bool
    failed_reasons: List[str]
    estimated_acceptance_probability: float
    probability_percentage: str
    affordability_status: str
    rank_score: float
    recommendation_reason: str
    disclaimer: str


class LoanComparisonRequest(BaseModel):
    merchant_id: str
    loan_ids: List[str]
    requested_amount: Optional[float] = 100000.0
    tenure_days: Optional[int] = 365


class LoanComparisonSummary(BaseModel):
    products: List[LoanRecommendationItem]
    lowest_interest_loan_id: Optional[str] = None
    highest_probability_loan_id: Optional[str] = None
    best_overall_loan_id: Optional[str] = None
    notes: List[str]


class LoanSimulationRequest(BaseModel):
    merchant_id: str
    loan_amount: float
    tenure_days: int
    annual_interest_rate: float
    processing_fee_pct: float = 1.0
    prepayment_fee_pct: float = 0.0
    safety_buffer: Optional[float] = 5000.0


class LoanSimulationResult(BaseModel):
    merchant_id: str
    loan_amount: float
    tenure_days: int
    annual_interest_rate: float
    daily_emi: float
    total_interest: float
    processing_fee: float
    total_cost: float
    total_repayment: float
    pre_loan_closing_balance: float
    post_loan_projected_min_balance: float
    has_negative_balance_risk: bool
    negative_balance_dates: List[str]
    safety_buffer_breaches: List[str]
    is_affordable: bool
    affordability_notes: str
    suggested_alternatives: List[Dict[str, Any]]
    disclaimer: str = "Simulated projection for decision support only. Assumes constant business conditions."


class OptimizationSummary(BaseModel):
    merchant_id: str
    active_loans_count: int
    total_remaining_principal: float
    total_current_daily_emi: float
    completed_loans_count: int
    total_repaid_principal: float
    forecast_avg_daily_net_cashflow: float
    cash_available_after_emi: float
    refinance_or_consolidation_recommendation: str
    warnings: List[str]
    active_loans: List[Any]

