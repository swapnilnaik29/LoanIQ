# Antigravity Execution Prompt --- Build LoanIQ

You are the lead full-stack Python, ML and AI-agent engineer
implementing LoanIQ.

## First instruction: read the specification

Before writing code, read the complete `prompt.md` in the project root.
Treat it as the authoritative product and technical specification. Also
inspect all six supplied files in `data/` (or their current
uploaded/project locations):

-   `daily_sales.csv`
-   `loan_applications.csv`
-   `loan_products.json`
-   `merchants.csv`
-   `merchants_loans_completed.csv`
-   `merchants_loans_pending.csv`

Do not start by generating a generic dashboard. First inspect schemas,
data quality, date ranges, merchant IDs, class balance, product fields
and loan records. The source datasets contain four merchants and
fictional loan products for an MVP. Preserve their values and
disclaimers.

## Required deliverable

Build a complete, runnable LoanIQ application using: - FastAPI backend
and an MCP server integrated with FastAPI. - Python ML
training/inference using pandas, NumPy and scikit-learn. - HTML, CSS and
vanilla JavaScript frontend. - Chart.js for forecast visualizations. -
SQLite for translation cache and lightweight app state. - Mandatory
AI-agent subsystem (orchestrator, specialized workflows, tool registry,
conversation context manager and provider adapters). - OpenAI, Sarvam
and Google Cloud Translation adapters, which must all be implemented;
external API execution depends on credentials.

Do not use React, Next.js or Flutter. Do not create a static-only UI.

**Critical distinction:** AI agents are NOT optional project features. The complete agent architecture and integration must be implemented. API keys only control whether external LLM/translation/voice services can execute. The app must degrade gracefully without keys; it must not omit the agent layer or make core financial features dependent on it.

## Execution plan

### Phase 1 --- Inspect and validate data

1.  Inspect all six datasets and confirm the actual schemas.
2.  Implement `scripts/validate_data.py`.
3.  Check duplicate rows/IDs, missing values, date parsing, per-merchant
    coverage, arithmetic consistency and balance continuity.
4.  Record validation results in a human-readable report.
5.  The sales dataset spans 2024-01-01 to 2026-10-31 (1,035 daily rows
    for each of four merchants), so it is approximately 34 months. Use
    the valid available history; do not assume it is exactly two years.
6.  The application dataset contains 1,000 rows and target `accepted`
    with both classes. Use chronological evaluation and check for
    applicant overlap/leakage.

### Phase 2 --- Train and persist ML models

Implement: - A pooled horizon-aware daily forecasting model for sales
inflow and total expense, with lag/rolling/calendar/merchant/horizon
features and strict no-future-leakage feature generation. - A naive
seasonal baseline and chronological validation. - A loan acceptance
classifier comparing Logistic Regression and Random Forest (or another
justified scikit-learn alternative), with preprocessing pipelines,
chronological split, metrics and probability calibration where
supported.

Save: - Forecast model artifact(s) under `artifacts/models/`. - Loan
acceptance model under `artifacts/models/`. - `model_metadata.json` with
training timestamp, feature list, split dates, model type, metrics and
limitations. - One 30-row prediction CSV per merchant: -
`artifacts/predictions/predicted_merchant001.csv` -
`artifacts/predictions/predicted_merchant002.csv` -
`artifacts/predictions/predicted_merchant003.csv` -
`artifacts/predictions/predicted_merchant004.csv`

Each forecast must include forecast date, horizon, predicted sales
inflow, predicted expense, net cash flow and projected closing balance.
Derive net cash flow as inflow minus expense and closing balance
cumulatively from the latest actual balance. Do not independently
predict mutually dependent financial values.

The frontend must let the merchant select 3, 7, 15 or 30 days and
visualize the daily forecast. The selected timeframe filters the same
30-day prediction, rather than retraining a different model.

### Phase 3 --- Backend and service layer

Build a modular FastAPI backend. Keep route handlers thin and place
business logic in services.

