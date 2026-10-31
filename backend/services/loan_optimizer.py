"""
Rule-Based Loan Optimization and Simulation Engine.
Evaluates active loan burden, daily EMI pressure against cashflow,
simulates additional borrowing with safety buffers, and proposes actionable scenarios.
"""

from typing import Dict, Any, List
from backend.config import settings
from backend.schemas.loan import LoanSimulationResult, OptimizationSummary
from backend.services.merchant_service import (
    get_merchant_profile,
    get_merchant_loans,
    get_loan_products
)
from backend.services.emi_calculator import calculate_daily_emi, calculate_loan_cost
from backend.services.forecasting import get_merchant_forecast


def get_merchant_optimization(merchant_id: str) -> OptimizationSummary:
    profile = get_merchant_profile(merchant_id)
    if not profile:
        raise ValueError(f"Merchant {merchant_id} not found.")

    active_loans = get_merchant_loans(merchant_id, status="active")
    completed_loans = get_merchant_loans(merchant_id, status="completed")

    total_remaining_principal = round(sum(l.remaining_principal for l in active_loans), 2)
    total_current_daily_emi = round(sum(l.daily_emi for l in active_loans), 2)
    total_repaid_principal = round(sum(l.principal_repaid_to_date for l in completed_loans), 2)

    forecast = get_merchant_forecast(merchant_id, horizon_days=30)
    avg_net_cf = forecast.avg_daily_net_cashflow
    cash_after_emi = round(avg_net_cf - total_current_daily_emi, 2)

    warnings = []
    if cash_after_emi < 100.0:
        warnings.append(
            f"Tight daily liquidity: After daily EMI of ₹{total_current_daily_emi:.2f}, "
            f"average net cash buffer is only ₹{cash_after_emi:.2f}/day."
        )

    if forecast.min_projected_balance < settings.FORECAST_SAFETY_BUFFER:
        warnings.append(
            f"Projected closing cash balance drops to ₹{forecast.min_projected_balance:,.2f}, "
            f"which is below the ₹{settings.FORECAST_SAFETY_BUFFER:,.0f} safety buffer."
        )

    # Consolidation / refinancing recommendation rule
    products = get_loan_products()
    lowest_rate_product = min(products, key=lambda p: p.annual_interest_rate)

    high_rate_active = [l for l in active_loans if l.annual_interest_rate > lowest_rate_product.annual_interest_rate + 2.0]
    if high_rate_active and total_remaining_principal <= lowest_rate_product.max_amount:
        recom = (
            f"Consider debt consolidation: You have active borrowing at up to {max(l.annual_interest_rate for l in active_loans)}% APR. "
            f"Refinancing outstanding ₹{total_remaining_principal:,.2f} with {lowest_rate_product.product_name} at "
            f"{lowest_rate_product.annual_interest_rate}% APR could reduce daily interest expense."
        )
    else:
        recom = (
            f"Current debt structure is stable. Focus on completing active loan tenures "
            f"({min(l.remaining_tenure_days for l in active_loans)} days remaining on shortest active loan)."
        )

    return OptimizationSummary(
        merchant_id=merchant_id,
        active_loans_count=len(active_loans),
        total_remaining_principal=total_remaining_principal,
        total_current_daily_emi=total_current_daily_emi,
        completed_loans_count=len(completed_loans),
        total_repaid_principal=total_repaid_principal,
        forecast_avg_daily_net_cashflow=avg_net_cf,
        cash_available_after_emi=cash_after_emi,
        refinance_or_consolidation_recommendation=recom,
        warnings=warnings,
        active_loans=[l.model_dump() for l in active_loans]
    )


