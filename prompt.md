# LoanIQ --- Complete Project Specification

## 1. Project objective

Build **LoanIQ**, a merchant-facing AI-powered credit recommendation,
advisory and loan-optimization application for a hackathon MVP.

LoanIQ helps merchants: - Discover loan products that fit their profile
and borrowing requirement. - Estimate the likelihood of historical
lender acceptance. - Compare eligible products using acceptance
probability, interest rate, fees, amount and tenure. - Forecast sales
inflow, business outflow, net cash flow and projected closing cash
balance for the next 3, 7, 15 or 30 days. - Optimize existing loan
repayments and evaluate additional borrowing using transparent rules. -
View merchant profile and active/completed loan details. - Interact
through a multilingual UI and conversational voice/text AI when the
required external API keys are configured.

The AI-agent subsystem is a COMPULSORY part of the LoanIQ architecture and implementation. It must be designed, implemented, integrated with the backend service layer, exposed through MCP tools, and included in the UI workflow from the beginning. Do not omit it, treat it as future work, or label the agents as optional.

The application must also remain usable when external API keys are absent. This is a graceful-degradation requirement, not a reason to omit the agent architecture:
- With an OpenAI API key, the conversational agent performs natural-language finance Q&A, intent understanding, tool selection, UI navigation instructions, form-prefill instructions and on-screen explanations.
- Without an OpenAI API key, the assistant/agent entry point must clearly report that LLM reasoning is unavailable, while the rest of the application remains fully functional. Deterministic navigation, forms, recommendations, comparisons, calculations and backend tools must still work through normal UI controls and REST/MCP service functions.
- With a Sarvam API key, voice STT/TTS is enabled. Without it, text interaction and all non-voice features remain usable.
- With a Google Translation API key, requested UI translations are generated and cached. Without it, the UI remains fully usable in English and clearly indicates that translation is unavailable.

The AI-agent architecture and its tool contracts are mandatory deliverables. External API execution is credential-dependent; core financial computation and navigation must never depend on an LLM response.

This is a demo using synthetic/fictional data. Do not represent
predictions as actual lender decisions, real Paytm offers, credit bureau
decisions or regulatory approval.

## 2. Mandatory technology stack

### Backend

-   Python 3.11+
-   FastAPI
-   Pydantic
-   pandas, NumPy
-   scikit-learn
-   joblib
-   SQLite for lightweight application state, cached translations and
    audit/demo interaction records
-   Python MCP SDK (Model Context Protocol) integrated with the FastAPI
    service, exposing an MCP endpoint (prefer Streamable HTTP if
    supported by the installed SDK)
-   Uvicorn

### Frontend

-   HTML5
-   CSS3
-   Vanilla JavaScript (ES modules where useful)
-   Chart.js for charts
-   Fetch API for backend calls
-   Responsive desktop and mobile layouts

Do not use React, Next.js, Flutter or a frontend framework. The required
frontend is HTML/CSS/JavaScript.

### External API integrations (required integration points; credential-dependent runtime)

-   OpenAI API: conversational finance assistant, natural-language
    intent parsing, tool orchestration and on-screen explanations.
-   Sarvam AI: speech-to-text (STT) and text-to-speech (TTS) for
    supported Indian languages.
-   Google Cloud Translation API: UI translation.
-   Implement all three integration adapters and their configuration/status handling. API calls are made only when the corresponding key is configured. Missing keys must trigger graceful degradation, never application startup failure.

## 3. Dataset inventory and verified schemas

Use the uploaded files as the source of truth. Do not invent replacement
columns or silently change their meaning.

### 3.1 `daily_sales.csv`

Verified columns: - `transaction_id` - `merchant_id` -
`transaction_date` - `sales_inflow` - `total_expense` - `net_cashflow` -
`closing_cash_balance`

Verified data: - 4,140 rows. - Four merchants: M001, M002, M003, M004. -
1,035 daily records per merchant. - Date range: 2024-01-01 through
2026-10-31. - No missing values in the inspected columns.

Note: the dataset spans approximately 34 months, not exactly 24 months.
Use all valid available history by default. Do not truncate to two years
unless an explicit configuration is added.

