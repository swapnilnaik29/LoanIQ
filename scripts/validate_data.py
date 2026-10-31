"""
Data Validation Script for LoanIQ.
Inspects all six datasets in data/ and verifies schemas, data quality, date parsing,
balance continuity, arithmetic consistency, and cross-dataset integrity.
Generates a human-readable validation report.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_PATH = Path(__file__).resolve().parent.parent / "data_validation_report.txt"


def validate_merchants(report_lines: list) -> pd.DataFrame:
    report_lines.append("=" * 60)
    report_lines.append("1. VALIDATING merchants.csv")
    report_lines.append("=" * 60)
    file_path = DATA_DIR / "merchants.csv"
    if not file_path.exists():
        report_lines.append(f"ERROR: {file_path} not found!")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    report_lines.append(f"Row count: {len(df)}")
    expected_cols = [
        "merchant_id", "business_name", "merchant_type", "city", "city_tier",
        "business_age_months", "monthly_sales_reference", "monthly_profit_reference",
        "credit_score", "opening_cash_balance", "preferred_language",
        "existing_loan_count", "existing_daily_emi", "completed_loan_count"
    ]
    missing_cols = set(expected_cols) - set(df.columns)
    if missing_cols:
        report_lines.append(f"ERROR: Missing columns: {missing_cols}")
    else:
        report_lines.append("All expected columns present.")

    duplicates = df["merchant_id"].duplicated().sum()
    report_lines.append(f"Duplicate merchant_ids: {duplicates}")
    null_counts = df.isnull().sum().to_dict()
    report_lines.append(f"Null values: {null_counts}")
    report_lines.append(f"Merchant IDs found: {list(df['merchant_id'].values)}")
    report_lines.append(f"Languages: {list(df['preferred_language'].values)}")
    return df


def validate_daily_sales(report_lines: list, merchants_df: pd.DataFrame) -> pd.DataFrame:
    report_lines.append("\n" + "=" * 60)
    report_lines.append("2. VALIDATING daily_sales.csv")
    report_lines.append("=" * 60)
    file_path = DATA_DIR / "daily_sales.csv"
    if not file_path.exists():
        report_lines.append(f"ERROR: {file_path} not found!")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    report_lines.append(f"Total row count: {len(df)}")
    expected_cols = [
        "transaction_id", "merchant_id", "transaction_date",
        "sales_inflow", "total_expense", "net_cashflow", "closing_cash_balance"
    ]
    missing_cols = set(expected_cols) - set(df.columns)
    if missing_cols:
        report_lines.append(f"ERROR: Missing columns: {missing_cols}")
    else:
        report_lines.append("All expected columns present.")

    # Date parsing: note DD-MM-YYYY format in dataset
    df["parsed_date"] = pd.to_datetime(df["transaction_date"], format="%d-%m-%Y", errors="coerce")
    failed_dates = df["parsed_date"].isnull().sum()
    report_lines.append(f"Failed date parses: {failed_dates}")
    report_lines.append(f"Overall Date Range: {df['parsed_date'].min().strftime('%Y-%m-%d')} to {df['parsed_date'].max().strftime('%Y-%m-%d')}")

    # Arithmetic check: net_cashflow == sales_inflow - total_expense
    arithmetic_diff = (df["sales_inflow"] - df["total_expense"]) - df["net_cashflow"]
    max_arith_diff = arithmetic_diff.abs().max()
    report_lines.append(f"Max difference between (sales_inflow - total_expense) and net_cashflow: {max_arith_diff:.4f}")
    if max_arith_diff > 0.05:
        report_lines.append(f"WARNING: Arithmetic discrepancy detected! Count with diff > 0.05: {(arithmetic_diff.abs() > 0.05).sum()}")
    else:
        report_lines.append("Arithmetic integrity confirmed: net_cashflow = sales_inflow - total_expense (within rounding)")

    # Per merchant checks
    for m_id, m_group in df.groupby("merchant_id"):
        m_group = m_group.sort_values("parsed_date")
        row_cnt = len(m_group)
        date_min = m_group["parsed_date"].min().strftime("%Y-%m-%d")
        date_max = m_group["parsed_date"].max().strftime("%Y-%m-%d")
        # Check continuity (no missing days)
        full_date_range = pd.date_range(start=m_group["parsed_date"].min(), end=m_group["parsed_date"].max(), freq="D")
        missing_days = len(full_date_range) - row_cnt

        # Check balance continuity
        # closing_balance[t] vs closing_balance[t-1] + net_cashflow[t]
        shifted_prev_bal = m_group["closing_cash_balance"].shift(1)
        expected_bal = shifted_prev_bal + m_group["net_cashflow"]
        bal_diff = (m_group["closing_cash_balance"].iloc[1:] - expected_bal.iloc[1:]).abs().max()

        # Day 1 balance vs merchant opening balance if available
        first_row = m_group.iloc[0]
        day1_note = ""
        if not merchants_df.empty and m_id in merchants_df["merchant_id"].values:
            opening_bal = merchants_df.loc[merchants_df["merchant_id"] == m_id, "opening_cash_balance"].values[0]
            day1_expected = opening_bal + first_row["net_cashflow"]
            day1_diff = abs(first_row["closing_cash_balance"] - day1_expected)
            day1_note = f" (Day 1 vs opening bal {opening_bal}: diff={day1_diff:.2f})"

        report_lines.append(
            f"Merchant {m_id}: {row_cnt} days ({date_min} to {date_max}), missing calendar days: {missing_days}, "
            f"balance continuity max diff: {bal_diff:.4f}{day1_note}"
        )

    return df


def validate_loan_products(report_lines: list) -> list:
    report_lines.append("\n" + "=" * 60)
    report_lines.append("3. VALIDATING loan_products.json")
    report_lines.append("=" * 60)
    file_path = DATA_DIR / "loan_products.json"
    if not file_path.exists():
        report_lines.append(f"ERROR: {file_path} not found!")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    products = data.get("products", [])
    report_lines.append(f"Product count: {len(products)}")
    expected_fields = [
        "loan_id", "lender_id", "lender_name", "product_name",
        "min_amount", "max_amount", "annual_interest_rate",
        "min_tenure_days", "max_tenure_days", "processing_fee_pct",
        "prepayment_fee_pct", "min_monthly_sales", "min_business_age_months",
        "min_credit_score", "disclaimer"
    ]

    for p in products:
        missing = [f for f in expected_fields if f not in p]
        if missing:
            report_lines.append(f"Product {p.get('loan_id', 'UNKNOWN')} missing fields: {missing}")

    report_lines.append("Summary of Loan Products:")
    for p in products:
        report_lines.append(
            f" - {p['loan_id']}: {p['product_name']} by {p['lender_name']} | Rate: {p['annual_interest_rate']}% | "
            f"Range: ₹{p['min_amount']:,} - ₹{p['max_amount']:,} | Tenure: {p['min_tenure_days']}-{p['max_tenure_days']} days | "
            f"Proc Fee: {p['processing_fee_pct']}% | Prepay Fee: {p['prepayment_fee_pct']}%"
        )
    return products


def validate_loan_applications(report_lines: list) -> pd.DataFrame:
    report_lines.append("\n" + "=" * 60)
    report_lines.append("4. VALIDATING loan_applications.csv")
    report_lines.append("=" * 60)
    file_path = DATA_DIR / "loan_applications.csv"
    if not file_path.exists():
        report_lines.append(f"ERROR: {file_path} not found!")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    report_lines.append(f"Total row count: {len(df)}")
    expected_cols = [
        "application_id", "application_date", "applicant_id", "business_name",
        "merchant_type", "city", "city_tier", "business_age_months",
        "monthly_sales_reference", "monthly_profit_reference", "credit_score",
        "existing_loan_count", "existing_daily_emi", "loan_id", "lender_id",
        "loan_amount_offered", "annual_interest_rate", "tenure_days",
        "processing_fee_pct", "debt_service_to_profit_ratio", "pre_screen_eligible", "accepted"
    ]
    missing_cols = set(expected_cols) - set(df.columns)
    if missing_cols:
        report_lines.append(f"ERROR: Missing columns: {missing_cols}")
    else:
        report_lines.append("All expected columns present.")

    df["parsed_date"] = pd.to_datetime(df["application_date"], format="%Y-%m-%d", errors="coerce")
    report_lines.append(f"Date range: {df['parsed_date'].min().strftime('%Y-%m-%d')} to {df['parsed_date'].max().strftime('%Y-%m-%d')}")
    target_counts = df["accepted"].value_counts().to_dict()
    report_lines.append(f"Target distribution (accepted): {target_counts}")
    unique_applicants = df["applicant_id"].nunique()
    report_lines.append(f"Unique applicants: {unique_applicants} across {len(df)} applications")
    null_counts = df.isnull().sum()
    null_dict = null_counts[null_counts > 0].to_dict()
    report_lines.append(f"Columns with null values: {null_dict if null_dict else 'None'}")
    return df


def validate_merchant_loans(report_lines: list, merchants_df: pd.DataFrame):
    report_lines.append("\n" + "=" * 60)
    report_lines.append("5. VALIDATING pending & completed loan records")
    report_lines.append("=" * 60)

    pending_path = DATA_DIR / "merchants_loans_pending.csv"
    completed_path = DATA_DIR / "merchants_loans_completed.csv"

    p_df = pd.read_csv(pending_path) if pending_path.exists() else pd.DataFrame()
    c_df = pd.read_csv(completed_path) if completed_path.exists() else pd.DataFrame()

    report_lines.append(f"Pending loans row count: {len(p_df)}")
    report_lines.append(f"Completed loans row count: {len(c_df)}")

    if not p_df.empty:
        report_lines.append("\nPending loans per merchant:")
        for m_id, grp in p_df.groupby("merchant_id"):
            tot_principal = grp["remaining_principal"].sum()
            tot_emi = grp["daily_emi"].sum()
            report_lines.append(f" - {m_id}: {len(grp)} active loans, remaining principal=₹{tot_principal:,.2f}, total daily EMI=₹{tot_emi:.2f}")

    if not c_df.empty:
        report_lines.append("\nCompleted loans per merchant:")
        for m_id, grp in c_df.groupby("merchant_id"):
            repaid = grp["principal_repaid_to_date"].sum()
            report_lines.append(f" - {m_id}: {len(grp)} completed loans, repaid principal=₹{repaid:,.2f}")


def run_validation():
    report_lines = [
        "LoanIQ Dataset Validation Report",
        "Generated during Phase 1 execution\n"
    ]
    merchants_df = validate_merchants(report_lines)
    validate_daily_sales(report_lines, merchants_df)
    validate_loan_products(report_lines)
    validate_loan_applications(report_lines)
    validate_merchant_loans(report_lines, merchants_df)

    report_text = "\n".join(report_lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)
    try:
        print(report_text)
    except UnicodeEncodeError:
        print(report_text.encode("ascii", errors="replace").decode("ascii"))
    print(f"\nReport written to: {REPORT_PATH}")


if __name__ == "__main__":
    run_validation()

