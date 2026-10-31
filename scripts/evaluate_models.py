"""
Model Evaluation and Verification Script for LoanIQ.
Loads artifacts/models/model_metadata.json, checks saved model bundles,
and outputs a clean, comprehensive evaluation report.
"""

import json
from pathlib import Path
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "artifacts" / "models"
PREDICTIONS_DIR = PROJECT_ROOT / "artifacts" / "predictions"


def evaluate():
    metadata_path = MODELS_DIR / "model_metadata.json"
    if not metadata_path.exists():
        print(f"Error: {metadata_path} does not exist. Run train_models.py first.")
        return

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    print("=" * 65)
    print("LOANIQ ML MODEL EVALUATION REPORT")
    print("=" * 65)
    print(f"Metadata Generated At: {meta.get('generated_at')}")
    print(f"Total Pipeline Training Time: {meta.get('training_duration_seconds', 0):.2f}s\n")

    # 1. Forecaster
    fc = meta.get("cashflow_forecaster", {})
    print("-" * 65)
    print("1. DAILY CASH-FLOW FORECASTER")
    print("-" * 65)
    print(f"Model Type: {fc.get('model_type')}")
    print(f"Train Samples: {fc.get('train_samples')}, Val Samples: {fc.get('validation_samples')}")
    print(f"Chronological Split Date: {fc.get('validation_split_date')}")
    print(f"Overall Inflow  -> MAE: {fc.get('inflow_mae', 0):.2f}, RMSE: {fc.get('inflow_rmse', 0):.2f}")
    print(f"Overall Expense -> MAE: {fc.get('expense_mae', 0):.2f}, RMSE: {fc.get('expense_rmse', 0):.2f}")

    base = fc.get("baseline_comparison", {})
    print("\nBaseline Comparison (Seasonal Naive):")
    print(f" - Inflow Seasonal Naive  -> MAE: {base.get('inflow_seasonal_naive_mae', 0):.2f}, RMSE: {base.get('inflow_seasonal_naive_rmse', 0):.2f}")
    print(f" - Expense Seasonal Naive -> MAE: {base.get('expense_seasonal_naive_mae', 0):.2f}, RMSE: {base.get('expense_seasonal_naive_rmse', 0):.2f}")

    print("\nMetrics by Forecast Horizon:")
    for h, h_m in fc.get("metrics_by_horizon", {}).items():
        print(f" - Horizon {h:5s} -> Inflow MAE: {h_m['inflow_mae']:.2f}, Expense MAE: {h_m['exp_mae']:.2f}")

    print("\nLimitations:")
    for lim in fc.get("limitations", []):
        print(f" * {lim}")

    # 2. Acceptance Classifier
    cl = meta.get("loan_acceptance_model", {})
    print("\n" + "-" * 65)
    print("2. LOAN ACCEPTANCE CLASSIFIER")
    print("-" * 65)
    print(f"Model Type: {cl.get('model_type')}")
    print(f"Train: {cl.get('train_samples')}, Test: {cl.get('test_samples')}")
    print(f"Chronological Split Date: {cl.get('chronological_split_date')}")
    print(f"Applicant Overlap Across Splits: {cl.get('applicant_overlap_between_splits')}")

    ev = cl.get("evaluation_metrics", {})
    print(f"\nEvaluation Metrics (Test Set):")
    print(f" - ROC-AUC:      {ev.get('roc_auc', 0):.4f}")
    print(f" - PR-AUC:       {ev.get('pr_auc', 0):.4f}")
    print(f" - Accuracy:     {ev.get('accuracy', 0):.4f}")
    print(f" - F1 Score:     {ev.get('f1', 0):.4f}")
    print(f" - Precision:    {ev.get('precision', 0):.4f}")
    print(f" - Recall:       {ev.get('recall', 0):.4f}")
    print(f" - Brier Score:  {ev.get('brier_score', 0):.4f} (Calibrated Probabilities)")
    print(f" - Confusion Matrix: {ev.get('confusion_matrix')}")

    comps = cl.get("comparison_models", {})
    print("\nModel Comparison on Test Set:")
    for m_name, m_stats in comps.items():
        print(f" - {m_name:26s} -> ROC-AUC: {m_stats['roc_auc']:.4f}, PR-AUC: {m_stats['pr_auc']:.4f}, F1: {m_stats['f1']:.4f}, Brier: {m_stats['brier_score']:.4f}")

    leak = cl.get("leakage_analysis", {})
    print(f"\nFeature Leakage Analysis (pre_screen_eligible):")
    print(f" - ROC-AUC with pre_screen:    {leak.get('roc_auc_with_prescreen', 0):.4f}")
    print(f" - ROC-AUC without pre_screen: {leak.get('roc_auc_without_prescreen', 0):.4f}")
    print(f" - Note: {leak.get('note')}")

    print("\nLimitations:")
    for lim in cl.get("limitations", []):
        print(f" * {lim}")

    # Check prediction files
    print("\n" + "-" * 65)
    print("3. VERIFYING MERCHANT PREDICTION CSVS")
    print("-" * 65)
    for m in ["merchant001", "merchant002", "merchant003", "merchant004"]:
        p_file = PREDICTIONS_DIR / f"predicted_{m}.csv"
        if p_file.exists():
            import pandas as pd
            df = pd.read_csv(p_file)
            print(f" * {p_file.name}: {len(df)} rows, columns: {list(df.columns)}")
        else:
            print(f" * ERROR: {p_file.name} missing!")
    print("=" * 65)


if __name__ == "__main__":
    evaluate()