Interpretation: - `sales_inflow`: daily business inflow/sales. -
`total_expense`: daily business outflow. - `net_cashflow`: daily net
cash flow. Validate whether it equals inflow minus expense. -
`closing_cash_balance`: historical end-of-day balance. Validate
continuity and do not forecast it independently if it can be derived
from forecast net cash flow and the latest known balance.

### 3.2 `loan_applications.csv`

Verified columns: - `application_id` - `application_date` -
`applicant_id` - `business_name` - `merchant_type` - `city` -
`city_tier` - `business_age_months` - `monthly_sales_reference` -
`monthly_profit_reference` - `credit_score` - `existing_loan_count` -
`existing_daily_emi` - `loan_id` - `lender_id` - `loan_amount_offered` -
`annual_interest_rate` - `tenure_days` - `processing_fee_pct` -
`debt_service_to_profit_ratio` - `pre_screen_eligible` - `accepted`

Verified data: - 1,000 rows. - 469 accepted (1) and 531 rejected (0). -
No missing values in the inspected columns.

Target: - `accepted` (binary 0/1).

Feature rules: - Use only information available at application decision
time. - Exclude identifiers and free-text names from model features:
`application_id`, `applicant_id`, `business_name`. - `loan_id` and
`lender_id` can be encoded as categorical features because
product/lender differences matter. - `pre_screen_eligible` may be used
only if it is known before the acceptance outcome and is genuinely
available at inference time. Document this assumption and compare model
performance with and without it to detect leakage. - Do not use
post-decision fields or target-derived transformations. - Do not treat
`accepted` as an eligibility label. - Use chronological splitting by
`application_date`, not random splitting, for final evaluation. If
repeated applicant identities cause leakage, group or otherwise account
for repeated applicants in evaluation. - Report class balance, ROC-AUC,
PR-AUC, precision, recall, F1, confusion matrix, Brier score and
calibration where possible. - Compare at least Logistic Regression and
Random Forest. Select based on validation metrics, calibration and
stability, not training accuracy. - Calibrate predicted probabilities
when the validation data supports calibration. - Persist the fitted
preprocessing pipeline and model with joblib.

The result is a **historical acceptance probability estimate**, not a
guaranteed lender decision or a real credit score.

### 3.3 `loan_products.json`

Contains 15 fictional products under the `products` key. Product fields
include: - `loan_id`, `lender_id`, `lender_name`, `product_name` -
`min_amount`, `max_amount` - `annual_interest_rate` - `min_tenure_days`,
`max_tenure_days` - `processing_fee_pct`, `prepayment_fee_pct` -
`min_monthly_sales` - `min_business_age_months` - `min_credit_score` -
`disclaimer`

Use the product data dynamically. Never hardcode only one or two
products. Preserve each product's disclaimer and display a visible
demo-data disclaimer in the UI.

### 3.4 `merchants.csv`

Verified columns: - `merchant_id` - `business_name` - `merchant_type` -
`city` - `city_tier` - `business_age_months` -
`monthly_sales_reference` - `monthly_profit_reference` -
`credit_score` - `opening_cash_balance` - `preferred_language` -
`existing_loan_count` - `existing_daily_emi` - `completed_loan_count`

Contains exactly four merchants. Use merchant ID-only demo login. Valid
IDs must be loaded from this file; do not hardcode a separate list that
can drift from the data.

### 3.5 `merchants_loans_completed.csv`

Contains completed loan account records, including: - Loan account,
merchant and product IDs - Disbursement, contractual end and snapshot
dates - Principal, interest rate, tenure and daily EMI - Installments
paid, amount paid, interest paid, principal repaid - Remaining
principal, remaining tenure, next due date, next daily EMI and loan
status

Use this file to display historical completed loans and derive repayment
history summaries. Missing `next_due_date` values are expected for
completed loans and must not be treated as an error.

### 3.6 `merchants_loans_pending.csv`

Contains active/pending loan account records with the same general
loan-account structure. Use it for current obligations and optimization.
Treat `snapshot_date` as the reference date for the snapshot. Do not
assume that every loan has identical repayment terms.

## 4. Application architecture

Use a modular structure similar to:

