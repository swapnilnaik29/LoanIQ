import pandas as pd
from backend.config import settings


def test_merchants_dataset_exists_and_valid():
    p = settings.data_path / "merchants.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 4
    assert set(df["merchant_id"]) == {"M001", "M002", "M003", "M004"}
    assert df["merchant_id"].duplicated().sum() == 0
    assert df.isnull().sum().sum() == 0


def test_daily_sales_arithmetic_and_continuity():
    p = settings.data_path / "daily_sales.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 4140
    # DD-MM-YYYY format
    df["date"] = pd.to_datetime(df["transaction_date"], format="%d-%m-%Y")
    assert df["date"].isnull().sum() == 0

    # Arithmetic check: sales_inflow - total_expense == net_cashflow
    diff = (df["sales_inflow"] - df["total_expense"]) - df["net_cashflow"]
    assert diff.abs().max() < 0.01

    # Check 1,035 days per merchant
    for m in ["M001", "M002", "M003", "M004"]:
        m_df = df[df["merchant_id"] == m].sort_values("date")
        assert len(m_df) == 1035
        # Balance continuity check: balance[t] == balance[t-1] + net_cashflow[t]
        prev_bal = m_df["closing_cash_balance"].shift(1)
        expected = prev_bal + m_df["net_cashflow"]
        bal_diff = (m_df["closing_cash_balance"].iloc[1:] - expected.iloc[1:]).abs()
        assert bal_diff.max() < 0.01


def test_loan_products_schema():
    import json
    p = settings.data_path / "loan_products.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    products = data.get("products", [])
    assert len(products) == 15
    for prod in products:
        assert "loan_id" in prod
        assert "annual_interest_rate" in prod
        assert "min_amount" in prod
        assert "max_amount" in prod
        assert prod["min_amount"] <= prod["max_amount"]
        assert prod["min_tenure_days"] <= prod["max_tenure_days"]

