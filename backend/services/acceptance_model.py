"""
Loan Acceptance Probability Inference Service.
Loads the trained CalibratedClassifierCV pipeline and computes historical acceptance estimates.
Safeguards:
- Returns probability in [0, 1].
- Distinguishes probability from approval guarantees.
- Provides fallback heuristic with clear label if artifact is absent.
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import pandas as pd
from backend.config import settings
from backend.services.merchant_service import get_merchant_profile, get_loan_product_by_id
from backend.services.emi_calculator import calculate_daily_emi

_ACCEPTANCE_MODEL_BUNDLE = None


def get_acceptance_model_bundle():
    global _ACCEPTANCE_MODEL_BUNDLE
    if _ACCEPTANCE_MODEL_BUNDLE is None:
        model_path = settings.artifacts_path / "models" / "loan_acceptance_model.joblib"
        if model_path.exists():
            _ACCEPTANCE_MODEL_BUNDLE = joblib.load(model_path)
    return _ACCEPTANCE_MODEL_BUNDLE


def predict_loan_acceptance_probability(
    merchant_id: str,
    loan_id: str,
    requested_amount: float,
    tenure_days: int
) -> Tuple[float, str, bool]:
    """
    Returns (probability: float, formatted_pct: str, is_fallback: bool).
    """
    profile = get_merchant_profile(merchant_id)
    product = get_loan_product_by_id(loan_id)
    if not profile or not product:
        return 0.0, "0.0%", False

    bundle = get_acceptance_model_bundle()
    if bundle is None:
        # Fallback heuristic: score based on credit score, debt service ratio, and business age
        score = 0.5
        if profile.credit_score >= product.min_credit_score:
            score += 0.15
        if profile.business_age_months >= product.min_business_age_months:
            score += 0.1
        if profile.monthly_sales_reference >= product.min_monthly_sales:
            score += 0.1
        score = min(0.95, max(0.05, score))
        return score, f"{score * 100:.1f}% (Fallback Heuristic)", True

    # Calculate candidate daily EMI for the loan
    new_daily_emi = calculate_daily_emi(requested_amount, product.annual_interest_rate, tenure_days)

    # Derive debt_service_to_profit_ratio
    profit = max(1.0, profile.monthly_profit_reference)
    monthly_debt_service = (profile.existing_daily_emi * 30.0) + (requested_amount * (product.annual_interest_rate / 100.0) / 12.0)
    debt_service_ratio = round(monthly_debt_service / profit, 4)

    # Derive pre_screen_eligible
    pre_screen = int(
        product.min_amount <= requested_amount <= product.max_amount and
        product.min_tenure_days <= tenure_days <= product.max_tenure_days and
        profile.monthly_sales_reference >= product.min_monthly_sales and
        profile.business_age_months >= product.min_business_age_months and
        profile.credit_score >= product.min_credit_score
    )

    feature_cols = bundle["feature_cols"]
    preprocessor = bundle["preprocessor"]
    model = bundle["model"]

    row_data = {
        "merchant_type": profile.merchant_type,
        "city": profile.city,
        "city_tier": profile.city_tier,
        "business_age_months": profile.business_age_months,
        "monthly_sales_reference": profile.monthly_sales_reference,
        "monthly_profit_reference": profile.monthly_profit_reference,
        "credit_score": profile.credit_score,
        "existing_loan_count": profile.existing_loan_count,
        "existing_daily_emi": profile.existing_daily_emi,
        "loan_id": product.loan_id,
        "lender_id": product.lender_id,
        "loan_amount_offered": requested_amount,
        "annual_interest_rate": product.annual_interest_rate,
        "tenure_days": tenure_days,
        "processing_fee_pct": product.processing_fee_pct,
        "debt_service_to_profit_ratio": debt_service_ratio,
        "pre_screen_eligible": pre_screen,
    }

    input_df = pd.DataFrame([row_data])
    X = preprocessor.transform(input_df[feature_cols])
    proba = float(model.predict_proba(X)[0][1])

    # Bound in [0.0, 1.0]
    proba = max(0.0, min(1.0, proba))
    formatted_pct = f"{proba * 100:.1f}%"
    return proba, formatted_pct, False