``` text
LoanIQ/
├── README.md
├── prompt.md
├── ANTIGRAVITY_PROMPT.md
├── .env.example
├── requirements.txt
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
│   ├── routers/
│   ├── services/
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
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── api.js
│   │   ├── auth.js
│   │   ├── dashboard.js
│   │   ├── loans.js
│   │   ├── forecast.js
│   │   ├── optimizer.js
│   │   ├── assistant.js
│   │   └── i18n.js
│   └── assets/
└── scripts/
    ├── validate_data.py
    ├── train_models.py
    ├── generate_forecasts.py
    └── evaluate_models.py
```

The exact structure may be adjusted if the implementation remains
modular and understandable. Do not place all backend logic in one file.

## 5. Model 1 --- Daily sales and cash-flow forecasting

### Objective

For a selected merchant, forecast every day from day 1 through day 30
for: 1. Sales inflow. 2. Total expense/outflow. 3. Net cash flow. 4.
Projected closing cash balance.

The UI must allow 3, 7, 15 and 30-day selections. These are views over
the same 30-day forecast, not four unrelated models.

### Recommended approach

Use a pooled/global tabular time-series regression approach across the
four merchants. A global model can learn shared weekday and seasonal
patterns while merchant ID and merchant-specific lag/rolling features
preserve differences between merchants.

Implement a supervised horizon-aware direct forecasting dataset: - Each
training sample uses only observations available up to forecast origin
date `t`. - Create samples for target horizons 1 to 30. - Include
`horizon` as a feature. - Train separate regressors for `sales_inflow`
and `total_expense`, or use a validated multi-output approach. -
Generate all 30 daily values from the latest available date by
requesting horizons 1 through 30. - Do not use future observations to
create lag or rolling features.

Features should include, where available: - Merchant ID (categorical
encoding). - Lag 1, 2, 3, 7, 14, 28 days for inflow and expense. -
Rolling mean and standard deviation over 7, 14 and 28 days, shifted so
the current target is not included. - Day of week, day of month, month,
weekend flag. - Horizon (1--30). - Recent net cash flow and relevant
historical balance features. - Calendar seasonality features that can be
derived without future leakage.

For a hackathon MVP, compare a simple baseline (last value / same
weekday last week / rolling average) with a scikit-learn model such as
HistGradientBoostingRegressor or RandomForestRegressor. Choose the model
based on chronological validation performance. Do not assume a complex
model is better.

### Evaluation

-   Use chronological validation and test windows.
-   Do not randomly shuffle time-series rows.
-   Report MAE and RMSE separately for inflow and expense.
-   Report errors by forecast horizon (1--3, 4--7, 8--15, 16--30).
-   Compare with a seasonal-naive baseline.
-   Save evaluation metrics and training date range in model metadata.

### Derived calculations

For each forecast date: -
`predicted_net_cashflow = predicted_sales_inflow - predicted_total_expense`. -
`predicted_closing_cash_balance = previous_closing_cash_balance + predicted_net_cashflow`. -
Carry each day's predicted closing balance forward to the next date. -
Clamp or flag physically impossible negative inflow/expense predictions;
document the chosen handling. Avoid silently hiding negative projected
cash balance because it may be an important financial warning.

### Prediction file format

Generate one CSV per merchant, with 30 rows: - `merchant_id` -
`forecast_date` - `horizon_day` - `predicted_sales_inflow` -
`predicted_total_expense` - `predicted_net_cashflow` -
`predicted_closing_cash_balance` - Optional lower/upper uncertainty
estimates if actually calculated and validated.

File names: - `predicted_merchant001.csv` for M001 -
`predicted_merchant002.csv` for M002 - `predicted_merchant003.csv` for
M003 - `predicted_merchant004.csv` for M004

Write files atomically so a failed run does not leave a partially
written prediction file. Generate on training/startup or via an explicit
refresh endpoint/command. The API must be able to regenerate forecasts
on demand.

### Forecast UI

-   Horizon selector: 3, 7, 15, 30 days.
-   Line chart with actual historical data and forecast values.
-   Allow toggling inflow, outflow, net cash flow and projected closing
    balance.
-   Show forecast totals and averages for the selected horizon.
-   Show a warning when projected cash balance becomes negative or
    unusually low.
-   Show the forecast generation timestamp and explain that forecasts
    are estimates.
-   Do not display only a single aggregate number; show the daily graph.

## 6. Model 2 --- Loan acceptance probability

### Objective

For a merchant and a product, estimate the probability that an
application with the relevant attributes would be accepted based on
historical application data.