Implement: - Merchant-ID-only demo login using IDs loaded from
`merchants.csv`; no password/OTP. - Profile and loan history. - Product
listing from JSON. - Product-rule eligibility checks. - Acceptance
probability inference using the saved model and the same training
feature pipeline. - Recommendation ranking that considers eligibility,
probability, interest, fees, requested amount/tenure and
affordability. - Loan comparison. - EMI and total-cost calculator with
explicitly documented assumptions. - Forecast retrieval and refresh. -
Rule-based existing-loan optimization and new-loan simulation. - Model
status endpoint. - Health endpoint.

Keep acceptance probability, rule eligibility and affordability as three
distinct outputs. Never represent the classifier probability as
guaranteed approval. Never show a product as eligible if it fails an
explicit product requirement.

### Phase 4 --- Loan optimization

Use pending loan records for current obligations and completed loan
records for history. Aggregate daily EMI and remaining principal.
Compare forecast cash flow against existing EMI burden. Simulate a new
loan and evaluate the effect on projected cash balance and a
configurable safety buffer. Include processing/prepayment fees where
applicable. Provide reasons for each warning/recommendation.

### Phase 5 --- Mandatory AI-agent subsystem

The AI-agent subsystem is a compulsory project feature. Do not omit it,
postpone it as future work, or describe the agents as optional.

Implement:
1. Agent Orchestrator / Triage Agent to classify requests and route workflows.
2. Finance Q&A workflow grounded in a bounded finance knowledge context and verified backend data.
3. Loan Action workflow for natural-language requirement extraction, tool invocation, form-prefill payloads and validated UI navigation actions.
4. Comparison / On-screen Explanation workflow using structured frontend page context and authoritative backend product data.
5. Typed Tool Registry backed by shared domain services.
6. Merchant-scoped Conversation Context Manager.
7. Provider Gateway and OpenAI adapter with configuration checks, timeouts and structured errors.

A compact architecture with one orchestrator and specialized workflow nodes is acceptable. Keep the responsibilities distinct without creating unnecessary independent LLM calls.

When `OPENAI_API_KEY` is configured, enable LLM reasoning, finance Q&A, natural-language intent extraction, tool selection and contextual explanations. When it is absent, initialize the agent subsystem and expose deterministic tools/status normally; return a structured `llm_unavailable` response for requests that require LLM reasoning. Never fabricate an AI answer. Manual forms, direct navigation, REST APIs, MCP deterministic tools and core application features must continue working.

### Phase 6 --- MCP server

Implement MCP tools that reuse the exact same backend service layer as
REST endpoints: - `get_merchant_profile` - `get_merchant_loans` -
`get_loan_products` - `check_product_eligibility` -
`predict_loan_acceptance` - `recommend_loans` - `compare_loans` -
`get_cashflow_forecast` - `simulate_loan` - `optimize_existing_loans` -
`get_page_context` - `navigate_ui`

Integrate the MCP server with FastAPI using the supported Python MCP SDK
transport. Document the endpoint and transport. Validate every argument,
merchant ID, page name and navigation parameter. Do not expose arbitrary
SQL tools. Do not allow cross-merchant data access.

### Phase 7 --- Frontend

Build a polished, responsive LoanIQ interface with Paytm-inspired
blue/navy/light backgrounds, but use LoanIQ branding rather than Paytm
logos.

Pages: - Login - Dashboard - Loan recommendations - Compare loans -
Forecast analytics - Loan optimizer/simulator - Merchant profile and
loan history - Assistant panel/page

The login must accept only a merchant ID. Populate valid IDs dynamically
from the backend. Provide logout and clear the active session.

Dashboard must show: - Merchant snapshot. - Top eligible loan
recommendations. - Active loan summary. - Forecast preview. - Navigation
to all key features.

Forecast page: - 3/7/15/30-day selector. - Daily line graph. - Toggle
inflow, outflow, net cash flow and closing balance. - Forecast
totals/averages. - Negative/low cash-balance warnings. - Forecast
timestamp and estimate disclaimer.

