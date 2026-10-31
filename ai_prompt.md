# LoanIQ AI Implementation Specification

**Status:** Implementation specification for the AI layer.  
**Parent specification:** `prompt.md` (authoritative for existing product features, datasets, ML, backend and frontend requirements).  
**Execution companion:** `ANTIGRAVITY_AI_REFERENCE_PROMPT.md`.

## 1. Non-negotiable preservation rule

This document adds AI capabilities to LoanIQ. It does not replace the existing application specification.

- Read the complete root `prompt.md`, existing source code, tests, routes, frontend pages, data files and current MCP tools before changing anything.
- Preserve every existing working feature, route, page, model, dataset, calculation, workflow, UI interaction and configuration. Do not delete, rename, weaken, rewrite unnecessarily, or replace a working implementation.
- Integrate AI into the existing architecture and reuse existing services. Do not create duplicate implementations of forecasting, eligibility, recommendation, loan calculations, loan optimization or merchant data access.
- Before changing an existing API contract, schema, database table, MCP tool name/argument, route, frontend interaction or stored data format, document the impact and obtain explicit approval.
- Make additive, backward-compatible changes wherever possible. Add regression tests for preserved capabilities.
- Do not invent Paytm/lender integrations. Loan products and historical data remain demo/synthetic as described in `prompt.md`.

## 2. AI provider selection

Use the following providers and exact model IDs. Keep provider calls behind adapters so the application can be tested with mocks and can start without credentials.

### 2.1 OpenAI

- **Model:** `gpt-5.6-luna`
- **API:** OpenAI Responses API (`POST /v1/responses`)
- **Purpose:** intent understanding, triage, choosing workflows, structured argument extraction, calling approved tools, contextual explanations, finance-domain Q&A and converting user requests into validated UI action plans.
- **Tool use:** Responses API function calling with strict JSON schemas. Use structured outputs for final action payloads where appropriate.
- **Do not use the LLM for:** arithmetic, EMI calculations, eligibility rules, model inference, forecasts, ranking calculations, SQL construction or deciding whether a product passes deterministic eligibility checks. Those remain backend services.
- **No automatic model escalation:** use Luna only. Do not silently switch to a more expensive model. If Luna cannot complete a task, return a clear limitation or ask a clarification.
- **Reasoning effort:** start with `low` for simple routing/extraction and `medium` for multi-step workflows; tune only after testing. Keep output limits low and task-specific.

Official references:
- https://developers.openai.com/api/docs/models/gpt-5.6-luna
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/prompt-caching

### 2.2 Sarvam

Use one backend-only `SARVAM_API_KEY` for these Sarvam APIs:

| Capability | Model ID | API endpoint | LoanIQ use |
|---|---|---|---|
| Speech-to-text | `saaras:v4` | `/speech-to-text` | Convert merchant speech to text in the original spoken language. |
| Text translation | `mayura:v1` | `/translate` | Translate merchant input to English for reasoning and translate assistant output/UI text back to the selected language. |
| Text-to-speech | `bulbul:v4-flash` | `/text-to-speech` | Speak the final response in a supported Indian language. |

Use Mayura for supported languages (including Marathi, Hindi and English). If the product later requires languages outside Mayura's supported set, propose `sarvam-translate:v1` as a separate change; do not silently switch models. Verify exact request fields, language codes, limits, voice IDs and response parsing against current official docs during implementation. Do not guess API schemas.

Official references:
- https://docs.sarvam.ai/api/getting-started/models/saaras
- https://docs.sarvam.ai/api/getting-started/models/mayura
- https://docs.sarvam.ai/api/getting-started/models/bulbul
- https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/overview
- https://docs.sarvam.ai/api-reference/text/translate-text

