"""
Merchant and Product Data Repository Service.
Loads merchants, active/completed loans, and loan products dynamically from data/.
Ensures strict merchant isolation.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from backend.config import settings
from backend.schemas.merchant import MerchantProfile, MerchantLoanAccount
from backend.schemas.loan import LoanProduct


def get_merchants_df() -> pd.DataFrame:
    path = settings.data_path / "merchants.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return pd.read_csv(path)


def get_all_merchant_ids() -> List[str]:
    df = get_merchants_df()
    return list(df["merchant_id"].dropna().unique())


def get_merchant_profile(merchant_id: str) -> Optional[MerchantProfile]:
    df = get_merchants_df()
    match = df[df["merchant_id"] == merchant_id]
    if match.empty:
        return None
    row = match.iloc[0].to_dict()
    return MerchantProfile(**row)


def get_merchant_loans(merchant_id: str, status: str = "all") -> List[MerchantLoanAccount]:
    records: List[MerchantLoanAccount] = []

    if status in ["active", "all"]:
        p_path = settings.data_path / "merchants_loans_pending.csv"
        if p_path.exists():
            pdf = pd.read_csv(p_path)
            m_pdf = pdf[pdf["merchant_id"] == merchant_id]
            for _, r in m_pdf.iterrows():
                d = r.to_dict()
                if pd.isna(d.get("next_due_date")):
                    d["next_due_date"] = None
                records.append(MerchantLoanAccount(**d))

    if status in ["completed", "all"]:
        c_path = settings.data_path / "merchants_loans_completed.csv"
        if c_path.exists():
            cdf = pd.read_csv(c_path)
            m_cdf = cdf[cdf["merchant_id"] == merchant_id]
            for _, r in m_cdf.iterrows():
                d = r.to_dict()
                if pd.isna(d.get("next_due_date")):
                    d["next_due_date"] = None
                records.append(MerchantLoanAccount(**d))

    return records


def get_loan_products() -> List[LoanProduct]:
    path = settings.data_path / "loan_products.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [LoanProduct(**p) for p in data.get("products", [])]


def get_loan_product_by_id(loan_id: str) -> Optional[LoanProduct]:
    products = get_loan_products()
    for p in products:
        if p.loan_id == loan_id:
            return p
    return None

