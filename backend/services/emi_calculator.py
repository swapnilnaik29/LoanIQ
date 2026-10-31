"""
EMI and Loan Cost Calculation Service.
Uses reducing balance convention matching standard commercial micro-lending practice
and verified against the dataset.
Formula:
    r = annual_rate / (100 * 365)
    n = tenure_days
    daily_emi = P * (r * (1 + r)^n) / ((1 + r)^n - 1)
"""

from typing import Dict, Any


def calculate_daily_emi(principal: float, annual_interest_rate: float, tenure_days: int) -> float:
    """
    Calculate daily EMI using reducing balance formula.
    If interest rate is 0, falls back to principal / tenure_days.
    """
    if principal <= 0 or tenure_days <= 0:
        return 0.0

    if annual_interest_rate <= 0:
        return round(principal / tenure_days, 2)

    r = (annual_interest_rate / 100.0) / 365.0
    n = tenure_days
    factor = (1.0 + r) ** n
    emi = principal * (r * factor) / (factor - 1.0)
    return round(float(emi), 2)


def calculate_loan_cost(
    principal: float,
    annual_interest_rate: float,
    tenure_days: int,
    processing_fee_pct: float = 1.0,
    prepayment_fee_pct: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate full loan repayment breakdown:
    daily EMI, total repayment, total interest, processing fee, and total borrowing cost.
    """
    daily_emi = calculate_daily_emi(principal, annual_interest_rate, tenure_days)
    total_repayment = round(daily_emi * tenure_days, 2)
    total_interest = round(max(0.0, total_repayment - principal), 2)
    processing_fee = round(principal * (processing_fee_pct / 100.0), 2)
    total_cost = round(total_interest + processing_fee, 2)

    return {
        "principal": round(principal, 2),
        "annual_interest_rate": annual_interest_rate,
        "tenure_days": tenure_days,
        "daily_emi": daily_emi,
        "total_repayment": total_repayment,
        "total_interest": total_interest,
        "processing_fee_pct": processing_fee_pct,
        "processing_fee": processing_fee,
        "prepayment_fee_pct": prepayment_fee_pct,
        "total_cost": total_cost,
        "calculation_convention": "Daily reducing balance; daily rate = annual_rate / 365"
    }

