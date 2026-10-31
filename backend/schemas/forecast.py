from typing import List
from pydantic import BaseModel


class ForecastRow(BaseModel):
    merchant_id: str
    forecast_date: str
    horizon_day: int
    predicted_sales_inflow: float
    predicted_total_expense: float
    predicted_net_cashflow: float
    predicted_closing_cash_balance: float


class MerchantForecastResponse(BaseModel):
    merchant_id: str
    horizon_selected: int
    generated_at: str
    safety_buffer: float
    is_negative_risk: bool
    min_projected_balance: float
    summary_inflow: float
    summary_expense: float
    summary_net_cashflow: float
    avg_daily_inflow: float
    avg_daily_expense: float
    avg_daily_net_cashflow: float
    rows: List[ForecastRow]
    disclaimer: str = "Forecasts are algorithmic estimates based on historical trends; actual merchant sales may vary."

