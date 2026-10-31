from typing import List, Optional
from pydantic import BaseModel, Field


class MerchantProfile(BaseModel):
    merchant_id: str
    business_name: str
    merchant_type: str
    city: str
    city_tier: str
    business_age_months: int
    monthly_sales_reference: float
    monthly_profit_reference: float
    credit_score: int
    opening_cash_balance: float
    preferred_language: str
    existing_loan_count: int
    existing_daily_emi: float
    completed_loan_count: int


class MerchantLoanAccount(BaseModel):
    loan_account_id: str
    merchant_id: str
    loan_id: str
    disbursement_date: str
    contractual_end_date: str
    snapshot_date: str
    principal_amount: float
    annual_interest_rate: float
    tenure_days: int
    daily_emi: float
    installments_paid_to_date: int
    amount_paid_to_date: float
    interest_paid_to_date: float
    principal_repaid_to_date: float
    remaining_principal: float
    remaining_tenure_days: int
    next_due_date: Optional[str] = None
    next_daily_emi: float
    loan_status: str


class MerchantAuthRequest(BaseModel):
    merchant_id: str = Field(..., description="Demo Merchant ID (e.g. M001, M002, M003, M004)")


class MerchantAuthResponse(BaseModel):
    authenticated: bool
    merchant_id: str
    profile: Optional[MerchantProfile] = None
    message: str

