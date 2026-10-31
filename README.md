# LoanIQ --- AI-Powered Credit & Cash-Flow Advisory

LoanIQ is a full-stack, merchant-facing credit recommendation, cash-flow forecasting, debt optimization, and advisory platform designed for retail micro-enterprises.

---

## 1. Project Architecture & Directory Structure

```text
LoanIQ/
├── README.md
├── prompt.md
├── ANTIGRAVITY_PROMPT.md
├── .env.example
├── requirements.txt
├── pytest.ini
├── data_validation_report.txt
├── data/
│   ├── daily_sales.csv
│   ├── loan_applications.csv
│   ├── loan_products.json
│   ├── merchants.csv
│   ├── merchants_loans_completed.csv
│   └── merchants_loans_pending.csv
├── artifacts/
│   ├── models/
│   │   ├── cashflow_forecaster.joblib
│   │   ├── loan_acceptance_model.joblib
│   │   └── model_metadata.json
│   └── predictions/
│       ├── predicted_merchant001.csv
│       ├── predicted_merchant002.csv
│       ├── predicted_merchant003.csv
│       └── predicted_merchant004.csv
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas/
│   │   ├── merchant.py
│   │   ├── loan.py
│   │   ├── forecast.py
│   │   ├── agent.py
│   │   ├── translation.py
│   │   ├── voice.py
│   │   └── model_status.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── merchants.py
│   │   ├── loans.py
│   │   ├── assistant.py
│   │   ├── translation.py
│   │   └── system.py
│   ├── services/
│   │   ├── merchant_service.py
│   │   ├── forecasting.py
│   │   ├── acceptance_model.py
│   │   ├── recommendation.py
│   │   ├── loan_optimizer.py
│   │   ├── emi_calculator.py
│   │   ├── translation.py
│   │   ├── voice.py
│   │   └── agent_service.py
│   ├── mcp/
│   │   ├── server.py
│   │   └── tools.py
│   └── tests/
│       ├── conftest.py
│       ├── test_validation.py
│       ├── test_models.py
│       ├── test_financial_services.py
│       ├── test_api_endpoints.py
│       └── test_mcp_server.py
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── api.js
│       ├── auth.js
│       ├── i18n.js
│       ├── app.js
│       ├── dashboard.js
│       ├── loans.js
│       ├── forecast.js
│       ├── optimizer.js
│       └── assistant.js
└── scripts/
    ├── validate_data.py
    ├── train_models.py
    ├── evaluate_models.py
    └── generate_forecasts.py
```

---

## 2. Setup & Installation

### Step 1: Create Python Virtual Environment (Python 3.11+)

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

*Note: All core platform features (demo authentication, ML inference, forecasts, loan recommendations, comparisons, optimizer, and deterministic AI agent workflows) function without external API keys. Configure `OPENAI_API_KEY`, `SARVAM_API_KEY`, or `GOOGLE_TRANSLATE_API_KEY` only when external reasoning, speech, or cloud translation services are required.*

---

## 3. Data Validation, Model Training & Forecast Generation

### 1. Validate Datasets

```bash
python scripts/validate_data.py
```
Validates schemas, missing values, date ranges (2024-01-01 to 2026-10-31), balance continuity, and arithmetic consistency (`sales_inflow - total_expense == net_cashflow`).

### 2. Train ML Models & Generate Merchant Forecasts

```bash
python scripts/train_models.py
```
This single script:
- Trains the pooled horizon-aware cashflow forecaster (`HistGradientBoostingRegressor`).
- Trains the calibrated loan acceptance classifier (`CalibratedClassifierCV` with `RandomForestClassifier`).
- Generates 30-day forecast CSVs (`predicted_merchant001.csv` .. `predicted_merchant004.csv`).
- Saves `artifacts/models/model_metadata.json`.

### 3. Evaluate Models

```bash
python scripts/evaluate_models.py
```

### 4. Regenerate Forecasts (On Demand)

```bash
python scripts/generate_forecasts.py --merchant all
```

---

## 4. Run the Application