### Inference construction

At recommendation time, combine: - Merchant profile fields from
`merchants.csv`. - Candidate loan product fields from
`loan_products.json`. - Existing loan obligations from pending loan
records. - Sales/profit references and calculated financial indicators.

Construct the inference row using the same feature names and
transformations used during training. Map candidate product attributes
to application feature names: - product `loan_id` -\> application
`loan_id` - product `lender_id` -\> application `lender_id` - merchant
`business_age_months` -\> same application feature - merchant
`monthly_sales_reference` -\> same application feature - merchant
`monthly_profit_reference` -\> same application feature - merchant
`credit_score` -\> same application feature - merchant
`existing_loan_count` -\> same application feature - merchant
`existing_daily_emi` -\> same application feature - product
`loan_amount_offered` -\> `loan_amount_offered` - product
`annual_interest_rate` -\> same application feature - product tenure
choice -\> `tenure_days` - product processing fee -\>
`processing_fee_pct` - derive `debt_service_to_profit_ratio`
consistently and document the formula - derive `pre_screen_eligible`
using the product's explicit minimum requirements, if this feature is
used by the trained model.

Where city, city tier or merchant type are available, map them from the
merchant profile. Never fabricate missing values. The model pipeline
must handle categorical features consistently.

### Product eligibility is a separate rule

Before ranking: - Check requested loan amount against product min/max. -
Check monthly sales against product minimum. - Check business age
against product minimum. - Check credit score against product minimum. -
Check selected tenure against product min/max. - Mark each failed
condition with a human-readable reason. - Do not call an ineligible
product eligible just because its model probability is high.

### Recommendation ranking

Recommend products that pass explicit product rules, then rank with
transparent multi-factor logic: - Predicted acceptance probability. -
Annual interest rate. - Processing fee and prepayment fee. - Requested
amount/tenure compatibility. - Affordability based on forecast cash flow
and existing daily EMI.

Do not rank solely by acceptance probability or solely by interest rate.
Expose the factors and reason for the ranking. Allow a user to inspect
all products, including ineligible products and their reasons.

### Model safeguards

-   Probability must be returned as 0--1 and formatted as a percentage
    in the UI.
-   Do not call the probability "approval guarantee".
-   Display "Estimated acceptance probability based on demo historical
    data".
-   If model artifacts are missing, use a clearly labelled fallback
    heuristic only if explicitly implemented; do not silently pretend
    the model is trained.
-   Include a `/api/model/status` endpoint showing model type, trained
    timestamp, metrics and whether a fallback is active.

## 7. Loan recommendation and comparison

Main dashboard: - Show the top eligible recommended loan products for
the logged-in merchant. - Show lender, product, amount range, interest
rate, processing fee, tenure range, estimated acceptance probability and
eligibility status. - Show why each product is recommended. - Provide a
"View all offers" or equivalent action. - Do not imply that the user can
submit an actual lender application; lender APIs are not supplied.

Comparison page: - Compare all 15 products or a selected subset. - Show
amount, interest, tenure, processing fee, prepayment fee, eligibility,
estimated acceptance probability and affordability. - Clearly identify
the lowest-interest product, highest predicted acceptance probability
among eligible products, and best overall fit according to the
transparent ranking logic. - Use an EMI calculator consistent with the
product's repayment convention. If daily EMI is used, state the
calculation assumptions. - Include a detailed cost estimate with
principal, interest and processing fee. Do not compare products using
annual interest rate alone.

## 8. Loan optimization --- rule-based engine

Use `merchants_loans_pending.csv` and `merchants_loans_completed.csv`.

### Active loan dashboard

Display: - Total outstanding principal. - Combined daily EMI. - Active
loan count. - Remaining tenure for each active loan. - Next due date and
next daily EMI. - Completed loan history and amount repaid.

### Optimization rules

Implement transparent deterministic rules: 1. Aggregate active daily
EMIs for the merchant. 2. Compare existing daily EMI with recent and
forecast net cash flow. 3. Calculate daily cash available after business
expenses and existing EMIs. 4. Simulate an additional loan at a selected
amount, rate and tenure. 5. Compare the projected post-loan cash
position with the baseline. 6. Identify dates where projected closing
balance becomes negative or falls below a configurable safety buffer. 7.
Evaluate whether prepayment is allowed and account for the product's
prepayment fee. 8. Compare total cost and cash-flow pressure across
scenarios. 9. Suggest a lower amount or longer tenure if the requested
scenario is not affordable. 10. Never recommend taking another loan
merely because the merchant is technically eligible.

