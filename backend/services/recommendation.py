"""
Loan Recommendation, Rule-Based Eligibility, and Product Comparison Service.
Enforces strict separation:
- Product-rule eligibility is NOT bypassed by high acceptance probability.
- Ranking balances acceptance probability, interest rate, fees, and cashflow affordability.
"""

from typing import List, Optional, Dict, Any
from backend.schemas.loan import (
    LoanProduct,
    EligibilityResult,
    LoanRecommendationItem,
    LoanComparisonSummary
)
from backend.services.merchant_service import (
    get_merchant_profile,
    get_loan_products,
    get_loan_product_by_id
)
from backend.services.emi_calculator import calculate_loan_cost
from backend.services.acceptance_model import predict_loan_acceptance_probability
from backend.services.forecasting import get_merchant_forecast


def check_product_eligibility(
    merchant_id: str,
    loan_id: str,
    requested_amount: float,
    tenure_days: int
) -> EligibilityResult:
    profile = get_merchant_profile(merchant_id)
    product = get_loan_product_by_id(loan_id)

    if not profile:
        return EligibilityResult(loan_id=loan_id, is_eligible=False, failed_reasons=["Merchant profile not found."], passed_checks=[])
    if not product:
        return EligibilityResult(loan_id=loan_id, is_eligible=False, failed_reasons=["Loan product not found."], passed_checks=[])

    failed = []
    passed = []

    # 1. Loan Amount Bounds
    if requested_amount < product.min_amount:
        failed.append(f"Requested amount ₹{requested_amount:,.0f} is below minimum allowed ₹{product.min_amount:,.0f}.")
    elif requested_amount > product.max_amount:
        failed.append(f"Requested amount ₹{requested_amount:,.0f} exceeds maximum allowed ₹{product.max_amount:,.0f}.")
    else:
        passed.append(f"Amount ₹{requested_amount:,.0f} within allowed limits (₹{product.min_amount:,.0f} - ₹{product.max_amount:,.0f}).")

    # 2. Tenure Bounds
    if tenure_days < product.min_tenure_days:
        failed.append(f"Tenure {tenure_days} days is below minimum {product.min_tenure_days} days.")
    elif tenure_days > product.max_tenure_days:
        failed.append(f"Tenure {tenure_days} days exceeds maximum {product.max_tenure_days} days.")
    else:
        passed.append(f"Tenure {tenure_days} days within allowed range ({product.min_tenure_days} - {product.max_tenure_days} days).")

    # 3. Monthly Sales
    if profile.monthly_sales_reference < product.min_monthly_sales:
        failed.append(f"Merchant monthly sales ₹{profile.monthly_sales_reference:,.0f} is below required ₹{product.min_monthly_sales:,.0f}.")
    else:
        passed.append(f"Monthly sales ₹{profile.monthly_sales_reference:,.0f} meets required ₹{product.min_monthly_sales:,.0f}.")

    # 4. Business Age
    if profile.business_age_months < product.min_business_age_months:
        failed.append(f"Business age {profile.business_age_months} months is below required {product.min_business_age_months} months.")
    else:
        passed.append(f"Business age {profile.business_age_months} months meets required {product.min_business_age_months} months.")

    # 5. Credit Score
    if profile.credit_score < product.min_credit_score:
        failed.append(f"Credit score {profile.credit_score} is below required {product.min_credit_score}.")
    else:
        passed.append(f"Credit score {profile.credit_score} meets required {product.min_credit_score}.")

    return EligibilityResult(
        loan_id=loan_id,
        is_eligible=len(failed) == 0,
        failed_reasons=failed,
        passed_checks=passed
    )