Start the integrated FastAPI backend and frontend service:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Frontend Application:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Demo Login Page:** [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login)
- **Interactive REST Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **MCP Server Endpoint:** [http://127.0.0.1:8000/mcp](http://127.0.0.1:8000/mcp)

---

## 5. Automated Tests & Quality Verification

Run the full pytest test suite:

```bash
pytest -v
```

### Verified Test Categories (25 Automated Tests Passing):
1. **Dataset Validation:** Checks all 6 files, 0 null values, 4 merchants, row counts, and date continuity.
2. **Forecast Leakage & Split:** Validates zero future leakage and chronological splits.
3. **Exact 30 Forecast Rows:** Verified 30 daily forecast rows for each merchant (`M001` through `M004`).
4. **Forecast Arithmetic:** Verified `predicted_net_cashflow == predicted_sales_inflow - predicted_total_expense`.
5. **Cumulative Balance:** Verified day-by-day balance continuity from latest actual closing balance.
6. **Acceptance Probability Bounds:** Calibrated probabilities strictly in $[0, 1]$.
7. **Product Eligibility:** Independent rule evaluation checking sales, age, credit score, amount, and tenure.
8. **Recommendation Multi-Factor Ranking:** Balances acceptance probability, interest APR, fees, and liquidity margin.
9. **EMI Reducing Balance Calculation:** Exact daily compounding formula verified against historical dataset.
10. **Merchant Isolation:** Strictly segregates profiles and loan histories between `M001`, `M002`, `M003`, and `M004`.
11. **MCP Security & Allowlisting:** Rejects unauthorized merchant IDs and non-allowlisted pages.
12. **MCP JSON-RPC 2.0 Transport:** Verified standard MCP protocol execution.
13. **Graceful Fallbacks:** Verifies that absent API keys default to English UI, text fallback, and deterministic agent workflows.

---

## 6. Model Metrics & Evaluation Comparison

### Model 1: Cash-Flow Forecaster (`HistGradientBoostingRegressor`)
- **Validation Period:** 2026-07-01 to 2026-09-30 (evaluating predictions up to 2026-10-31)
- **Training Samples:** 53,040 horizon-aware observations
- **Overall Inflow MAE:** ₹354.93 (vs Seasonal-Naive Baseline MAE: ₹579.67, **38.8% improvement**)
- **Overall Expense MAE:** ₹246.06 (vs Seasonal-Naive Baseline MAE: ₹399.06, **38.3% improvement**)
- **Horizon Breakdown:**
  - Horizons 1--3: Inflow MAE ₹350.49 | Expense MAE ₹254.94
  - Horizons 4--7: Inflow MAE ₹359.26 | Expense MAE ₹253.68
  - Horizons 8--15: Inflow MAE ₹358.29 | Expense MAE ₹249.25
  - Horizons 16--30: Inflow MAE ₹352.87 | Expense MAE ₹240.55
- **Limitations:** Trained on historical merchant transactions; macroeconomic shocks and prolonged unobserved store closures are not modeled.

### Model 2: Loan Acceptance Classifier (`CalibratedClassifierCV` + `RandomForest`)
- **Evaluation Period:** Chronological test split after 2026-04-21 (800 train, 200 test)
- **Test ROC-AUC:** 0.6055 (vs Logistic Regression: 0.5892)
- **Test PR-AUC:** 0.5732 (vs Logistic Regression: 0.5823)
- **Brier Score:** 0.2406 (Calibrated probabilities via sigmoid calibration)
- **Test Accuracy / F1:** 58.0% / 0.4940
- **Pre-screen Leakage Delta:** +0.0049 ROC-AUC with verified pre-decision pre-screen criteria.
- **Limitations:** Provides historical likelihood estimates based on demo records; does NOT constitute guaranteed loan sanction or credit bureau approval.

---

## 7. Model Context Protocol (MCP) Server

LoanIQ integrates a standard Model Context Protocol (MCP) server directly with FastAPI.

### Transport Modes:
1. **JSON-RPC 2.0:** `POST /mcp`
2. **REST Endpoints:** `GET /api/mcp/tools`, `POST /api/mcp/call`

### Registered MCP Tools (12 Tools):
1. `get_merchant_profile(merchant_id)`
2. `get_merchant_loans(merchant_id, status)`
3. `get_loan_products()`
4. `check_product_eligibility(merchant_id, loan_id, requested_amount, tenure_days)`
5. `predict_loan_acceptance(merchant_id, loan_id, requested_amount, tenure_days)`
6. `recommend_loans(merchant_id, requested_amount, max_daily_emi)`
7. `compare_loans(merchant_id, loan_ids)`
8. `get_cashflow_forecast(merchant_id, horizon_days)`
9. `simulate_loan(merchant_id, loan_amount, tenure_days, annual_interest_rate, processing_fee_pct)`
10. `optimize_existing_loans(merchant_id)`
11. `get_page_context(merchant_id, page_name, selected_ids)`
12. `navigate_ui(merchant_id, page, parameters)`

### Example MCP JSON-RPC Invocation:
```bash
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "recommend_loans",
      "arguments": {
        "merchant_id": "M001",
        "requested_amount": 100000,
        "max_daily_emi": 500
      }
    },
    "id": 1
  }'
```

---

## 8. AI Agent Subsystem

LoanIQ implements a mandatory AI Agent Subsystem structured into:
1. **Triage / Orchestrator:** Classifies intent into `LOAN_ACTION`, `COMPARISON_EXPLANATION`, `FINANCE_QA`, and `NAVIGATION`.
2. **Loan Action Workflow:** Extracts amounts, tenures, and EMI limits from natural language, calls backend recommendation tools, prepopulates UI forms, and returns automated navigation actions.
3. **Comparison & Explanation Workflow:** Grounds product comparison on authoritative backend data and on-screen context.
4. **Finance Q&A Workflow:** Explains financial concepts (Daily EMI, Reducing Balance, Prepayment Fees) using bounded definitions.
5. **OpenAI Provider Gateway:** When `OPENAI_API_KEY` is present, enables LLM reasoning. When absent, runs fully functional deterministic agent workflows with zero crashes.

---

## 9. Disclaimers

- **Synthetic Data Notice:** All merchant records, historical sales, loan applications, lenders, and product terms are synthetic artifacts created for evaluation.
- **Decision-Support Only:** Acceptance probability estimates and cash-flow projections are decision-support outputs; they do not represent real banking agreements or guaranteed disbursements.