def simulate_loan(
    merchant_id: str,
    loan_amount: float,
    tenure_days: int,
    annual_interest_rate: float,
    processing_fee_pct: float = 1.0,
    prepayment_fee_pct: float = 0.0,
    safety_buffer: float = 5000.0
) -> LoanSimulationResult:
    profile = get_merchant_profile(merchant_id)
    if not profile:
        raise ValueError(f"Merchant {merchant_id} not found.")

    cost = calculate_loan_cost(
        principal=loan_amount,
        annual_interest_rate=annual_interest_rate,
        tenure_days=tenure_days,
        processing_fee_pct=processing_fee_pct,
        prepayment_fee_pct=prepayment_fee_pct
    )
    daily_emi = cost["daily_emi"]

    forecast = get_merchant_forecast(merchant_id, horizon_days=30)
    pre_min_bal = forecast.min_projected_balance

    # Evaluate day-by-day impact on 30-day projected cash balance
    # In reality, new loan disbursement adds loan_amount (minus processing fee) on Day 1,
    # and incurs additional daily EMI each day.
    post_balances = []
    negative_dates = []
    buffer_breach_dates = []

    # Get baseline starting balance (day 1 before change)
    first_row = forecast.rows[0]
    # Starting balance before day 1 forecast
    base_balance = first_row.predicted_closing_cash_balance - first_row.predicted_net_cashflow

    # On day 1, merchant receives net disbursement: loan_amount - processing_fee
    net_disbursed = loan_amount - cost["processing_fee"]
    curr_balance = base_balance + net_disbursed

    for r in forecast.rows:
        # Each day: net cashflow from operations MINUS the new daily EMI
        day_net = r.predicted_net_cashflow - daily_emi
        curr_balance += day_net
        post_balances.append(curr_balance)

        if curr_balance < 0:
            negative_dates.append(r.forecast_date)
        elif curr_balance < safety_buffer:
            buffer_breach_dates.append(r.forecast_date)

    post_min_bal = round(min(post_balances), 2)
    has_neg_risk = len(negative_dates) > 0
    is_affordable = not has_neg_risk and len(buffer_breach_dates) <= 3

    if is_affordable:
        affordability_notes = (
            f"Loan is affordable. Projected minimum cash balance remains healthy at ₹{post_min_bal:,.2f} "
            f"with daily EMI ₹{daily_emi:.2f}."
        )
    else:
        reasons = []
        if has_neg_risk:
            reasons.append(f"triggers negative cash balance on {len(negative_dates)} day(s)")
        if buffer_breach_dates:
            reasons.append(f"breaches ₹{safety_buffer:,.0f} safety buffer on {len(buffer_breach_dates)} day(s)")
        affordability_notes = f"Caution: Borrowing ₹{loan_amount:,.0f} {' and '.join(reasons)}. Consider adjusting tenure or amount."

    # Suggest 2 alternatives
    alt1_amount = round(loan_amount * 0.75, 0)
    alt1_cost = calculate_loan_cost(alt1_amount, annual_interest_rate, tenure_days, processing_fee_pct)
    alt2_tenure = min(540, int(tenure_days * 1.5))
    alt2_cost = calculate_loan_cost(loan_amount, annual_interest_rate, alt2_tenure, processing_fee_pct)

    alternatives = [
        {
            "scenario": "Reduced Amount (75%)",
            "loan_amount": alt1_amount,
            "tenure_days": tenure_days,
            "daily_emi": alt1_cost["daily_emi"],
            "total_interest": alt1_cost["total_interest"],
            "rationale": f"Lowers daily EMI from ₹{daily_emi:.2f} to ₹{alt1_cost['daily_emi']:.2f} to preserve working capital."
        },
        {
            "scenario": "Extended Tenure",
            "loan_amount": loan_amount,
            "tenure_days": alt2_tenure,
            "daily_emi": alt2_cost["daily_emi"],
            "total_interest": alt2_cost["total_interest"],
            "rationale": f"Extends tenure to {alt2_tenure} days, cutting daily payment to ₹{alt2_cost['daily_emi']:.2f}."
        }
    ]

    return LoanSimulationResult(
        merchant_id=merchant_id,
        loan_amount=loan_amount,
        tenure_days=tenure_days,
        annual_interest_rate=annual_interest_rate,
        daily_emi=daily_emi,
        total_interest=cost["total_interest"],
        processing_fee=cost["processing_fee"],
        total_cost=cost["total_cost"],
        total_repayment=cost["total_repayment"],
        pre_loan_closing_balance=pre_min_bal,
        post_loan_projected_min_balance=post_min_bal,
        has_negative_balance_risk=has_neg_risk,
        negative_balance_dates=negative_dates,
        safety_buffer_breaches=buffer_breach_dates,
        is_affordable=is_affordable,
        affordability_notes=affordability_notes,
        suggested_alternatives=alternatives
    )

