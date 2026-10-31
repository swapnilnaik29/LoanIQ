"""
Standalone Forecast Generation Script for LoanIQ.
Generates 30-day forecast CSVs for merchants using artifacts/models/cashflow_forecaster.joblib.
Can be executed from CLI or called directly by the backend forecast refresh endpoint.
"""

import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
PREDICTIONS_DIR = ARTIFACTS_DIR / "predictions"


def generate_forecast_for_merchant(merchant_id: str, bundle: dict = None, sales_df: pd.DataFrame = None) -> pd.DataFrame:
    if bundle is None:
        model_path = MODELS_DIR / "cashflow_forecaster.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Forecaster artifact not found at {model_path}. Train models first.")
        bundle = joblib.load(model_path)

    if sales_df is None:
        sales_path = DATA_DIR / "daily_sales.csv"
        sales_df = pd.read_csv(sales_path)
        sales_df["parsed_date"] = pd.to_datetime(sales_df["transaction_date"], format="%d-%m-%Y")

    m_history = sales_df[sales_df["merchant_id"] == merchant_id].sort_values("parsed_date").reset_index(drop=True)
    if m_history.empty:
        raise ValueError(f"No history found for merchant {merchant_id}")

    latest_actual_row = m_history.iloc[-1]
    origin_date = latest_actual_row["parsed_date"]
    latest_actual_balance = float(latest_actual_row["closing_cash_balance"])

    # Extract features
    from scripts.train_models import extract_features_at_origin
    feat_df = extract_features_at_origin(m_history, origin_date)

    preprocessor = bundle["preprocessor"]
    feature_cols = bundle["feature_cols"]
    inflow_model = bundle["inflow_model"]
    exp_model = bundle["exp_model"]

    X_test = preprocessor.transform(feat_df[feature_cols])

    raw_inflow = inflow_model.predict(X_test)
    raw_exp = exp_model.predict(X_test)

    clamped_inflow = np.maximum(raw_inflow, 0.0)
    clamped_exp = np.maximum(raw_exp, 0.0)

    # Net cash flow = inflow - expense
    net_cashflow = clamped_inflow - clamped_exp

    # Cumulative closing balance
    closing_balances = []
    curr_bal = latest_actual_balance
    for ncf in net_cashflow:
        curr_bal += ncf
        closing_balances.append(curr_bal)

    forecast_rows = []
    for i in range(30):
        target_date = feat_df.loc[i, "target_date"].strftime("%Y-%m-%d")
        h = i + 1
        forecast_rows.append({
            "merchant_id": merchant_id,
            "forecast_date": target_date,
            "horizon_day": h,
            "predicted_sales_inflow": round(float(clamped_inflow[i]), 2),
            "predicted_total_expense": round(float(clamped_exp[i]), 2),
            "predicted_net_cashflow": round(float(net_cashflow[i]), 2),
            "predicted_closing_cash_balance": round(float(closing_balances[i]), 2),
        })

    out_df = pd.DataFrame(forecast_rows)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = PREDICTIONS_DIR / f"temp_{merchant_id.lower()}.csv"
    final_path = PREDICTIONS_DIR / f"predicted_{merchant_id.lower().replace('m', 'merchant')}.csv"
    out_df.to_csv(temp_path, index=False)
    temp_path.replace(final_path)
    return out_df


def generate_all_forecasts():
    sales_path = DATA_DIR / "daily_sales.csv"
    sales_df = pd.read_csv(sales_path)
    sales_df["parsed_date"] = pd.to_datetime(sales_df["transaction_date"], format="%d-%m-%Y")

    model_path = MODELS_DIR / "cashflow_forecaster.joblib"
    bundle = joblib.load(model_path)

    merchants = ["M001", "M002", "M003", "M004"]
    for m in merchants:
        df = generate_forecast_for_merchant(m, bundle=bundle, sales_df=sales_df)
        print(f"Merchant {m}: generated {len(df)} rows forecast.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 30-day forecasts for merchants")
    parser.add_argument("--merchant", type=str, default="all", help="Merchant ID (M001..M004) or 'all'")
    args = parser.parse_args()

    if args.merchant == "all":
        generate_all_forecasts()
    else:
        generate_forecast_for_merchant(args.merchant)
        print(f"Forecast generated for {args.merchant}")