### 2.3 Environment variables

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_EFFORT=low
SARVAM_API_KEY=
SARVAM_STT_MODEL=saaras:v4
SARVAM_TRANSLATE_MODEL=mayura:v1
SARVAM_TTS_MODEL=bulbul:v4-flash
AI_RESPONSE_CACHE_TTL_SECONDS=300
AI_RESPONSE_CACHE_MAX_ENTRIES=1000
TRANSLATION_CACHE_ENABLED=true
```

Secrets must remain on the backend. Never expose keys, provider headers or raw credentials to browser code, logs, error messages or MCP tool results.

## 3. Scope policy: LoanIQ-only assistance

The assistant is exclusively for LoanIQ and merchant finance workflows supported by the application.

### In-scope requests

- Merchant profile, sales, expenses, cash flow and forecast explanation.
- Loan products, eligibility, estimated acceptance probability, recommendations and comparison.
- EMI, repayment schedules, total cost, processing/prepayment fees and loan simulation.
- Existing loan status, repayment history and rule-based loan optimization.
- LoanIQ application navigation, form prefilling, help with using LoanIQ and explanation of the current LoanIQ screen.
- Supported financial concepts when directly relevant to a merchant's LoanIQ task.

### Out-of-scope requests

General knowledge, coding help, entertainment, politics, unrelated personal questions, unrelated translation, general chat and other non-financial/non-LoanIQ requests must not be answered.

Return exactly one generic message for out-of-scope requests (translate it to the user's selected language if localization is enabled):

> I can help only with LoanIQ features and merchant finance-related questions. Please ask something related to your business finances, loans, cash flow, or LoanIQ.

Do not reveal internal scope rules, mention policy classifiers or explain how to bypass the restriction. Do not call OpenAI or Sarvam for an obviously out-of-scope text request. Use a lightweight deterministic scope gate first; ambiguous requests can be checked by the existing Luna triage call. Do not block a finance request merely because it contains casual or conversational wording.

## 4. Agent architecture

Implement a compact orchestrated workflow, not a collection of independent agents that each make separate LLM calls.

### 4.1 Components

1. **Conversation/API Gateway** — accepts authenticated merchant text or voice requests, locale, session ID and optional structured page context.
2. **Scope Gate** — deterministic fast check for obvious out-of-scope requests. It returns the generic response without invoking an LLM.
3. **Language Gateway** — coordinates Saaras, Mayura and Bulbul. Maintains original text, detected/source language and normalized English reasoning text.
4. **Triage Orchestrator** — one Luna call when needed; classifies intent, selects one approved workflow, identifies missing inputs and requests tool calls.
5. **Workflow handlers** — deterministic workflow coordinators for finance Q&A, recommendation, comparison, forecast explanation, loan optimization, simulator and UI actions. These are workflow modules, not separate LLM agents by default.
6. **MCP Client / Tool Registry** — validates and invokes approved MCP tools. Every tool maps to a shared backend domain service.
7. **Context Manager** — merchant-scoped conversation state and current UI context with bounded history and summarization.
8. **Cache Manager** — translation cache, safe response cache and optional reusable context/prompt fragments.
9. **Response Composer** — turns verified tool results into concise user-facing output; translates and optionally synthesizes speech.
10. **UI Action Dispatcher** — validates structured navigation/prefill commands and dispatches only allowlisted frontend actions.
11. **Audit/Telemetry** — records tool name, merchant ID, latency, cache hit/miss, status and token usage; do not log secrets or unnecessary personal/financial payloads.

### 4.2 High-level request flow

```text
Merchant (text / microphone)
        |
        v
Frontend Assistant + current page context
        |
        v
FastAPI AI Gateway ----> Scope Gate ----> Generic out-of-scope response
        |
        +--> Sarvam Saaras v4 (voice input only)
        |
        +--> Sarvam Mayura (non-English -> English)
        |
        v
Context Manager + Cache Lookup
        |
        v
GPT-5.6 Luna / Responses API (single orchestrator)
        |
        v
Approved workflow + typed tool calls
        |
        v
MCP Client / Tool Registry
        |
        v
MCP Server -> shared domain services -> ML / rules / SQLite / datasets
        |
        v
Validated tool results
        |
        v