def recommend_loans(
    merchant_id: str,
    requested_amount: Optional[float] = 100000.0,
    max_daily_emi: Optional[float] = None,
    tenure_days: Optional[int] = 365
) -> List[LoanRecommendationItem]:
    profile = get_merchant_profile(merchant_id)
    if not profile:
        return []

    if requested_amount is None or requested_amount <= 0:
        requested_amount = 100000.0
    if tenure_days is None or tenure_days <= 0:
        tenure_days = 365

    # Get merchant cash flow forecast to evaluate affordability
    forecast = get_merchant_forecast(merchant_id, horizon_days=30)
    avg_daily_net = forecast.avg_daily_net_cashflow
    existing_emi = profile.existing_daily_emi

    products = get_loan_products()
    items: List[LoanRecommendationItem] = []

    for p in products:
        # Check explicit rules
        eligibility = check_product_eligibility(merchant_id, p.loan_id, requested_amount, tenure_days)

        # Calculate cost
        cost = calculate_loan_cost(
            principal=requested_amount,
            annual_interest_rate=p.annual_interest_rate,
            tenure_days=tenure_days,
            processing_fee_pct=p.processing_fee_pct,
            prepayment_fee_pct=p.prepayment_fee_pct
        )
        daily_emi = cost["daily_emi"]

        # Predict acceptance probability
        proba, proba_str, is_fallback = predict_loan_acceptance_probability(
            merchant_id=merchant_id,
            loan_id=p.loan_id,
            requested_amount=requested_amount,
            tenure_days=tenure_days
        )

        # Affordability assessment
        free_cash = avg_daily_net - (existing_emi + daily_emi)
        affordability = "Comfortable"
        if max_daily_emi and daily_emi > max_daily_emi:
            affordability = "Exceeds Requested EMI Limit"
            eligibility.is_eligible = False
            eligibility.failed_reasons.append(
                f"Calculated daily EMI ₹{daily_emi:.2f} exceeds requested affordability limit of ₹{max_daily_emi:.2f}/day."
            )
        elif free_cash < -50.0:
            affordability = "High Risk (Negative Cash Margin)"
        elif free_cash < 50.0:
            affordability = "Moderate Pressure"

        # Multi-factor ranking score
        if eligibility.is_eligible:
            score = (
                (proba * 40.0) +
                ((25.0 - p.annual_interest_rate) * 2.0) +
                ((2.0 - p.processing_fee_pct) * 5.0) +
                (20.0 if affordability == "Comfortable" else (10.0 if "Moderate" in affordability else 0.0))
            )
            reasons = []
            if p.annual_interest_rate <= 15.0:
                reasons.append("Competitive low interest rate")
            if proba >= 0.55:
                reasons.append("High historical acceptance likelihood")
            if p.processing_fee_pct <= 1.0:
                reasons.append("Minimal 1% processing fee")
            if p.prepayment_fee_pct == 0.0:
                reasons.append("Zero prepayment penalty")
            if affordability == "Comfortable":
                reasons.append("Well within merchant daily cashflow")
            rec_reason = "; ".join(reasons) if reasons else "Eligible product matching requested tenure and borrowing profile."
        else:
            score = -100.0 - len(eligibility.failed_reasons)
            rec_reason = f"Ineligible: {eligibility.failed_reasons[0]}"

        items.append(LoanRecommendationItem(
            loan_id=p.loan_id,
            product_name=p.product_name,
            lender_name=p.lender_name,
            annual_interest_rate=p.annual_interest_rate,
            min_amount=p.min_amount,
            max_amount=p.max_amount,
            min_tenure_days=p.min_tenure_days,
            max_tenure_days=p.max_tenure_days,
            processing_fee_pct=p.processing_fee_pct,
            prepayment_fee_pct=p.prepayment_fee_pct,
            estimated_daily_emi=daily_emi,
            estimated_total_interest=cost["total_interest"],
            estimated_processing_fee=cost["processing_fee"],
            estimated_total_cost=cost["total_cost"],
            is_eligible=eligibility.is_eligible,
            failed_reasons=eligibility.failed_reasons,
            estimated_acceptance_probability=proba,
            probability_percentage=proba_str,
            affordability_status=affordability,
            rank_score=round(score, 2),
            recommendation_reason=rec_reason,
            disclaimer=p.disclaimer
        ))

    # Sort descending by rank score
    items.sort(key=lambda x: x.rank_score, reverse=True)

    # Enrich products with LLM-evaluated Affordability Status and Recommendation Fit
    enrich_recommendations_with_llm(merchant_id, profile, forecast, items, requested_amount, tenure_days)

    return items