Comparison page must show all meaningful cost and eligibility fields.
Optimizer page must have working inputs and call backend simulation
endpoints. Do not leave buttons decorative.

### Phase 8 --- Mandatory translation and voice integration adapters

The application must start and all core features must work with an empty
`.env`.

OpenAI: - Implement the mandatory conversational AI-agent workflows and provider adapter. The agent architecture and integration are required; OpenAI API execution requires `OPENAI_API_KEY`. - Use
structured tool calling for backend operations. - Natural-language
intent example: "I need a ₹5 lakh loan and can afford ₹2,000 daily EMI."
Extract fields, call backend recommendation/simulation tools, populate
the form and return a validated frontend navigation action. - Comparison
request should navigate to comparison and explain the products using
authoritative backend data. - On-screen explanation must use structured
page context sent by frontend (page name, selected product IDs, visible
data identifiers), then fetch authoritative backend details. Do not rely
on arbitrary screen scraping. - Do not allow arbitrary natural-language
SQL. Use predefined tools and parameterized operations. - If
`OPENAI_API_KEY` is missing, show assistant
unavailable/configuration-required status without breaking the rest of
the application.

Sarvam: - Implement the required voice integration adapter and STT/TTS workflows. Actual API execution requires `SARVAM_API_KEY`. Integrate STT and TTS using current official documented
endpoints and payloads. - Read `SARVAM_API_KEY` from backend environment
only. - Support graceful errors and text fallback. - Do not invent API
endpoints or claim voice works when credentials are missing.

Google Translation: - Implement the required translation adapter, UI string-key translation workflow and persistent cache. Actual API execution requires `GOOGLE_TRANSLATE_API_KEY`. Translate UI string keys only. - Support English,
Hindi and Marathi initially. - Use `GOOGLE_TRANSLATE_API_KEY`. - Cache
by source/target language and source text/key in SQLite or persistent
cache. - Do not call translation API again for cached values. - Missing
key must leave English UI fully functional.

### Phase 9 --- Tests and quality

Create automated tests for: - Dataset validation. - Forecast leakage and
chronological splits. - Exactly 30 forecast rows per merchant. -
Forecast arithmetic and cumulative balance. - Prediction CSV
generation. - Acceptance probability bounds and model status. - Product
eligibility and ranking. - EMI/fee calculations. - Loan aggregation and
optimization warnings. - Merchant data isolation. - Missing API-key
operation. - Translation cache. - MCP tool validation. - Frontend
login/logout, navigation, horizon selector and chart data.

Run the training scripts, tests and application. Fix errors rather than
merely listing them.

## Engineering requirements

-   Use type hints and Pydantic schemas.
-   Keep secrets in environment variables; never send them to frontend.
-   Add CORS only as needed for local development.
-   Use parameterized database queries.
-   Add useful error messages, loading states and empty states.
-   Keep all business calculations deterministic in backend services.
-   Do not fabricate forecast/model metrics.
-   If model quality is weak, show the metrics and limitations rather
    than hiding them.
-   Use INR formatting consistently.
-   Add visible synthetic-data and non-production disclaimers.
-   Do not claim real lender integration, actual loan approval,
    application submission or disbursement.

## Required final handoff

At completion, provide: 1. Final folder structure. 2. Exact
setup/install/run commands. 3. Exact model training and forecast
generation commands. 4. Test command and test results. 5. Local
frontend/backend URLs. 6. MCP endpoint and example tool invocation
instructions. 7. `.env.example` with external API keys blank while all mandatory adapters and agent architecture are implemented. 8. Model
metrics and limitations. 9. List of features verified working. 10. List
of incomplete features, if any.

Do not stop after creating a plan or skeleton. Implement the complete
working MVP described in `prompt.md`, run it, test it and fix issues. If
a requirement cannot be completed, state the precise reason and do not
pretend it works.