Luna response synthesis (only if explanation is needed)
        |
        +--> Mayura (English -> selected language)
        +--> Bulbul v4 Flash (voice response only)
        |
        v
Frontend response + optional validated UI action
```

Avoid repeated LLM calls. The orchestrator should perform one tool-calling loop where possible. If multiple deterministic tools are required, call them in one workflow and return compact results to Luna for a single final explanation. Never call the LLM just to format a number or display an existing API result.

## 5. Agent/workflow capabilities

### 5.1 Triage and routing

Classify a request into one of these existing workflows:

- `finance_qa`
- `loan_recommendation`
- `loan_comparison`
- `cashflow_forecast`
- `loan_optimization`
- `loan_simulation`
- `ui_navigation_action`
- `on_screen_explanation`
- `clarification_required`
- `out_of_scope`

Return a typed object with `intent`, `workflow`, `confidence`, `required_fields`, `extracted_values`, `tool_plan`, `ui_action`, `requires_confirmation` and `user_message`. Validate it with Pydantic. Do not trust model-generated IDs or merchant IDs; bind merchant identity from the authenticated session.

### 5.2 Finance Q&A

Answer only questions in the LoanIQ/merchant-finance scope. Ground answers in the approved knowledge content and backend tools. For merchant-specific figures, fetch current backend values. If information is missing, say so. Never fabricate loan terms, lender decisions, regulatory requirements, balances, rates or predictions. If asked about a current page, use page context and authoritative backend data.

### 5.3 Loan recommendation

Extract desired amount, tenure, acceptable EMI/repayment limit and any stated preference. Call the existing recommendation and eligibility services. Keep these separate:

- Rule-based product eligibility.
- Historical acceptance probability estimate.
- Affordability/cash-flow impact.

Do not claim approval is guaranteed. Do not let Luna alter scores or override eligibility. Return ranked products with reasons already calculated by backend services.

### 5.4 Loan comparison

Use backend `compare_loans` data for product facts and calculations. Luna may explain trade-offs but must not invent or recalculate rates, fees or repayment values. If products are not identified, ask one concise clarification or use the existing comparison page's selected product IDs.

### 5.5 Forecast and optimizer explanation

Retrieve forecasts and optimization results from existing deterministic services. Luna can explain patterns, warnings and assumptions. It cannot generate replacement numeric forecasts or override optimization rules. Include the forecast timestamp and synthetic/demo-data disclaimer where relevant.

### 5.6 Natural-language UI control

The interface must be designed so MCP-controlled actions are first-class, not bolted on later.

- Every page has a stable `page_id` and semantic context contract.
- Every actionable control has a stable `action_id` and an allowlisted handler.
- Forms expose typed field names, types, constraints, defaults and current values.
- Frontend registers a central `UIActionDispatcher`; no arbitrary DOM selectors, generated JavaScript, HTML injection or eval.
- The assistant may request navigation, open a modal, select a tab, set a horizon, select known products, prefill validated form fields, or focus a control.
- Frontend validates action schema and field constraints again before applying it.
- Unknown page/action/field IDs return a clear unsupported-action result.
- The backend must never pretend the UI changed; frontend returns an acknowledgement after it actually applies the action.

Supported structured action contract:

```json
{
  "action_type": "navigate_and_prefill",
  "page_id": "loan_recommendations",
  "form_id": "loan_request_form",
  "field_values": {
    "requested_amount": 500000,
    "max_daily_emi": 2000
  },
  "selected_ids": [],
  "filters": {},
  "requires_confirmation": false,
  "explanation": "Open recommendations with the requested amount and daily EMI limit."
}
```

Allowlisted action types should include `navigate`, `navigate_and_prefill`, `set_filter`, `select_items`, `open_modal`, `focus_field` and `show_explanation`. These are UI-only actions. They must not submit an application, change a financial record, initiate a payment or perform any irreversible operation. Such operations require a separate explicit confirmation flow and are outside the current MVP unless approved.

Examples:

- “I need a ₹5 lakh loan and can pay ₹2,000 daily” -> open loan recommendations, prefill amount and daily EMI limit, then invoke recommendation service.
- “Compare all available loans” -> open comparison page and load products.
- “Show the next 30 days of cash flow” -> open forecast page and select 30 days.
- “Optimize my existing loans” -> open optimizer and load the merchant's active obligations.
- “Explain this loan” -> use current page context and selected product ID; fetch current product facts before explaining.

If required values are ambiguous, ask a clarification instead of guessing. Never infer a loan amount, tenure, product ID or merchant identity without evidence.

## 6. MCP server architecture

### 6.1 Design principles

- MCP server is a typed capability boundary over existing LoanIQ domain services.
- MCP tools must reuse the same service functions as REST endpoints. Do not duplicate business logic inside tool handlers.
- Keep tool handlers thin: validate input -> authenticate/authorize merchant context -> call service -> return typed result.
- Do not expose arbitrary SQL, shell, filesystem, Python execution, unrestricted HTTP, generic browser control or arbitrary code execution.
- Enforce merchant isolation on every tool call. Merchant ID must come from trusted authenticated context; never trust a model-supplied merchant ID.
- Apply per-tool timeouts, output size limits, validation and consistent error envelopes.
- Use Streamable HTTP MCP transport integrated with FastAPI if supported by the installed official Python MCP SDK. Keep a local stdio transport only if needed for development/testing. Document exact MCP endpoint and transport.

### 6.2 Existing approved MCP tools (preserve)

These are already in the LoanIQ project specification and are considered baseline capabilities. Keep names and contracts backward-compatible:

| Tool | Responsibility | Backing service |
|---|---|---|
| `get_merchant_profile` | Retrieve the authenticated merchant's profile. | Merchant service |
| `get_merchant_loans` | Retrieve active and completed loan records. | Loan account service |
| `get_loan_products` | Retrieve available demo loan products. | Product service |
| `check_product_eligibility` | Evaluate explicit product eligibility rules and reasons. | Eligibility service |
| `predict_loan_acceptance` | Return historical model probability and model metadata. | Acceptance model service |
| `recommend_loans` | Rank eligible products for the merchant/request. | Recommendation service |
| `compare_loans` | Compare selected/all products and cost fields. | Comparison service |
| `get_cashflow_forecast` | Retrieve existing 3/7/15/30-day forecast. | Forecast service |
| `simulate_loan` | Calculate EMI, total cost and projected cash-flow impact. | Simulator service |
| `optimize_existing_loans` | Evaluate current obligations and repayment scenarios. | Optimizer service |
| `get_page_context` | Retrieve a sanitized current page/context snapshot. | UI context service |
| `navigate_ui` | Return a validated UI action request to the frontend dispatcher. | UI action service |

### 6.3 MCP server layers

```text
MCP Host (LoanIQ Agent Orchestrator)
        |
        v