Make all thresholds configurable and document them. Label outputs as
decision-support estimates, not financial advice.

### Loan simulator

Inputs: - Desired loan amount. - Tenure. - Product/lender (optional). -
Optional daily EMI affordability limit. Outputs: - Estimated EMI under a
clearly stated calculation method. - Total repayment. - Estimated
interest. - Processing fee. - Total estimated cost. - Forecast cash-flow
impact. - Affordability status and reason. - Alternative scenarios.

Use consistent rounding and currency formatting (INR).

## 9. Merchant profile and login

### Login

-   Login form accepts only a merchant ID.
-   Validate against merchant IDs loaded from `merchants.csv`.
-   No password or OTP in this MVP.
-   Store the active merchant ID in sessionStorage or another simple
    browser session mechanism.
-   Provide a visible logout button.
-   On logout, clear the active session and return to login.
-   Protect merchant-specific API routes by requiring a valid demo
    merchant ID/session header or equivalent.
-   Clearly label this as demo authentication, not secure production
    authentication.

### Profile

Show relevant fields from `merchants.csv`: - Business name - Merchant
ID - Merchant type - City and city tier - Business age - Monthly sales
reference - Monthly profit reference - Credit score (demo data) -
Preferred language - Existing loan count - Existing daily EMI -
Completed loan count

Never expose another merchant's data after a merchant switches or logs
out.

## 10. Frontend pages and navigation

Use Paytm-inspired visual styling: - Primary blue: approximately
`#00B9F1` / `#00BAF2`. - Dark navy: approximately `#002970`. -
White/light backgrounds, pale blue panels, restrained green for positive
indicators and red/amber for warnings. - Use a clean financial dashboard
layout, clear typography, rounded cards, subtle shadows and accessible
contrast. - Do not use Paytm logos or claim the app is an official Paytm
product. Use LoanIQ branding and a note that it is a hackathon demo.

Required pages/sections: 1. Merchant login. 2. Main dashboard: -
Merchant greeting/profile summary. - Recommended eligible loans. -
Sales/cash-flow forecast preview. - Active loan summary. - Quick actions
for compare, optimize and assistant. 3. Loan recommendations. 4. Compare
loans. 5. Forecast analytics. 6. Loan optimizer/simulator. 7. Profile
and loan history. 8. Conversational assistant panel/page.

All navigation must work. Do not build static mockup-only buttons. Every
visible action must call a real frontend handler and backend endpoint or
be clearly disabled with an explanation.

## 11. Multilingual UI translation

### Requirement

Translate visible UI labels, buttons, navigation, headings, helper text
and static messages into a selected language using Google Cloud
Translation API.

-   Default language: English.
-   Initial language options should include English, Hindi and Marathi;
    make the list configurable.
-   Use the merchant's `preferred_language` as the initial preference
    when supported.
-   Translate only UI strings, not IDs, amounts, product IDs, merchant
    IDs, dates, API keys or arbitrary data values.
-   Keep a stable translation key for every UI string.
-   Cache each translated key/value by source language, target language
    and source text/hash in SQLite or a persistent JSON cache.
-   Reuse cached translations on later visits.
-   If the API key is missing, English must work normally. Show a clear
    "translation unavailable" state rather than breaking the UI.
-   Do not repeatedly call the translation API for already cached
    strings.
-   Add a language selector and persist the selection for the
    merchant/session.

Environment variable: `GOOGLE_TRANSLATE_API_KEY`

## 12. Mandatory AI-agent subsystem, conversational AI and voice

### Availability

The conversational AI-agent subsystem is a mandatory architectural component. Implement its orchestrator, intent schemas, tool registry, context manager, service adapters, MCP integration, API routes and frontend interaction even when no API key is present. OpenAI-powered reasoning calls require `OPENAI_API_KEY`; absence of that key disables only LLM reasoning, not the agent subsystem's deterministic tools or the rest of LoanIQ.

