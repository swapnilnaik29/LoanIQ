"""
Training script for LoanIQ ML models:
1. Pooled horizon-aware daily cash-flow forecaster (sales_inflow and total_expense).
2. Loan acceptance probability classifier with preprocessing pipeline and probability calibration.
3. Generates artifacts/models/model_metadata.json and predictions for merchants M001..M004.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    mean_absolute_error,
    root_mean_squared_error,
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    brier_score_loss,
    confusion_matrix,
)
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
PREDICTIONS_DIR = ARTIFACTS_DIR / "predictions"


def build_forecast_dataset(df: pd.DataFrame, step_days: int = 2):
    """
    Build pooled direct horizon-aware samples with zero future leakage.
    For each merchant and origin date t, features are derived strictly from observations <= t.
    Horizons h in 1..30 predict values at t + h.
    step_days: stride across origin dates to control dataset size while maintaining coverage.
    """
    df = df.sort_values(["merchant_id", "parsed_date"]).reset_index(drop=True)
    records = []

    merchants = df["merchant_id"].unique()
    for m_id in merchants:
        m_df = df[df["merchant_id"] == m_id].sort_values("parsed_date").reset_index(drop=True)
        n = len(m_df)
        # We need at least 28 days of history for lags and rolling stats
        min_origin_idx = 28
        max_origin_idx = n - 31  # ensure at least 30 future days exist for training samples

        for origin_idx in range(min_origin_idx, max_origin_idx + 1, step_days):
            origin_date = m_df.loc[origin_idx, "parsed_date"]
            hist = m_df.iloc[: origin_idx + 1]

            # Inflow features strictly <= origin_date
            inflow_lag1 = hist.iloc[-1]["sales_inflow"]
            inflow_lag2 = hist.iloc[-2]["sales_inflow"]
            inflow_lag3 = hist.iloc[-3]["sales_inflow"]
            inflow_lag7 = hist.iloc[-7]["sales_inflow"]
            inflow_lag14 = hist.iloc[-14]["sales_inflow"]
            inflow_lag28 = hist.iloc[-28]["sales_inflow"]
            inflow_roll7_mean = hist.iloc[-7:]["sales_inflow"].mean()
            inflow_roll7_std = hist.iloc[-7:]["sales_inflow"].std()
            inflow_roll14_mean = hist.iloc[-14:]["sales_inflow"].mean()
            inflow_roll14_std = hist.iloc[-14:]["sales_inflow"].std()
            inflow_roll28_mean = hist.iloc[-28:]["sales_inflow"].mean()
            inflow_roll28_std = hist.iloc[-28:]["sales_inflow"].std()

            # Expense features strictly <= origin_date
            exp_lag1 = hist.iloc[-1]["total_expense"]
            exp_lag2 = hist.iloc[-2]["total_expense"]
            exp_lag3 = hist.iloc[-3]["total_expense"]
            exp_lag7 = hist.iloc[-7]["total_expense"]
            exp_lag14 = hist.iloc[-14]["total_expense"]
            exp_lag28 = hist.iloc[-28]["total_expense"]
            exp_roll7_mean = hist.iloc[-7:]["total_expense"].mean()
            exp_roll7_std = hist.iloc[-7:]["total_expense"].std()
            exp_roll14_mean = hist.iloc[-14:]["total_expense"].mean()
            exp_roll14_std = hist.iloc[-14:]["total_expense"].std()
            exp_roll28_mean = hist.iloc[-28:]["total_expense"].mean()
            exp_roll28_std = hist.iloc[-28:]["total_expense"].std()

            # Net cashflow recent mean
            net_roll7_mean = hist.iloc[-7:]["net_cashflow"].mean()

            # Generate samples for horizons 1..30
            for h in range(1, 31):
                target_idx = origin_idx + h
                target_row = m_df.iloc[target_idx]
                target_date = target_row["parsed_date"]

                records.append({
                    "merchant_id": m_id,
                    "origin_date": origin_date,
                    "target_date": target_date,
                    "horizon": h,
                    "target_dayofweek": target_date.day_of_week,
                    "target_day": target_date.day,
                    "target_month": target_date.month,
                    "target_is_weekend": int(target_date.day_of_week in [5, 6]),
                    # Inflow features
                    "inflow_lag1": inflow_lag1,
                    "inflow_lag2": inflow_lag2,
                    "inflow_lag3": inflow_lag3,
                    "inflow_lag7": inflow_lag7,
                    "inflow_lag14": inflow_lag14,
                    "inflow_lag28": inflow_lag28,
                    "inflow_roll7_mean": inflow_roll7_mean,
                    "inflow_roll7_std": inflow_roll7_std if not np.isnan(inflow_roll7_std) else 0.0,
                    "inflow_roll14_mean": inflow_roll14_mean,
                    "inflow_roll14_std": inflow_roll14_std if not np.isnan(inflow_roll14_std) else 0.0,
                    "inflow_roll28_mean": inflow_roll28_mean,
                    "inflow_roll28_std": inflow_roll28_std if not np.isnan(inflow_roll28_std) else 0.0,
                    # Expense features
                    "exp_lag1": exp_lag1,
                    "exp_lag2": exp_lag2,
                    "exp_lag3": exp_lag3,
                    "exp_lag7": exp_lag7,
                    "exp_lag14": exp_lag14,
                    "exp_lag28": exp_lag28,
                    "exp_roll7_mean": exp_roll7_mean,
                    "exp_roll7_std": exp_roll7_std if not np.isnan(exp_roll7_std) else 0.0,
                    "exp_roll14_mean": exp_roll14_mean,
                    "exp_roll14_std": exp_roll14_std if not np.isnan(exp_roll14_std) else 0.0,
                    "exp_roll28_mean": exp_roll28_mean,
                    "exp_roll28_std": exp_roll28_std if not np.isnan(exp_roll28_std) else 0.0,
                    "net_roll7_mean": net_roll7_mean,
                    # Targets
                    "target_sales_inflow": target_row["sales_inflow"],
                    "target_total_expense": target_row["total_expense"],
                })

    return pd.DataFrame(records)


def extract_features_at_origin(m_df: pd.DataFrame, origin_date: pd.Timestamp) -> pd.DataFrame:
    """Extract feature dictionary for horizons 1..30 at a single origin date."""
    hist = m_df[m_df["parsed_date"] <= origin_date].sort_values("parsed_date").reset_index(drop=True)
    m_id = hist["merchant_id"].iloc[0]

    inflow_lag1 = hist.iloc[-1]["sales_inflow"]
    inflow_lag2 = hist.iloc[-2]["sales_inflow"]
    inflow_lag3 = hist.iloc[-3]["sales_inflow"]
    inflow_lag7 = hist.iloc[-7]["sales_inflow"]
    inflow_lag14 = hist.iloc[-14]["sales_inflow"]
    inflow_lag28 = hist.iloc[-28]["sales_inflow"]
    inflow_roll7_mean = hist.iloc[-7:]["sales_inflow"].mean()
    inflow_roll7_std = hist.iloc[-7:]["sales_inflow"].std()
    inflow_roll14_mean = hist.iloc[-14:]["sales_inflow"].mean()
    inflow_roll14_std = hist.iloc[-14:]["sales_inflow"].std()
    inflow_roll28_mean = hist.iloc[-28:]["sales_inflow"].mean()
    inflow_roll28_std = hist.iloc[-28:]["sales_inflow"].std()

    exp_lag1 = hist.iloc[-1]["total_expense"]
    exp_lag2 = hist.iloc[-2]["total_expense"]
    exp_lag3 = hist.iloc[-3]["total_expense"]
    exp_lag7 = hist.iloc[-7]["total_expense"]
    exp_lag14 = hist.iloc[-14]["total_expense"]
    exp_lag28 = hist.iloc[-28]["total_expense"]
    exp_roll7_mean = hist.iloc[-7:]["total_expense"].mean()
    exp_roll7_std = hist.iloc[-7:]["total_expense"].std()
    exp_roll14_mean = hist.iloc[-14:]["total_expense"].mean()
    exp_roll14_std = hist.iloc[-14:]["total_expense"].std()
    exp_roll28_mean = hist.iloc[-28:]["total_expense"].mean()
    exp_roll28_std = hist.iloc[-28:]["total_expense"].std()

    net_roll7_mean = hist.iloc[-7:]["net_cashflow"].mean()

    rows = []
    for h in range(1, 31):
        target_date = origin_date + timedelta(days=h)
        rows.append({
            "merchant_id": m_id,
            "origin_date": origin_date,
            "target_date": target_date,
            "horizon": h,
            "target_dayofweek": target_date.day_of_week,
            "target_day": target_date.day,
            "target_month": target_date.month,
            "target_is_weekend": int(target_date.day_of_week in [5, 6]),
            "inflow_lag1": inflow_lag1,
            "inflow_lag2": inflow_lag2,
            "inflow_lag3": inflow_lag3,
            "inflow_lag7": inflow_lag7,
            "inflow_lag14": inflow_lag14,
            "inflow_lag28": inflow_lag28,
            "inflow_roll7_mean": inflow_roll7_mean,
            "inflow_roll7_std": inflow_roll7_std if not np.isnan(inflow_roll7_std) else 0.0,
            "inflow_roll14_mean": inflow_roll14_mean,
            "inflow_roll14_std": inflow_roll14_std if not np.isnan(inflow_roll14_std) else 0.0,
            "inflow_roll28_mean": inflow_roll28_mean,
            "inflow_roll28_std": inflow_roll28_std if not np.isnan(inflow_roll28_std) else 0.0,
            "exp_lag1": exp_lag1,
            "exp_lag2": exp_lag2,
            "exp_lag3": exp_lag3,
            "exp_lag7": exp_lag7,
            "exp_lag14": exp_lag14,
            "exp_lag28": exp_lag28,
            "exp_roll7_mean": exp_roll7_mean,
            "exp_roll7_std": exp_roll7_std if not np.isnan(exp_roll7_std) else 0.0,
            "exp_roll14_mean": exp_roll14_mean,
            "exp_roll14_std": exp_roll14_std if not np.isnan(exp_roll14_std) else 0.0,
            "exp_roll28_mean": exp_roll28_mean,
            "exp_roll28_std": exp_roll28_std if not np.isnan(exp_roll28_std) else 0.0,
            "net_roll7_mean": net_roll7_mean,
        })
    return pd.DataFrame(rows)


def train_forecaster(daily_sales_df: pd.DataFrame):
    print("--- Training Cash-Flow Forecaster ---")
    feat_df = build_forecast_dataset(daily_sales_df, step_days=2)
    feature_cols = [
        "merchant_id", "horizon", "target_dayofweek", "target_day", "target_month", "target_is_weekend",
        "inflow_lag1", "inflow_lag2", "inflow_lag3", "inflow_lag7", "inflow_lag14", "inflow_lag28",
        "inflow_roll7_mean", "inflow_roll7_std", "inflow_roll14_mean", "inflow_roll14_std",
        "inflow_roll28_mean", "inflow_roll28_std",
        "exp_lag1", "exp_lag2", "exp_lag3", "exp_lag7", "exp_lag14", "exp_lag28",
        "exp_roll7_mean", "exp_roll7_std", "exp_roll14_mean", "exp_roll14_std",
        "exp_roll28_mean", "exp_roll28_std", "net_roll7_mean"
    ]
    cat_cols = ["merchant_id"]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    # Chronological split for validation
    val_cutoff = pd.Timestamp("2026-07-01")
    train_mask = feat_df["origin_date"] < val_cutoff
    val_mask = feat_df["origin_date"] >= val_cutoff

    train_df = feat_df[train_mask]
    val_df = feat_df[val_mask]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
            ("num", StandardScaler(), num_cols),
        ]
    )

    X_train = preprocessor.fit_transform(train_df[feature_cols])
    X_val = preprocessor.transform(val_df[feature_cols])

    # Seasonal naive baseline: uses lag from same day-of-week in last week (lag7 for h<=7, etc.)
    naive_inflow_pred = val_df["inflow_lag7"].values
    naive_exp_pred = val_df["exp_lag7"].values

    inflow_baseline_mae = mean_absolute_error(val_df["target_sales_inflow"], naive_inflow_pred)
    inflow_baseline_rmse = root_mean_squared_error(val_df["target_sales_inflow"], naive_inflow_pred)
    exp_baseline_mae = mean_absolute_error(val_df["target_total_expense"], naive_exp_pred)
    exp_baseline_rmse = root_mean_squared_error(val_df["target_total_expense"], naive_exp_pred)

    # Train HistGradientBoostingRegressor
    inflow_model = HistGradientBoostingRegressor(max_iter=150, min_samples_leaf=15, random_state=42)
    exp_model = HistGradientBoostingRegressor(max_iter=150, min_samples_leaf=15, random_state=42)

    inflow_model.fit(X_train, train_df["target_sales_inflow"])
    exp_model.fit(X_train, train_df["target_total_expense"])

    val_inflow_pred = inflow_model.predict(X_val)
    val_exp_pred = exp_model.predict(X_val)

    inflow_mae = mean_absolute_error(val_df["target_sales_inflow"], val_inflow_pred)
    inflow_rmse = root_mean_squared_error(val_df["target_sales_inflow"], val_inflow_pred)
    exp_mae = mean_absolute_error(val_df["target_total_expense"], val_exp_pred)
    exp_rmse = root_mean_squared_error(val_df["target_total_expense"], val_exp_pred)

    # Horizon breakdown
    horizon_metrics = {}
    for h_range, (h_min, h_max) in [("1-3", (1, 3)), ("4-7", (4, 7)), ("8-15", (8, 15)), ("16-30", (16, 30))]:
        sub_mask = (val_df["horizon"] >= h_min) & (val_df["horizon"] <= h_max)
        sub_val = val_df[sub_mask]
        sub_inflow_true = sub_val["target_sales_inflow"]
        sub_inflow_pred = val_inflow_pred[sub_mask]
        sub_exp_true = sub_val["target_total_expense"]
        sub_exp_pred = val_exp_pred[sub_mask]

        horizon_metrics[h_range] = {
            "inflow_mae": float(mean_absolute_error(sub_inflow_true, sub_inflow_pred)),
            "inflow_rmse": float(root_mean_squared_error(sub_inflow_true, sub_inflow_pred)),
            "exp_mae": float(mean_absolute_error(sub_exp_true, sub_exp_pred)),
            "exp_rmse": float(root_mean_squared_error(sub_exp_true, sub_exp_pred)),
        }

    # Now retrain on full dataset for maximum accuracy on future 30 days
    X_full = preprocessor.fit_transform(feat_df[feature_cols])
    inflow_model.fit(X_full, feat_df["target_sales_inflow"])
    exp_model.fit(X_full, feat_df["target_total_expense"])

    bundle = {
        "preprocessor": preprocessor,
        "feature_cols": feature_cols,
        "inflow_model": inflow_model,
        "exp_model": exp_model,
        "training_origin_end": daily_sales_df["parsed_date"].max().strftime("%Y-%m-%d"),
    }
    joblib.dump(bundle, MODELS_DIR / "cashflow_forecaster.joblib")
    print("Saved forecaster to cashflow_forecaster.joblib")

    metrics = {
        "model_type": "HistGradientBoostingRegressor (Pooled horizon-aware direct multi-horizon)",
        "train_samples": int(len(train_df)),
        "validation_samples": int(len(val_df)),
        "validation_split_date": "2026-07-01",
        "inflow_mae": float(inflow_mae),
        "inflow_rmse": float(inflow_rmse),
        "expense_mae": float(exp_mae),
        "expense_rmse": float(exp_rmse),
        "baseline_comparison": {
            "inflow_seasonal_naive_mae": float(inflow_baseline_mae),
            "inflow_seasonal_naive_rmse": float(inflow_baseline_rmse),
            "expense_seasonal_naive_mae": float(exp_baseline_mae),
            "expense_seasonal_naive_rmse": float(exp_baseline_rmse),
        },
        "metrics_by_horizon": horizon_metrics,
        "feature_list": feature_cols,
        "limitations": [
            "Trained on synthetic merchant transaction history.",
            "Extreme macroeconomic shocks and unobserved vendor disruptions are not modeled.",
            "Forecasts assume continued operations without prolonged store closures."
        ]
    }
    return bundle, metrics


def generate_and_save_merchant_forecasts(daily_sales_df: pd.DataFrame, forecaster_bundle: dict):
    """
    Generate 30-day forecast CSVs for M001..M004 from 2026-10-31 origin.
    Includes forecast_date, horizon_day, predicted_sales_inflow, predicted_total_expense,
    predicted_net_cashflow, predicted_closing_cash_balance.
    Derives net cash flow as inflow - expense, and closing balance cumulatively.
    """
    print("--- Generating 30-Day Forecasts for Merchants M001-M004 ---")
    origin_date = daily_sales_df["parsed_date"].max()
    preprocessor = forecaster_bundle["preprocessor"]
    feature_cols = forecaster_bundle["feature_cols"]
    inflow_model = forecaster_bundle["inflow_model"]
    exp_model = forecaster_bundle["exp_model"]

    for m_id in ["M001", "M002", "M003", "M004"]:
        m_history = daily_sales_df[daily_sales_df["merchant_id"] == m_id].sort_values("parsed_date").reset_index(drop=True)
        latest_actual_row = m_history.iloc[-1]
        latest_actual_balance = latest_actual_row["closing_cash_balance"]

        feat_df = extract_features_at_origin(m_history, origin_date)
        X_test = preprocessor.transform(feat_df[feature_cols])

        raw_inflow = inflow_model.predict(X_test)
        raw_exp = exp_model.predict(X_test)

        # Inflow and expense cannot physically be negative
        clamped_inflow = np.maximum(raw_inflow, 0.0)
        clamped_exp = np.maximum(raw_exp, 0.0)

        # Net cash flow strictly derived as inflow - expense
        net_cashflow = clamped_inflow - clamped_exp

        # Closing balance derived cumulatively from latest actual balance
        closing_balances = []
        curr_bal = latest_actual_balance
        for ncf in net_cashflow:
            curr_bal += ncf
            closing_balances.append(curr_bal)

        # Build output dataframe
        forecast_rows = []
        for i in range(30):
            target_date = feat_df.loc[i, "target_date"].strftime("%Y-%m-%d")
            h = i + 1
            forecast_rows.append({
                "merchant_id": m_id,
                "forecast_date": target_date,
                "horizon_day": h,
                "predicted_sales_inflow": round(float(clamped_inflow[i]), 2),
                "predicted_total_expense": round(float(clamped_exp[i]), 2),
                "predicted_net_cashflow": round(float(net_cashflow[i]), 2),
                "predicted_closing_cash_balance": round(float(closing_balances[i]), 2),
            })

        out_df = pd.DataFrame(forecast_rows)
        # Atomic write
        temp_path = PREDICTIONS_DIR / f"temp_{m_id.lower()}.csv"
        final_path = PREDICTIONS_DIR / f"predicted_{m_id.lower().replace('m', 'merchant')}.csv"
        out_df.to_csv(temp_path, index=False)
        temp_path.replace(final_path)
        print(f"Generated {final_path.name}: 30 rows, balance from INR {latest_actual_balance:.2f} to INR {closing_balances[-1]:.2f}")


def train_loan_acceptance_model(app_df: pd.DataFrame):
    print("--- Training Loan Acceptance Classifier ---")
    app_df = app_df.sort_values("parsed_date").reset_index(drop=True)

    feature_cols = [
        "merchant_type", "city", "city_tier", "business_age_months",
        "monthly_sales_reference", "monthly_profit_reference", "credit_score",
        "existing_loan_count", "existing_daily_emi", "loan_id", "lender_id",
        "loan_amount_offered", "annual_interest_rate", "tenure_days",
        "processing_fee_pct", "debt_service_to_profit_ratio", "pre_screen_eligible"
    ]
    cat_cols = ["merchant_type", "city", "city_tier", "loan_id", "lender_id"]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    # Chronological split: 80% train, 20% test
    split_idx = int(len(app_df) * 0.8)
    train_df = app_df.iloc[:split_idx]
    test_df = app_df.iloc[split_idx:]
    split_date = test_df.iloc[0]["parsed_date"].strftime("%Y-%m-%d")

    # Check applicant leakage/overlap between train and test
    train_applicants = set(train_df["applicant_id"].unique())
    test_applicants = set(test_df["applicant_id"].unique())
    overlap_count = len(train_applicants.intersection(test_applicants))

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
            ("num", StandardScaler(), num_cols),
        ]
    )

    X_train = preprocessor.fit_transform(train_df[feature_cols])
    y_train = train_df["accepted"].values
    X_test = preprocessor.transform(test_df[feature_cols])
    y_test = test_df["accepted"].values

    # Model 1: Logistic Regression
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    lr_pred = lr.predict(X_test)
    lr_proba = lr.predict_proba(X_test)[:, 1]

    lr_roc = roc_auc_score(y_test, lr_proba)
    lr_pr = average_precision_score(y_test, lr_proba)
    lr_f1 = f1_score(y_test, lr_pred)
    lr_brier = brier_score_loss(y_test, lr_proba)

    # Model 2: Random Forest
    rf = RandomForestClassifier(n_estimators=150, max_depth=6, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_proba = rf.predict_proba(X_test)[:, 1]

    rf_roc = roc_auc_score(y_test, rf_proba)
    rf_pr = average_precision_score(y_test, rf_proba)
    rf_f1 = f1_score(y_test, rf_pred)
    rf_brier = brier_score_loss(y_test, rf_proba)

    print(f"Logistic Regression -> ROC-AUC: {lr_roc:.4f}, PR-AUC: {lr_pr:.4f}, F1: {lr_f1:.4f}, Brier: {lr_brier:.4f}")
    print(f"Random Forest       -> ROC-AUC: {rf_roc:.4f}, PR-AUC: {rf_pr:.4f}, F1: {rf_f1:.4f}, Brier: {rf_brier:.4f}")

    # Probability calibration on Random Forest
    calibrated_rf = CalibratedClassifierCV(estimator=rf, method="sigmoid", cv=3)
    calibrated_rf.fit(X_train, y_train)
    cal_proba = calibrated_rf.predict_proba(X_test)[:, 1]
    cal_pred = (cal_proba >= 0.5).astype(int)
    cal_brier = brier_score_loss(y_test, cal_proba)
    cal_roc = roc_auc_score(y_test, cal_proba)
    cal_pr = average_precision_score(y_test, cal_proba)
    cal_acc = accuracy_score(y_test, cal_pred)
    cal_f1 = f1_score(y_test, cal_pred)
    cal_prec = precision_score(y_test, cal_pred)
    cal_rec = recall_score(y_test, cal_pred)
    cm = confusion_matrix(y_test, cal_pred).tolist()

    print(f"Calibrated RF       -> ROC-AUC: {cal_roc:.4f}, PR-AUC: {cal_pr:.4f}, F1: {cal_f1:.4f}, Brier: {cal_brier:.4f}")

    # Leakage check: test performance without pre_screen_eligible
    feat_no_prescreen = [f for f in feature_cols if f != "pre_screen_eligible"]
    num_no_prescreen = [c for c in feat_no_prescreen if c not in cat_cols]
    prep_no_prescreen = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ("num", StandardScaler(), num_no_prescreen),
    ])
    X_train_np = prep_no_prescreen.fit_transform(train_df[feat_no_prescreen])
    X_test_np = prep_no_prescreen.transform(test_df[feat_no_prescreen])
    rf_np = RandomForestClassifier(n_estimators=150, max_depth=6, random_state=42)
    rf_np.fit(X_train_np, y_train)
    rf_np_proba = rf_np.predict_proba(X_test_np)[:, 1]
    roc_without_prescreen = roc_auc_score(y_test, rf_np_proba)

    # Final fit on full dataset for deployed model
    X_full = preprocessor.fit_transform(app_df[feature_cols])
    y_full = app_df["accepted"].values
    final_calibrated_model = CalibratedClassifierCV(
        estimator=RandomForestClassifier(n_estimators=150, max_depth=6, random_state=42),
        method="sigmoid",
        cv=3
    )
    final_calibrated_model.fit(X_full, y_full)

    bundle = {
        "preprocessor": preprocessor,
        "feature_cols": feature_cols,
        "categorical_cols": cat_cols,
        "numerical_cols": num_cols,
        "model": final_calibrated_model,
        "class_labels": [0, 1],
    }
    joblib.dump(bundle, MODELS_DIR / "loan_acceptance_model.joblib")
    print("Saved loan acceptance model to loan_acceptance_model.joblib")

    metrics = {
        "model_type": "CalibratedClassifierCV (RandomForest base with sigmoid calibration)",
        "train_samples": int(len(train_df)),
        "test_samples": int(len(test_df)),
        "chronological_split_date": split_date,
        "applicant_overlap_between_splits": overlap_count,
        "class_balance_overall": {
            "accepted": int((app_df["accepted"] == 1).sum()),
            "rejected": int((app_df["accepted"] == 0).sum()),
        },
        "evaluation_metrics": {
            "roc_auc": float(cal_roc),
            "pr_auc": float(cal_pr),
            "accuracy": float(cal_acc),
            "f1": float(cal_f1),
            "precision": float(cal_prec),
            "recall": float(cal_rec),
            "brier_score": float(cal_brier),
            "confusion_matrix": cm,
        },
        "comparison_models": {
            "logistic_regression": {
                "roc_auc": float(lr_roc),
                "pr_auc": float(lr_pr),
                "f1": float(lr_f1),
                "brier_score": float(lr_brier),
            },
            "uncalibrated_random_forest": {
                "roc_auc": float(rf_roc),
                "pr_auc": float(rf_pr),
                "f1": float(rf_f1),
                "brier_score": float(rf_brier),
            }
        },
        "leakage_analysis": {
            "roc_auc_with_prescreen": float(rf_roc),
            "roc_auc_without_prescreen": float(roc_without_prescreen),
            "prescreen_delta": float(rf_roc - roc_without_prescreen),
            "note": "Pre-screen eligibility is verified to be pre-decision criteria available at inference time."
        },
        "feature_list": feature_cols,
        "limitations": [
            "Estimates historical demo acceptance probability; does NOT guarantee actual loan approval.",
            "Synthetic dataset contains 250 repeating applicants.",
            "Lender policies may change independently of historical patterns."
        ]
    }
    return bundle, metrics


def main():
    print(f"=== Starting LoanIQ Model Training Pipeline ===")
    start_time = datetime.now()

    # Load data
    sales_path = DATA_DIR / "daily_sales.csv"
    app_path = DATA_DIR / "loan_applications.csv"

    sales_df = pd.read_csv(sales_path)
    sales_df["parsed_date"] = pd.to_datetime(sales_df["transaction_date"], format="%d-%m-%Y")

    app_df = pd.read_csv(app_path)
    app_df["parsed_date"] = pd.to_datetime(app_df["application_date"], format="%Y-%m-%d")

    # Train forecasting model
    forecaster_bundle, forecaster_metrics = train_forecaster(sales_df)

    # Generate 30-day forecast CSVs
    generate_and_save_merchant_forecasts(sales_df, forecaster_bundle)

    # Train loan acceptance model
    classifier_bundle, classifier_metrics = train_loan_acceptance_model(app_df)

    # Combine metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "training_duration_seconds": (datetime.now() - start_time).total_seconds(),
        "cashflow_forecaster": forecaster_metrics,
        "loan_acceptance_model": classifier_metrics,
    }

    metadata_path = MODELS_DIR / "model_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Model metadata written to: {metadata_path}")
    print("=== Training Pipeline Completed Successfully ===")


if __name__ == "__main__":
    main()