MCP Client / Connection Manager
        |
        v
LoanIQ MCP Server (Streamable HTTP)
        |
        +-- Authentication & merchant context
        +-- Tool registry / JSON schema validation
        +-- Authorization & rate limits
        +-- Tool handlers (thin)
        |
        v
Shared Domain Service Layer
        |
        +-- Merchant/Profile service
        +-- Loan/Product service
        +-- Eligibility / Acceptance / Recommendation
        +-- Forecasting / Cash-flow service
        +-- EMI / Simulation / Optimizer
        +-- UI Context / Navigation service
        |
        v
Existing ML artifacts, CSV/JSON datasets and SQLite
```

### 6.4 MCP result/error contract

Return structured results with `ok`, `data`, `error_code`, `message`, `retryable` and `correlation_id` (omit irrelevant fields where appropriate). Suggested error codes:

- `UNSUPPORTED_OPERATION` — the MCP server has no tool for the requested operation.
- `INVALID_ARGUMENT` — arguments fail schema or business validation.
- `UNAUTHORIZED` / `MERCHANT_SCOPE_VIOLATION` — invalid session or cross-merchant access.
- `NOT_FOUND` — requested product/loan/record does not exist.
- `SERVICE_UNAVAILABLE` — required backend/model service unavailable.
- `MODEL_NOT_READY` — model artifact unavailable.
- `PROVIDER_UNAVAILABLE` — external API unavailable or key missing.
- `TIMEOUT` — operation exceeded its timeout.

If MCP cannot perform an operation, tell the user clearly. Do not claim it was completed, do not silently substitute an unrelated tool, and do not invent results. User-facing example:

> I can't perform that operation in LoanIQ because the required capability is not available. No changes were made.

For a known unsupported operation, identify the limitation in plain language. Do not expose stack traces or internal implementation details.

## 7. Additional MCP capabilities — approval required

The following are proposals only. **Do not implement, expose, register, document as available, or call any of these until the project owner explicitly approves each item.** Existing tools in section 6.2 remain approved and must be preserved.

| Proposed tool | Potential value | Approval status |
|---|---|---|
| `get_merchant_cashflow_summary` | Compact summary of historical and forecast cash position. | Pending owner approval |
| `get_repayment_calendar` | Upcoming EMI/due-date schedule and aggregate daily burden. | Pending owner approval |
| `explain_recommendation` | Retrieve structured reason codes/factors for a recommendation. | Pending owner approval |
| `get_model_health` | Expose model readiness, last training time and evaluation metrics. | Pending owner approval |
| `get_supported_ui_actions` | Return currently registered page/action/field allowlists. | Pending owner approval |
| `get_translation_status` | Inspect configured languages and cache status without revealing credentials. | Pending owner approval |
| `get_assistant_capabilities` | Return a capability manifest so the agent can explain what it can/cannot do. | Pending owner approval |

Before adding any proposed tool, present its name, schema, authorization rules, backing service, user benefit, risks and tests in an approval request. Wait for explicit approval. Do not interpret silence as approval. Do not add more tools beyond this list without the same process.

## 8. Translation caching

Implement persistent SQLite caching for Sarvam translation calls, including UI strings and eligible conversational translations.

### Cache key

Use a deterministic key based on:

- Provider/model ID and model version where available.
- Source language code.
- Target language code.
- Translation mode/style and output script.
- Normalized source text or stable UI translation key + source text hash.

### Cache behavior

- Check cache before calling Sarvam.
- On miss, call Mayura and store the successful translation.
- Use a unique constraint on the cache key to prevent duplicate concurrent writes.
- Cache UI labels, buttons, navigation text, form labels, helper text and stable static messages for a long TTL (or indefinitely with explicit versioning).
- Cache dynamic sentences only when their full source text is identical; do not cache personalized financial responses under a shared/global key.
- Preserve placeholders such as `{merchant_name}`, `{amount}`, `{date}`, product IDs, loan IDs, merchant IDs, enum values, code tokens and interpolation markers. Translate templates with placeholders intact, then interpolate values after translation.
- Never translate or alter numbers, currency amounts, dates, IDs, API values, machine enums or structured JSON keys.
- Do not send an entire page's repeated strings as separate calls when a batch endpoint is available and officially supported; otherwise deduplicate and process only cache misses.
- Cache failures must not be stored as successful translations. On provider failure, fall back to English and show a non-blocking language-service status.
- Provide cache invalidation by translation key/version and a cache clear command for development.

Suggested table:

```sql
CREATE TABLE translation_cache (
  cache_key TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  source_language TEXT NOT NULL,
  target_language TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  source_text TEXT NOT NULL,
  translated_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_used_at TEXT NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 0
);
```

## 9. OpenAI response caching and minimum API usage

Use multiple layers; do not assume provider prompt caching is the same as application response caching.

### 9.1 Cache layers

1. **OpenAI prompt caching:** keep stable system instructions, tool schemas and workflow definitions at the beginning of the prompt; place dynamic merchant/page/request data after them. Reuse stable prompt prefixes. Do not add timestamps/random values to the stable prefix.
2. **Application response cache:** cache safe, repeatable read-only answers/results with a merchant-scoped key containing normalized request, workflow, merchant ID, relevant data/model version and locale. Use short configurable TTLs.
3. **Domain data cache:** cache expensive read-only product catalog/model metadata where appropriate; invalidate when underlying data/model changes.
4. **Translation cache:** handled separately in section 8.
5. **Conversation context:** keep only a bounded recent window plus compact merchant-scoped summary; do not resend the entire conversation on every turn.

### 9.2 Cache rules

- Never share personalized answers between merchants. Include merchant ID and authorization scope in all user-specific cache keys.
- Do not cache mutation/action results as reusable responses.
- Do not cache live balances, due status, current loan obligations, forecasts or recommendations beyond a conservative TTL; invalidate after any relevant data/model update. Prefer caching deterministic underlying results over natural-language explanations.
- Do not cache errors as successful responses. Negative-cache provider failures only briefly to prevent retry storms.
- Include `model_id`, system prompt version, tool schema version, dataset/model version and locale in relevant cache keys.
- Use SQLite initially. Add an in-process LRU only as a performance layer, never as the sole persistent cache.
- Add TTL cleanup and maximum-entry limits. Record cache hit/miss counts and token usage.

### 9.3 Minimize OpenAI calls/tokens

- Scope-gate obvious non-financial requests without OpenAI.
- Check response cache before calling Luna.
- Use one orchestrator call for routing + tool selection; avoid separate classification and planning calls.
- Keep tool descriptions concise and return only fields needed for the task.
- Parallelize independent deterministic backend/MCP calls within a workflow.
- Use deterministic backend results directly for simple displays; call Luna only when natural-language interpretation/explanation is needed.
- Use low reasoning effort for simple intent extraction; medium only for multi-step workflows.
- Set appropriate `max_output_tokens`; ask for concise responses.
- Avoid sending full datasets, full loan history or all page DOM. Send compact summaries and identifiers, then fetch details via tools.
- Summarize older conversation context and remove irrelevant turns.
- Avoid unnecessary Sarvam translation calls: English requests/responses need no translation; UI strings use cache; only synthesize TTS when user enables voice output or requests it.
- Do not translate the same content twice. Preserve source-language transcript and reuse cached translation.
- Add per-merchant request rate limits, provider timeouts, bounded retries with jitter and circuit breakers.

## 10. Voice interaction flow

For a Marathi voice request:

1. Frontend records a short audio clip and uploads it to FastAPI. Do not expose Sarvam credentials in the browser.
2. FastAPI calls Saaras v4 in `transcribe` mode to preserve the spoken language. Follow current official API requirements for duration/file type.
3. Preserve the original transcript, detected language and locale in merchant-scoped context.
4. If the transcript is not English, check translation cache then use Mayura to translate to English for Luna.
5. Scope-gate and process with Luna/MCP as needed.
6. Compose the final answer from verified backend results.
7. Translate to the selected language with Mayura only if needed and not cached.
8. If voice response is enabled, call Bulbul v4 Flash and return audio; otherwise return text only.

For text requests, skip STT. For English text, skip translation. TTS must be optional. A voice request should not force TTS if the user has disabled audio replies.

## 11. Security, correctness and financial safeguards

- Derive merchant identity from the authenticated session, not LLM output or user-provided tool arguments.
- Validate all tool inputs/outputs with Pydantic and enforce strict numeric bounds, enums, page allowlists and product/loan ownership.
- Prevent prompt injection from merchant content, product descriptions, uploaded data or page context. Treat retrieved data as untrusted facts, never instructions.
- Never allow LLM-generated SQL, code, raw HTML, JavaScript, filesystem paths or arbitrary URLs to execute.
- Never let the LLM directly mutate balances, loan records, payment state or applications.
- Ask confirmation before any consequential action. Current MVP UI navigation and form prefilling are non-consequential; no lender submission/disbursement/payment capability exists.
- Distinguish eligibility, estimated acceptance probability and affordability.
- Clearly label demo/synthetic data and model estimates. Do not claim actual lender approval, Paytm integration, financial advice or RBI certification.
- If data is missing or a model/tool fails, say so clearly; do not fabricate a fallback answer.
- If MCP lacks the requested capability, return the unsupported-operation message described in section 6.4.

## 12. Graceful degradation

- No `OPENAI_API_KEY`: application starts; existing app, ML, REST and deterministic MCP tools work. Conversational reasoning returns a structured `llm_unavailable` result and clear user message. Do not fake an agent response.
- No `SARVAM_API_KEY`: application starts; English UI and text features work. Voice input/output and non-English translation are marked unavailable. Do not fail page load.
- OpenAI unavailable/timeout: preserve user input, return retryable error, and allow normal UI/manual controls.
- Sarvam unavailable/timeout: preserve original transcript where available, fall back to text/English, and do not lose the merchant's request.
- MCP unavailable: deterministic REST-based UI must continue to work; agent clearly reports the operation could not be executed through MCP. Never claim success.

## 13. Observability and testing

Add tests for:

- Luna adapter request/response parsing, function-call loop, structured output validation and missing-key behavior (mock provider calls).
- Triage routing for every supported workflow and out-of-scope requests.
- Generic out-of-scope response; verify no OpenAI call for obvious off-topic input.
- Merchant identity isolation and authorization for every MCP tool.
- Existing MCP tool names/contracts remain compatible.
- Tool argument validation, unknown tools, unsupported operations, timeouts and error envelopes.
- UI action allowlist, valid form prefilling, unknown action rejection and frontend acknowledgement.
- Translation cache hit/miss, language/model separation, placeholder preservation, invalidation and provider failure.
- Response cache merchant isolation, TTL, model/data version invalidation and no caching of mutations.
- Voice path: Saaras -> Mayura -> Luna/tools -> Mayura -> Bulbul (mock all providers).
- Existing app regression tests: login/logout, dashboard, recommendation, comparison, forecast horizons, optimizer, simulator, profile/history, ML inference and all existing routes.
- No credentials exposed in frontend bundles, responses or logs.

Provide a usage report with number of OpenAI calls, Sarvam calls, prompt/output tokens (where returned), translation-cache hit rate, response-cache hit rate and average latency. Do not invent metrics.

## 14. Implementation sequence

1. Inspect `prompt.md`, the existing codebase, data, current tools, routes and tests. Produce an inventory of existing capabilities before editing.
2. Produce an AI integration plan and a compatibility/change-impact table. Identify any conflicts between this document and existing implementation; preserve current working behavior and ask before breaking changes.
3. Implement provider adapters and configuration/status handling.
4. Implement scope gate, context manager, cache layer and typed orchestrator.
5. Integrate the existing MCP tools with shared domain services and enforce merchant authorization.
6. Implement the workflows and validated UI action dispatcher.
7. Implement Sarvam voice and translation flows with SQLite caching.
8. Add tests and run all existing and new regression tests.
9. Verify application startup with no keys, OpenAI key only, Sarvam key only and both keys configured (mock external APIs where necessary).
10. Present the additional MCP proposals from section 7 for owner approval. Do not implement them until approval is explicitly received.

## 15. Definition of done

- All pre-existing LoanIQ capabilities continue to work and have regression evidence.
- GPT-5.6 Luna is the only configured OpenAI model and is called through Responses API.
- Sarvam Saaras v4, Mayura v1 and Bulbul v4 Flash are integrated through backend adapters.
- Triage/workflow orchestration, MCP tool calling, context management and UI action dispatch work end-to-end.
- UI navigation and prefilling use stable allowlisted action IDs; no arbitrary code execution.
- Translation and safe response caching work and are merchant-scoped where required.
- Obvious non-financial/non-LoanIQ questions receive the exact generic scope response without unnecessary API usage.
- Unsupported MCP operations are reported honestly; no false success messages.
- Missing provider keys do not break the application.
- New and existing tests pass, and setup/configuration is documented.
- Proposed additional MCP capabilities remain unimplemented until explicit owner approval.