Environment variables: - `OPENAI_API_KEY` - `OPENAI_MODEL`
(configurable) - `SARVAM_API_KEY` - `GOOGLE_TRANSLATE_API_KEY`

When OpenAI is unavailable: - Keep the rest of the application fully
functional. - The assistant UI should clearly say that AI assistant
features require configuration. - Do not return fabricated LLM
responses. - Deterministic non-LLM actions such as EMI calculation,
product filtering and loan comparison remain available through ordinary
APIs.

### Sarvam STT/TTS

-   Use Sarvam's current documented API endpoints and request formats.
-   Do not guess endpoint URLs or payload formats.
-   Read API keys from environment variables only.
-   STT: convert merchant speech into text.
-   TTS: convert assistant response text into audio in the selected
    supported language.
-   Handle unsupported language, quota, network and missing-key errors
    gracefully.
-   Voice input must have a text input fallback.

### Conversational agent: three core capabilities

#### A. General finance questions

Examples: - "What is daily EMI?" - "What is the difference between
interest and processing fee?" - "How does prepayment work?" - "How much
loan should a small business take?"

The agent should answer using a bounded finance knowledge context and
the current app's product/loan information when relevant. It must
distinguish general educational information from personalized
calculations.

#### B. Natural language to actions, forms and navigation

Example: "I need a ₹5 lakh loan and I can afford ₹2,000 daily EMI."

Expected flow: 1. Parse amount and daily EMI limit. 2. Ask for missing
information if needed (for example, tenure or purpose). 3. Call
deterministic backend tools to filter products and simulate
affordability. 4. Populate the loan requirement form with extracted
values. 5. Navigate to the loan recommendation page. 6. Show the
filtered recommendations and explain the assumptions. 7. Ask for
confirmation before any consequential action. The MVP does not submit
real loan applications.

Do not implement arbitrary natural-language-to-SQL execution. Use
structured intent extraction and predefined, parameterized backend
functions. If read-only SQL is needed internally, enforce table/column
allowlists and parameterized queries. Never expose raw SQL execution to
the LLM.

#### C. Loan comparison and on-screen explanation

Examples: - "Compare all loans." - "Which loan is better for me?" -
"Explain this loan on screen." - "Compare these two loans on screen."

Expected flow: 1. Identify the requested page or visible loan/product
IDs. 2. Fetch authoritative details from backend APIs. 3. Navigate to
the comparison page when requested. 4. Compare eligibility, acceptance
estimate, interest, fees, tenure, EMI and cash-flow affordability. 5.
Explain the result with explicit factors and caveats.

On-screen explanation must use structured page context supplied by the
frontend, not screenshots or arbitrary browser scraping. The frontend
should send the visible page name, selected product IDs and relevant
displayed data to the backend. The backend should verify/fetch
authoritative data before the LLM explains it.

## 13. MCP server

Implement an MCP server integrated with FastAPI. Expose documented tools
for the assistant and external MCP clients.

Required tools: - `get_merchant_profile(merchant_id)` -
`get_merchant_loans(merchant_id, status)` - `get_loan_products()` -
`check_product_eligibility(merchant_id, loan_id, requested_amount, tenure_days)` -
`predict_loan_acceptance(merchant_id, loan_id, requested_amount, tenure_days)` -
`recommend_loans(merchant_id, requested_amount, max_daily_emi)` -
`compare_loans(merchant_id, loan_ids)` -
`get_cashflow_forecast(merchant_id, horizon_days)` -
`simulate_loan(merchant_id, loan_amount, tenure_days, annual_interest_rate, processing_fee_pct)` -
`optimize_existing_loans(merchant_id)` -
`get_page_context(merchant_id, page_name, selected_ids)` (return
structured, authorized page data) -
`navigate_ui(merchant_id, page, parameters)` (return a validated
navigation action for the frontend to execute)

Security and correctness: - Validate merchant ID on every tool. - Do not
allow one merchant to query another merchant's private data through the
tool layer. - Validate page names against a fixed allowlist. - Validate
navigation parameters with Pydantic schemas. - The MCP server must call
the same backend service layer as REST endpoints; do not duplicate
business logic. - Do not let the LLM invent product terms or execute
arbitrary SQL. - Log tool name, merchant ID, timestamp and outcome
without logging API keys or sensitive secrets. - Document MCP endpoint,
transport and example tool calls in README.