def enrich_recommendations_with_llm(
    merchant_id: str,
    profile: Any,
    forecast: Any,
    items: List[LoanRecommendationItem],
    requested_amount: float,
    tenure_days: int
) -> None:
    """
    Enriches candidate loan items with LLM-evaluated Affordability Status and Recommendation Fit.
    Uses GPT-5.6 Luna with persistent caching. Gracefully falls back to deterministic strings on failure.
    """
    from backend.services.openai_adapter import OpenAIResponsesAdapter
    from backend.services.cache_service import get_cached_ai_response, set_cached_ai_response

    if not OpenAIResponsesAdapter.is_configured():
        return

    # Evaluate the top candidates
    target_items = items[:6]
    if not target_items:
        return

    product_ids_key = "-".join(sorted(it.loan_id for it in target_items))
    cache_msg_key = f"eval_{int(requested_amount)}_{int(tenure_days)}_{product_ids_key}"
    data_version = f"cs_{profile.credit_score}_sales_{int(profile.monthly_sales_reference)}"

    cached_eval = get_cached_ai_response(
        merchant_id=merchant_id,
        intent="LOAN_LLM_EVALUATION",
        message=cache_msg_key,
        data_version=data_version
    )
    if cached_eval and isinstance(cached_eval, dict):
        evaluations = cached_eval.get("evaluations", {})
        for it in target_items:
            if it.loan_id in evaluations:
                ev = evaluations[it.loan_id]
                if ev.get("affordability_status"):
                    it.affordability_status = ev["affordability_status"]
                if ev.get("recommendation_fit"):
                    it.recommendation_reason = ev["recommendation_fit"]
        return

    merchant_summary = {
        "merchant_id": merchant_id,
        "business_name": profile.business_name,
        "business_type": profile.merchant_type,
        "city": profile.city,
        "monthly_sales_ref": profile.monthly_sales_reference,
        "credit_score": profile.credit_score,
        "existing_daily_emi": profile.existing_daily_emi,
        "projected_avg_daily_net_cashflow": forecast.avg_daily_net_cashflow
    }

    candidate_loans = []
    for it in target_items:
        net_margin = round(forecast.avg_daily_net_cashflow - (profile.existing_daily_emi + it.estimated_daily_emi), 2)
        candidate_loans.append({
            "loan_id": it.loan_id,
            "product_name": it.product_name,
            "lender_name": it.lender_name,
            "annual_interest_rate": it.annual_interest_rate,
            "daily_emi": it.estimated_daily_emi,
            "processing_fee_pct": it.processing_fee_pct,
            "prepayment_fee_pct": it.prepayment_fee_pct,
            "acceptance_prob": it.probability_percentage,
            "net_daily_margin_after_new_emi": net_margin,
            "is_eligible": it.is_eligible,
            "failed_reasons": it.failed_reasons
        })

    try:
        evaluations = OpenAIResponsesAdapter.evaluate_loans_with_luna(merchant_summary, candidate_loans)
        if evaluations and isinstance(evaluations, dict):
            for it in target_items:
                if it.loan_id in evaluations:
                    ev = evaluations[it.loan_id]
                    if ev.get("affordability_status"):
                        it.affordability_status = ev["affordability_status"]
                    if ev.get("recommendation_fit"):
                        it.recommendation_reason = ev["recommendation_fit"]

            set_cached_ai_response(
                merchant_id=merchant_id,
                intent="LOAN_LLM_EVALUATION",
                message=cache_msg_key,
                response_payload={"evaluations": evaluations},
                data_version=data_version
            )
    except Exception as e:
        print(f"Error enriching loan recommendations with LLM: {e}")


def compare_loans(
    merchant_id: str,
    loan_ids: List[str],
    requested_amount: Optional[float] = 100000.0,
    tenure_days: Optional[int] = 365
) -> LoanComparisonSummary:
    all_recs = recommend_loans(merchant_id, requested_amount=requested_amount, tenure_days=tenure_days)
    selected = [r for r in all_recs if r.loan_id in loan_ids]
    if not selected:
        selected = all_recs[:4]  # default to top 4 if none selected

    # Ensure all selected comparison products are evaluated by the LLM
    profile = get_merchant_profile(merchant_id)
    forecast = get_merchant_forecast(merchant_id, horizon_days=30)
    if profile and forecast:
        enrich_recommendations_with_llm(merchant_id, profile, forecast, selected, requested_amount or 100000.0, tenure_days or 365)

    eligible_selected = [s for s in selected if s.is_eligible]

    lowest_interest_id = min(selected, key=lambda x: x.annual_interest_rate).loan_id if selected else None
    highest_prob_id = max(eligible_selected, key=lambda x: x.estimated_acceptance_probability).loan_id if eligible_selected else None
    best_overall_id = selected[0].loan_id if selected else None

    notes = [
        f"Compared {len(selected)} loan products for requested amount ₹{requested_amount:,.0f} and {tenure_days} days tenure.",
        f"Daily EMI computed via reducing balance convention (annual_rate / 365 daily compounding).",
        f"Best overall fit is {best_overall_id} based on combined acceptance probability, cost and cashflow buffer."
    ]

    return LoanComparisonSummary(
        products=selected,
        lowest_interest_loan_id=lowest_interest_id,
        highest_probability_loan_id=highest_prob_id,
        best_overall_loan_id=best_overall_id,
        notes=notes
    )

