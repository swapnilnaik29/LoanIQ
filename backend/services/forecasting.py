"""
Cash-Flow Forecasting Service for LoanIQ.
Provides forecast retrieval, horizon filtering (3, 7, 15, 30 days),
aggregate calculations, safety-buffer evaluation, and on-demand refresh.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import joblib
import pandas as pd
from backend.config import settings
from backend.schemas.forecast import ForecastRow, MerchantForecastResponse

_FORECASTER_BUNDLE = None


def get_forecaster_bundle():
    global _FORECASTER_BUNDLE
    if _FORECASTER_BUNDLE is None:
        model_path = settings.artifacts_path / "models" / "cashflow_forecaster.joblib"
        if model_path.exists():
            _FORECASTER_BUNDLE = joblib.load(model_path)
    return _FORECASTER_BUNDLE


def get_merchant_forecast(
    merchant_id: str,
    horizon_days: int = 30,
    safety_buffer: Optional[float] = None
) -> MerchantForecastResponse:
    if safety_buffer is None:
        safety_buffer = settings.FORECAST_SAFETY_BUFFER

    # Valid horizons allowed: 3, 7, 15, 30
    if horizon_days not in [3, 7, 15, 30]:
        horizon_days = 30

    csv_name = f"predicted_{merchant_id.lower().replace('m', 'merchant')}.csv"
    csv_path = settings.artifacts_path / "predictions" / csv_name

    # If predictions CSV does not exist, attempt to generate it
    if not csv_path.exists():
        from scripts.generate_forecasts import generate_forecast_for_merchant
        df = generate_forecast_for_merchant(merchant_id)
    else:
        df = pd.read_csv(csv_path)

    # Filter to requested horizon view
    filtered_df = df[df["horizon_day"] <= horizon_days].sort_values("horizon_day").reset_index(drop=True)

    rows = []
    for _, r in filtered_df.iterrows():
        rows.append(ForecastRow(
            merchant_id=r["merchant_id"],
            forecast_date=r["forecast_date"],
            horizon_day=int(r["horizon_day"]),
            predicted_sales_inflow=round(float(r["predicted_sales_inflow"]), 2),
            predicted_total_expense=round(float(r["predicted_total_expense"]), 2),
            predicted_net_cashflow=round(float(r["predicted_net_cashflow"]), 2),
            predicted_closing_cash_balance=round(float(r["predicted_closing_cash_balance"]), 2)
        ))

    summary_inflow = round(float(filtered_df["predicted_sales_inflow"].sum()), 2)
    summary_expense = round(float(filtered_df["predicted_total_expense"].sum()), 2)
    summary_net_cashflow = round(float(filtered_df["predicted_net_cashflow"].sum()), 2)
    avg_inflow = round(float(filtered_df["predicted_sales_inflow"].mean()), 2)
    avg_expense = round(float(filtered_df["predicted_total_expense"].mean()), 2)
    avg_net = round(float(filtered_df["predicted_net_cashflow"].mean()), 2)
    min_balance = round(float(filtered_df["predicted_closing_cash_balance"].min()), 2)
    is_neg_risk = min_balance < safety_buffer

    # Modified timestamp of prediction file
    mtime = datetime.fromtimestamp(csv_path.stat().st_mtime).isoformat() if csv_path.exists() else datetime.now().isoformat()

    return MerchantForecastResponse(
        merchant_id=merchant_id,
        horizon_selected=horizon_days,
        generated_at=mtime,
        safety_buffer=safety_buffer,
        is_negative_risk=is_neg_risk,
        min_projected_balance=min_balance,
        summary_inflow=summary_inflow,
        summary_expense=summary_expense,
        summary_net_cashflow=summary_net_cashflow,
        avg_daily_inflow=avg_inflow,
        avg_daily_expense=avg_expense,
        avg_daily_net_cashflow=avg_net,
        rows=rows
    )


def refresh_merchant_forecast(merchant_id: str) -> MerchantForecastResponse:
    from scripts.generate_forecasts import generate_forecast_for_merchant
    generate_forecast_for_merchant(merchant_id)
    return get_merchant_forecast(merchant_id, horizon_days=30)