## 13. Backend architecture and request flow

Build the backend around shared domain services. REST routes, MCP tools and AI-agent tools must all call the same service functions; do not create separate implementations of loan calculations or recommendation logic.

Recommended request flow:

```text
HTML/CSS/JavaScript UI
   |
   +--> REST API ------------------------------+
   |                                           |
   +--> Agent API --> Agent Orchestrator       |
   |                    |                      |
   |                    +--> Intent/Workflow   |
   |                    +--> Tool Registry ----+--> Shared Domain Services
   |                    +--> Context Manager   |       |
   |                    +--> OpenAI Adapter    |       +--> Forecasting Model
   |                                           |       +--> Acceptance Model
   +--> MCP Client --> FastAPI MCP Server -----+       +--> Eligibility Rules
                                                           +--> Loan Optimizer
                                                           +--> Loan/EMI Calculator
                                                           +--> Merchant/Data Repositories

Google Translation Adapter --> Translation Cache (SQLite)
Sarvam STT/TTS Adapter ------> Voice endpoints
```

Mandatory backend layers:
- **API layer:** FastAPI routers, request validation, response schemas, authentication/session checks.
- **Agent layer:** orchestrator, intent classification/schema, specialized workflows, context manager, tool registry and provider adapters.
- **MCP layer:** MCP server exposing the same typed domain tools to MCP clients and the agent.
- **Domain/service layer:** forecasting, acceptance prediction, recommendation, eligibility, comparison, loan optimization, EMI/cost calculation, merchant profile and loan history.
- **Data layer:** CSV/JSON repositories for supplied demo datasets, model artifact loader, prediction-file repository and SQLite cache/state.
- **Integration layer:** OpenAI, Sarvam and Google Translation adapters with key detection, timeouts, retries where safe, and structured error states.

Do not let an LLM directly read arbitrary files, execute arbitrary SQL, alter source datasets, invent loan terms, or calculate authoritative EMI/fees. The LLM may interpret intent and request tools; deterministic services must return financial values. The frontend must validate and execute only allowlisted navigation actions returned by the backend.

The application must expose integration health/status so the UI can distinguish:
- Agent subsystem implemented and available.
- OpenAI reasoning configured/unconfigured.
- Sarvam voice configured/unconfigured.
- Google translation configured/unconfigured.
- MCP server running/not running.

Renumber the following sections as needed.

## 14. REST API contracts

Use a consistent `/api` prefix and Pydantic request/response models.

Suggested endpoints: - `GET /api/health` - `GET /api/model/status` -
`POST /api/auth/login` --- accepts merchant ID only for demo login. -
`POST /api/auth/logout` - `GET /api/merchants/{merchant_id}/profile` -
`GET /api/merchants/{merchant_id}/loans?status=active|completed|all` -
`GET /api/merchants/{merchant_id}/recommendations` -
`POST /api/merchants/{merchant_id}/recommendations` -
`GET /api/loan-products` - `POST /api/loans/compare` -
`POST /api/loans/eligibility` -
`POST /api/loans/acceptance-probability` -
`GET /api/merchants/{merchant_id}/forecast?horizon=30` -
`POST /api/merchants/{merchant_id}/forecast/refresh` -
`POST /api/loans/simulate` -
`GET /api/merchants/{merchant_id}/optimization` -
`POST /api/translation/translate` - `POST /api/assistant/chat` -
`POST /api/assistant/stt` - `POST /api/assistant/tts`

Adapt routes if needed, but keep API documentation accurate and frontend
integration complete. Validate all user inputs and return useful HTTP
errors.

## 15. API-key-free operation and fallback policy

The following must work without any external API key: - Merchant-ID demo
login/logout. - Merchant profile. - Active/completed loan details. -
Loan product listing. - Rule-based eligibility. - ML model training and
inference using local datasets and local Python libraries. - Loan
recommendations using model probability plus deterministic rules. - Loan
comparison. - EMI and total-cost calculations. - Cash-flow model
training, forecast generation and CSV persistence. - Forecast graphs. -
Rule-based loan optimization and simulator. - Normal page navigation and
forms.

The following require external keys: - Google UI translation. - OpenAI
conversational/agentic reasoning and intent extraction. - Sarvam
STT/TTS.

