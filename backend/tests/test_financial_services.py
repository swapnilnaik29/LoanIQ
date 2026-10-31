import pytest
from backend.services.emi_calculator import calculate_daily_emi, calculate_loan_cost
from backend.services.recommendation import check_product_eligibility, recommend_loans, compare_loans
from backend.services.loan_optimizer import simulate_loan, get_merchant_optimization
from backend.services.merchant_service import get_merchant_profile, get_merchant_loans


def test_emi_calculation_matches_reducing_balance():
    # In pending loans dataset: P=85000, rate=17%, tenure=540 days -> daily_emi=178.07
    emi = calculate_daily_emi(85000.0, 17.0, 540)
    assert abs(emi - 178.07) <= 0.05

    # Check loan cost breakdown
    cost = calculate_loan_cost(85000.0, 17.0, 540, processing_fee_pct=1.0)
    assert cost["daily_emi"] == 178.07
    assert cost["total_repayment"] == round(178.07 * 540, 2)
    assert cost["processing_fee"] == 850.0
    assert cost["total_cost"] == round(cost["total_interest"] + 850.0, 2)


def test_eligibility_enforcement():
    # LP001: min_amount=20,000, max_amount=150,000, min_sales=50,000, min_score=620
    # M001 has sales=145,000, score=684
    # Test valid request
    res_valid = check_product_eligibility("M001", "LP001", 100000.0, 365)
    assert res_valid.is_eligible
    assert len(res_valid.failed_reasons) == 0

    # Test amount exceeding limit
    res_high_amount = check_product_eligibility("M001", "LP001", 500000.0, 365)
    assert not res_high_amount.is_eligible
    assert any("exceeds maximum allowed" in r for r in res_high_amount.failed_reasons)

    # Test tenure below minimum
    res_short_tenure = check_product_eligibility("M001", "LP001", 100000.0, 90)
    assert not res_short_tenure.is_eligible
    assert any("below minimum" in r for r in res_short_tenure.failed_reasons)


def test_recommendation_and_ranking():
    recs = recommend_loans("M001", requested_amount=100000.0, tenure_days=365)
    assert len(recs) == 15
    # Eligible products must be ranked higher than ineligible ones
    eligible = [r for r in recs if r.is_eligible]
    ineligible = [r for r in recs if not r.is_eligible]
    assert len(eligible) > 0
    if ineligible:
        assert eligible[0].rank_score > ineligible[0].rank_score


def test_merchant_data_isolation():
    p1 = get_merchant_profile("M001")
    p2 = get_merchant_profile("M002")
    assert p1.merchant_id == "M001"
    assert p2.merchant_id == "M002"
    assert p1.business_name != p2.business_name

    l1 = get_merchant_loans("M001", "active")
    l2 = get_merchant_loans("M002", "active")
    assert all(l.merchant_id == "M001" for l in l1)
    assert all(l.merchant_id == "M002" for l in l2)


def test_loan_simulator_and_affordability():
    sim = simulate_loan(
        merchant_id="M001",
        loan_amount=50000.0,
        tenure_days=180,
        annual_interest_rate=15.0,
        processing_fee_pct=1.0,
        safety_buffer=5000.0
    )
    assert sim.loan_amount == 50000.0
    assert sim.daily_emi > 0
    assert sim.total_cost > 0
    assert len(sim.suggested_alternatives) >= 2


def test_optimization_summary_and_consolidation_rule():
    opt = get_merchant_optimization("M001")
    assert opt.active_loans_count == 2
    assert opt.total_remaining_principal > 0
    assert opt.total_current_daily_emi == 358.17
    assert opt.completed_loans_count == 2
    assert opt.total_repaid_principal == 165000.0
    assert opt.refinance_or_consolidation_recommendation is not None

