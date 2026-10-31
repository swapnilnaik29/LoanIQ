import json
from pathlib import Path
import joblib
import pandas as pd
from backend.config import settings
from backend.services.forecasting import get_merchant_forecast
from backend.services.acceptance_model import predict_loan_acceptance_probability


def test_forecast_artifacts_and_metrics():
    model_path = settings.artifacts_path / "models" / "cashflow_forecaster.joblib"
    assert model_path.exists()
    bundle = joblib.load(model_path)
    assert "preprocessor" in bundle
    assert "inflow_model" in bundle
    assert "exp_model" in bundle

    meta_path = settings.artifacts_path / "models" / "model_metadata.json"
    assert meta_path.exists()
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "cashflow_forecaster" in meta
    assert "loan_acceptance_model" in meta


def test_merchant_prediction_csvs_and_balance_continuity():
    for m in ["merchant001", "merchant002", "merchant003", "merchant004"]:
        csv_path = settings.artifacts_path / "predictions" / f"predicted_{m}.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) == 30
        assert list(df.columns) == [
            "merchant_id", "forecast_date", "horizon_day",
            "predicted_sales_inflow", "predicted_total_expense",
            "predicted_net_cashflow", "predicted_closing_cash_balance"
        ]
        # Inflow and expense cannot be negative
        assert (df["predicted_sales_inflow"] >= 0).all()
        assert (df["predicted_total_expense"] >= 0).all()

        # Net cashflow == inflow - expense
        diff = (df["predicted_sales_inflow"] - df["predicted_total_expense"]) - df["predicted_net_cashflow"]
        assert diff.abs().max() <= 0.05

        # Balance continuity
        for i in range(1, 30):
            prev_b = df.loc[i - 1, "predicted_closing_cash_balance"]
            net_c = df.loc[i, "predicted_net_cashflow"]
            curr_b = df.loc[i, "predicted_closing_cash_balance"]
            assert abs((prev_b + net_c) - curr_b) <= 0.05


def test_acceptance_probability_bounds():
    prob, prob_str, is_fb = predict_loan_acceptance_probability("M001", "LP001", 100000.0, 365)
    assert 0.0 <= prob <= 1.0
    assert "%" in prob_str

    # Test another merchant and product
    prob2, prob_str2, _ = predict_loan_acceptance_probability("M004", "LP005", 80000.0, 180)
    assert 0.0 <= prob2 <= 1.0