The UI must show the configuration status of each required external integration. Missing API keys must not prevent FastAPI from starting or core pages from loading.

## 16. Configuration

Create `.env.example`:

``` env
OPENAI_API_KEY=
OPENAI_MODEL=
SARVAM_API_KEY=
GOOGLE_TRANSLATE_API_KEY=
DATABASE_URL=sqlite:///./loaniq.db
DATA_DIR=./data
ARTIFACTS_DIR=./artifacts
FORECAST_SAFETY_BUFFER=5000
```

Never commit `.env`. Never expose secret values in API responses or
frontend JavaScript.

## 17. Training and startup workflow

Create scripts: - `scripts/validate_data.py` -
`scripts/train_models.py` - `scripts/evaluate_models.py` -
`scripts/generate_forecasts.py`

Workflow: 1. Validate required files, columns, types, merchant IDs, date
continuity and duplicates. 2. Validate business arithmetic
(`net_cashflow` against inflow minus expense) and cash-balance
continuity. Report discrepancies; do not silently rewrite source data.
3. Train acceptance model and evaluate it using chronological splits. 4.
Train forecasting models and compare to naive baselines using
chronological splits. 5. Save model artifacts and metadata. 6. Generate
30-day forecasts for M001--M004. 7. Save predictions in the required CSV
files. 8. Start FastAPI. 9. On startup, check artifacts and data. If
missing, show a clear error or run an explicitly configured training
workflow. Do not silently substitute fake model predictions.

Provide a simple one-command setup and run process in README.

## 18. Testing requirements

Add automated tests for: - Data loading and schema validation. - Date
parsing and merchant filtering. - No time-series leakage in feature
generation. - Chronological train/validation/test split. - Forecast
output has exactly 30 daily rows per merchant. - Predicted net cash flow
equals predicted inflow minus predicted expense. - Projected closing
balance is cumulative from the last actual balance. - Prediction CSVs
are readable and correctly named. - Acceptance model returns a valid
probability in \[0, 1\]. - Product eligibility checks each
minimum/maximum condition. - Ineligible products are not shown as
eligible. - Recommendation ranking is deterministic for identical
inputs. - Loan calculations and fee calculations. - Existing loan
aggregation. - Optimization warning for negative/low cash balance. -
Merchant isolation between M001--M004. - Missing API keys do not break
core functionality. - Translation caching avoids repeated API calls. -
MCP tools validate inputs and call the same service layer. - UI login,
logout, navigation, horizon selection and chart rendering.

Use synthetic test fixtures only when necessary; do not replace the
supplied project datasets.

## 19. Demo and explainability requirements

The application should make it easy to demonstrate: 1. Login as M001,
M002, M003 or M004. 2. View profile and current loans. 3. See
recommended eligible products and acceptance estimates. 4. Compare loan
products. 5. Open forecast analytics and switch between 3, 7, 15 and 30
days. 6. View the daily inflow/outflow/net cash-flow/balance graph. 7.
Simulate a new loan against projected cash flow. 8. Optimize active
loans. 9. Use the assistant to request a loan amount and EMI limit, then
navigate to populated recommendations. 10. Ask the assistant to compare
products or explain the current screen. 11. Switch UI language when
Google Translation is configured. 12. Use voice input/output when Sarvam
is configured.

Display model metrics and a concise "How this recommendation was
generated" explanation. Clearly distinguish: - Product-rule
eligibility. - Historical model-estimated acceptance probability. -
Cash-flow affordability. - Final ranking score.

## 20. Non-negotiable implementation rules

-   Build a working full-stack application, not just a design prototype.
-   Inspect the supplied datasets before coding.
-   Preserve original source data.
-   Do not invent real Paytm or lender APIs.
-   Do not claim real loan approval or disbursement.
-   Do not make LLM calls necessary for core product functionality.
-   Do not use arbitrary LLM-generated SQL.
-   Do not let the LLM calculate authoritative financial values when
    deterministic backend functions can calculate them.
-   Keep secrets on the backend.
-   Use clear errors and loading states.
-   All visible controls must work.
-   Include README setup instructions, `.env.example`, requirements,
    model training commands, test commands and API/MCP documentation.
-   Finish by running tests and fixing errors. Report any feature that
    could not be completed rather than claiming it works.
