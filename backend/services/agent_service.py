"""
LoanIQ AI Agent Subsystem.
Mandatory architecture containing:
1. Agent Orchestrator / Triage: Classifies intents and routes workflows.
2. Finance Q&A Workflow: Bounded financial definitions & loan terms.
3. Loan Action Workflow: Intent extraction, recommendation tool calling, form prefill & navigation.
4. Comparison / On-screen Explanation Workflow: Structured page context & authoritative backend data.
5. Typed Tool Registry: Backed by shared domain services.
6. Merchant-scoped Conversation Context Manager: Persisted in SQLite.
7. OpenAI Provider Gateway: Configuration check, graceful degradation when API key is absent.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import httpx
from backend.config import settings
from backend.database import get_db_connection, log_tool_call
from backend.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    UIAction,
    ToolCallRecord,
    PageContext
)
from backend.services.merchant_service import (
    get_merchant_profile,
    get_merchant_loans,
    get_loan_products,
    get_loan_product_by_id
)
from backend.services.recommendation import (
    check_product_eligibility,
    recommend_loans,
    compare_loans
)
from backend.services.acceptance_model import predict_loan_acceptance_probability
from backend.services.forecasting import get_merchant_forecast
from backend.services.loan_optimizer import simulate_loan, get_merchant_optimization
from backend.services.emi_calculator import calculate_loan_cost

# Bounded finance knowledge definitions for Finance Q&A
BOUNDED_FINANCE_QA = {
    "daily_emi": (
        "Daily EMI (Equated Monthly Installment divided into daily installments) is a micro-repayment model "
        "designed for retail merchants. Instead of a large monthly lump sum, a small predictable amount is deducted "
        "daily from sales inflow. LoanIQ uses the daily reducing balance convention: interest accrues daily on the "
        "outstanding principal at (Annual Rate / 365)."
    ),
    "reducing_balance": (
        "Under the reducing balance method, interest is calculated on the remaining unpaid loan balance each day, "
        "rather than on the full original principal. As you repay principal daily, your daily interest charge progressively decreases."
    ),
    "prepayment_fee": (
        "A prepayment fee is a penalty charged by lenders if you close or repay your loan before the contractual tenure ends. "
        "In LoanIQ's product catalog, products like LP001, LP003, LP007, and LP009 charge 0% prepayment fees, while others charge 1.0%."
    ),
    "processing_fee": (
        "A processing fee is a one-time administrative charge deducted upfront upon loan disbursement. "
        "In our catalog, processing fees range between 1.0% and 1.5% of the sanctioned loan principal."
    ),
    "affordability": (
        "Loan affordability measures whether your projected daily net cash flow (inflow minus operating expenses) "
        "comfortably covers your existing daily EMIs plus the new loan's daily EMI, while preserving a healthy safety buffer (e.g. ₹5,000)."
    ),
    "acceptance_probability": (
        "Historical acceptance probability in LoanIQ is an algorithmic estimate produced by a Calibrated Machine Learning model "
        "trained on past lending records. It estimates how closely your business profile and requested terms match historically accepted applications. "
        "It is a decision-support estimate, NOT a guarantee of loan approval."
    )
}

# Allowlisted pages for UI navigation
ALLOWLISTED_PAGES = ["dashboard", "recommendations", "compare", "forecast", "optimizer", "profile", "assistant"]


# -------------------------------------------------------------------------
# Tool Registry: Typed shared functions
# -------------------------------------------------------------------------
class ToolRegistry:
    @staticmethod
    def get_merchant_profile(merchant_id: str) -> Dict[str, Any]:
        p = get_merchant_profile(merchant_id)
        return p.model_dump() if p else {"error": f"Merchant {merchant_id} not found"}

    @staticmethod
    def get_merchant_loans(merchant_id: str, status: str = "all") -> List[Dict[str, Any]]:
        loans = get_merchant_loans(merchant_id, status=status)
        return [l.model_dump() for l in loans]

    @staticmethod
    def get_loan_products() -> List[Dict[str, Any]]:
        products = get_loan_products()
        return [p.model_dump() for p in products]

    @staticmethod
    def check_product_eligibility(merchant_id: str, loan_id: str, requested_amount: float, tenure_days: int) -> Dict[str, Any]:
        res = check_product_eligibility(merchant_id, loan_id, requested_amount, tenure_days)
        return res.model_dump()

    @staticmethod
    def predict_loan_acceptance(merchant_id: str, loan_id: str, requested_amount: float, tenure_days: int) -> Dict[str, Any]:
        prob, prob_str, is_fb = predict_loan_acceptance_probability(merchant_id, loan_id, requested_amount, tenure_days)
        return {
            "loan_id": loan_id,
            "estimated_probability": prob,
            "probability_percentage": prob_str,
            "is_fallback": is_fb
        }

    @staticmethod
    def recommend_loans(merchant_id: str, requested_amount: float = 100000.0, max_daily_emi: Optional[float] = None, tenure_days: int = 365) -> List[Dict[str, Any]]:
        recs = recommend_loans(merchant_id, requested_amount, max_daily_emi, tenure_days)
        return [r.model_dump() for r in recs]

    @staticmethod
    def compare_loans(merchant_id: str, loan_ids: List[str], requested_amount: float = 100000.0, tenure_days: int = 365) -> Dict[str, Any]:
        comp = compare_loans(merchant_id, loan_ids, requested_amount, tenure_days)
        return comp.model_dump()

    @staticmethod
    def get_cashflow_forecast(merchant_id: str, horizon_days: int = 30) -> Dict[str, Any]:
        fc = get_merchant_forecast(merchant_id, horizon_days)
        return fc.model_dump()

    @staticmethod
    def simulate_loan(merchant_id: str, loan_amount: float, tenure_days: int, annual_interest_rate: float, processing_fee_pct: float = 1.0) -> Dict[str, Any]:
        sim = simulate_loan(merchant_id, loan_amount, tenure_days, annual_interest_rate, processing_fee_pct)
        return sim.model_dump()

    @staticmethod
    def optimize_existing_loans(merchant_id: str) -> Dict[str, Any]:
        opt = get_merchant_optimization(merchant_id)
        return opt.model_dump()

    @staticmethod
    def get_page_context(merchant_id: str, page_name: str, selected_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if page_name not in ALLOWLISTED_PAGES:
            return {"error": f"Page '{page_name}' is not in allowlisted pages."}
        profile = get_merchant_profile(merchant_id)
        data: Dict[str, Any] = {
            "page_name": page_name,
            "merchant_id": merchant_id,
            "business_name": profile.business_name if profile else None,
        }
        if page_name == "compare" and selected_ids:
            data["compared_products"] = [get_loan_product_by_id(pid).model_dump() for pid in selected_ids if get_loan_product_by_id(pid)]
        elif page_name == "optimizer":
            opt = get_merchant_optimization(merchant_id)
            data["optimization"] = opt.model_dump()
        return data

    @staticmethod
    def navigate_ui(merchant_id: str, page: str, parameters: Optional[Dict[str, Any]] = None) -> UIAction:
        if page not in ALLOWLISTED_PAGES:
            page = "dashboard"
        return UIAction(action_type="NAVIGATE", target_page=page, parameters=parameters or {})


# -------------------------------------------------------------------------
# Conversation Context Manager
# -------------------------------------------------------------------------
def get_session_history(merchant_id: str, session_id: str) -> List[Dict[str, str]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT messages_json FROM conversation_sessions WHERE session_id = ? AND merchant_id = ?",
        (session_id, merchant_id)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["messages_json"])
        except Exception:
            return []
    return []


def save_session_history(merchant_id: str, session_id: str, messages: List[Dict[str, str]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO conversation_sessions (session_id, merchant_id, messages_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            messages_json = excluded.messages_json,
            updated_at = excluded.updated_at
    """, (session_id, merchant_id, json.dumps(messages), now, now))
    conn.commit()
    conn.close()


# -------------------------------------------------------------------------
# Intent Parsing Helpers (Deterministic NLP)
# -------------------------------------------------------------------------
def extract_numeric_loan_requirement(text: str) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    """
    Extracts (amount, max_daily_emi, tenure_days) from natural language.
    Handles '5 lakh', '50,000', '₹50000', '2000 emi', '180 days', etc.
    """
    amount = None
    emi = None
    tenure = None

    # Amount patterns: e.g. "5 lakh", "2.5 lakh", "50000", "₹1,00,000"
    lakh_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lac|l)', text, re.IGNORECASE)
    if lakh_match:
        amount = float(lakh_match.group(1)) * 100000.0
    else:
        num_match = re.search(r'(?:₹|rs\.?|inr)?\s*([1-9]\d{1,2}(?:,\d{2,3})*(?:\.\d+)?|[1-9]\d{3,7})', text, re.IGNORECASE)
        if num_match:
            raw_str = num_match.group(1).replace(",", "")
            val = float(raw_str)
            if val >= 5000:  # loan amounts typically >= 5000
                amount = val

    # EMI pattern: "2000 daily emi", "emi of 500", "afford 500 emi", "with 2000 daily emi"
    emi_match = re.search(r'(?:(?:emi|daily\s*emi)\s*(?:of|is|limit|:)?\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)?(?:\.\d+)?))', text, re.IGNORECASE)
    if not emi_match:
        emi_match = re.search(r'(?:(?:with|afford|pay|max|upto)\s*)?(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:daily\s*emi|emi|per\s*day)', text, re.IGNORECASE)
    if emi_match:
        raw_emi = emi_match.group(1).replace(",", "")
        val = float(raw_emi)
        if amount is None or val < amount:  # EMI must be less than principal
            emi = val

    # Tenure pattern: "180 days", "365 days", "6 months", "1 year"
    tenure_days_match = re.search(r'(\d+)\s*(?:days|day)', text, re.IGNORECASE)
    if tenure_days_match:
        tenure = int(tenure_days_match.group(1))
    elif re.search(r'6\s*months?', text, re.IGNORECASE):
        tenure = 180
    elif re.search(r'1\s*(?:year|yr)', text, re.IGNORECASE) or re.search(r'12\s*months?', text, re.IGNORECASE):
        tenure = 365
    elif re.search(r'18\s*months?', text, re.IGNORECASE):
        tenure = 540

    return amount, emi, tenure


def classify_intent(text: str, page_context: Optional[PageContext]) -> str:
    lower = text.lower()

    # Loan action intent
    if any(k in lower for k in ["need a loan", "want a loan", "get a loan", "apply for", "borrow", "lakh", "afford", "can pay", "suggest a loan"]):
        return "LOAN_ACTION"

    # Comparison intent
    if any(k in lower for k in ["compare", "comparison", "difference between", "which is better", "which loan is best", "explain this loan", "explain screen", "explain on screen"]):
        return "COMPARISON_EXPLANATION"

    # Navigation intent
    if any(k in lower for k in ["go to forecast", "open forecast", "show forecast", "go to optimizer", "open optimizer", "view profile"]):
        return "NAVIGATION"

    # Finance Q&A intent
    if any(k in lower for k in ["what is", "how does", "how is", "explain", "meaning of", "penalty", "prepayment", "reducing balance"]):
        return "FINANCE_QA"

    return "GENERAL"


# -------------------------------------------------------------------------
# Agent Service Orchestrator
# -------------------------------------------------------------------------
class AgentService:
    @classmethod
    def process_chat(cls, req: AgentChatRequest) -> AgentChatResponse:
        merchant_id = req.merchant_id
        profile = get_merchant_profile(merchant_id)
        if not profile:
            return AgentChatResponse(
                reply_text=f"Merchant {merchant_id} is not recognized. Please sign in with a valid demo merchant ID.",
                workflow_type="ERROR",
                llm_used=False
            )

        history = get_session_history(merchant_id, req.session_id or "default")
        intent = classify_intent(req.message, req.page_context)
        api_key = settings.OPENAI_API_KEY.strip()

        # If OpenAI API Key is present, attempt LLM Reasoning Workflow
        if api_key:
            try:
                return cls._run_openai_workflow(req, intent, profile, history)
            except Exception as e:
                # Graceful degradation if LLM call fails
                print(f"OpenAI call failed ({str(e)}). Falling back to deterministic agent workflow.")

        # Deterministic Agent Workflows (Works completely API-key-free!)
        return cls._run_deterministic_workflow(req, intent, profile, history)

    @classmethod
    def _run_deterministic_workflow(
        cls,
        req: AgentChatRequest,
        intent: str,
        profile: Any,
        history: List[Dict[str, str]]
    ) -> AgentChatResponse:
        merchant_id = req.merchant_id
        text = req.message
        tool_records: List[ToolCallRecord] = []

        # Workflow 1: LOAN ACTION (Requirement Extraction & Form Navigation)
        if intent == "LOAN_ACTION":
            amount, emi, tenure = extract_numeric_loan_requirement(text)
            req_amount = amount or 100000.0
            req_tenure = tenure or 365

            recs = ToolRegistry.recommend_loans(merchant_id, requested_amount=req_amount, max_daily_emi=emi, tenure_days=req_tenure)
            log_tool_call("recommend_loans", merchant_id, json.dumps({"amount": req_amount, "emi": emi, "tenure": req_tenure}), "SUCCESS")

            eligible_recs = [r for r in recs if r["is_eligible"]]
            top_rec = eligible_recs[0] if eligible_recs else (recs[0] if recs else None)

            tool_records.append(ToolCallRecord(
                tool_name="recommend_loans",
                arguments={"merchant_id": merchant_id, "requested_amount": req_amount, "max_daily_emi": emi, "tenure_days": req_tenure},
                result_preview=f"Found {len(eligible_recs)} eligible products. Top match: {top_rec['product_name'] if top_rec else 'None'}"
            ))

            reply_parts = [
                f"I processed your loan requirement of ₹{req_amount:,.0f}"
                + (f" with a max daily EMI of ₹{emi:,.2f}" if emi else "")
                + f" over {req_tenure} days."
            ]

            if top_rec:
                reply_parts.append(
                    f"\n\n**Top Recommendation:** **{top_rec['product_name']}** by {top_rec['lender_name']}\n"
                    f"• Interest Rate: {top_rec['annual_interest_rate']}%\n"
                    f"• Estimated Daily EMI: ₹{top_rec['estimated_daily_emi']:.2f}\n"
                    f"• Acceptance Probability: {top_rec['probability_percentage']}\n"
                    f"• Affordability: {top_rec['affordability_status']}\n"
                    f"• Reason: {top_rec['recommendation_reason']}"
                )
                reply_parts.append("\n\nI have prefilled your requirement and routed you to the Recommendations page.")
            else:
                reply_parts.append("\n\nNo eligible products matched these strict limits. Navigating to Recommendations so you can review eligibility reasons.")

            ui_action = UIAction(
                action_type="NAVIGATE",
                target_page="recommendations",
                parameters={"amount": req_amount, "emi": emi, "tenure": req_tenure}
            )

            response = AgentChatResponse(
                reply_text="".join(reply_parts),
                workflow_type="LOAN_ACTION",
                llm_used=False,
                ui_action=ui_action,
                extracted_data={"amount": req_amount, "emi": emi, "tenure": req_tenure},
                tool_calls=tool_records,
                suggested_prompts=["Compare top eligible loans", "Check my cashflow forecast", "Simulate ₹50,000 for 180 days"]
            )
            cls._save_turn(merchant_id, req.session_id or "default", history, text, response.reply_text)
            return response

        # Workflow 2: COMPARISON & ON-SCREEN EXPLANATION
        if intent == "COMPARISON_EXPLANATION":
            # Check if user mentioned specific product IDs or if on-screen context was passed
            product_ids = re.findall(r'LP\d{3}', text.upper())
            if not product_ids and req.page_context and req.page_context.selected_product_ids:
                product_ids = req.page_context.selected_product_ids

            comp_result = ToolRegistry.compare_loans(merchant_id, loan_ids=product_ids, requested_amount=100000.0, tenure_days=365)
            log_tool_call("compare_loans", merchant_id, json.dumps({"loan_ids": product_ids}), "SUCCESS")

            tool_records.append(ToolCallRecord(
                tool_name="compare_loans",
                arguments={"merchant_id": merchant_id, "loan_ids": product_ids},
                result_preview=f"Best overall: {comp_result.get('best_overall_loan_id')}, Lowest rate: {comp_result.get('lowest_interest_loan_id')}"
            ))

            prods = comp_result.get("products", [])
            lines = ["Here is the authoritative comparison analysis based on verified backend product records:\n"]
            for p in prods[:4]:
                elig_label = "✅ Eligible" if p["is_eligible"] else "❌ Ineligible"
                lines.append(
                    f"**{p['product_name']}** ({p['loan_id']}) - {p['lender_name']}:\n"
                    f"  • Rate: {p['annual_interest_rate']}% APR | Daily EMI: ₹{p['estimated_daily_emi']:.2f}\n"
                    f"  • Processing Fee: {p['processing_fee_pct']}% | Prepay Fee: {p['prepayment_fee_pct']}%\n"
                    f"  • Acceptance Likelihood: {p['probability_percentage']} | Status: {elig_label}\n"
                )

            lines.append(
                f"\n**Verdict:** Product **{comp_result.get('best_overall_loan_id')}** offers the best multi-factor balance "
                f"of interest cost, acceptance probability, and cashflow safety. "
                f"Lowest interest APR is available on **{comp_result.get('lowest_interest_loan_id')}**."
            )

            ui_action = UIAction(
                action_type="NAVIGATE",
                target_page="compare",
                parameters={"loan_ids": [p["loan_id"] for p in prods[:4]]}
            )

            response = AgentChatResponse(
                reply_text="\n".join(lines),
                workflow_type="COMPARISON_EXPLANATION",
                llm_used=False,
                ui_action=ui_action,
                tool_calls=tool_records,
                suggested_prompts=["Explain prepayment fees", "Optimize my existing loans", "Check 30-day forecast"]
            )
            cls._save_turn(merchant_id, req.session_id or "default", history, text, response.reply_text)
            return response

        # Workflow 3: NAVIGATION
        if intent == "NAVIGATION":
            target = "dashboard"
            lower = text.lower()
            if "forecast" in lower:
                target = "forecast"
            elif "optimizer" in lower or "simulate" in lower:
                target = "optimizer"
            elif "recommend" in lower:
                target = "recommendations"
            elif "compare" in lower:
                target = "compare"
            elif "profile" in lower or "history" in lower:
                target = "profile"

            ui_action = UIAction(action_type="NAVIGATE", target_page=target, parameters={})
            reply = f"Navigating directly to the {target.title()} section."
            response = AgentChatResponse(
                reply_text=reply,
                workflow_type="NAVIGATION",
                llm_used=False,
                ui_action=ui_action,
                suggested_prompts=["Show loan recommendations", "Check my active loans"]
            )
            cls._save_turn(merchant_id, req.session_id or "default", history, text, reply)
            return response

        # Workflow 4: FINANCE Q&A
        if intent == "FINANCE_QA":
            lower = text.lower()
            reply = ""
            if "daily emi" in lower:
                reply = BOUNDED_FINANCE_QA["daily_emi"]
            elif "reducing" in lower:
                reply = BOUNDED_FINANCE_QA["reducing_balance"]
            elif "prepay" in lower:
                reply = BOUNDED_FINANCE_QA["prepayment_fee"]
            elif "processing fee" in lower:
                reply = BOUNDED_FINANCE_QA["processing_fee"]
            elif "afford" in lower:
                reply = BOUNDED_FINANCE_QA["affordability"]
            elif "acceptance" in lower or "probability" in lower:
                reply = BOUNDED_FINANCE_QA["acceptance_probability"]
            else:
                reply = (
                    "LoanIQ provides structured financing recommendations for merchants. "
                    "You can ask about daily EMI calculations, reducing balance interest, prepayment fees, "
                    "or ask for personalized loan recommendations matching your cashflow."
                )

            response = AgentChatResponse(
                reply_text=reply,
                workflow_type="FINANCE_QA",
                llm_used=False,
                suggested_prompts=["What is daily EMI?", "What is prepayment fee?", "I need a ₹1 lakh loan"]
            )
            cls._save_turn(merchant_id, req.session_id or "default", history, text, reply)
            return response

        # Workflow 5: GENERAL DEFAULT
        default_reply = (
            f"Hello {profile.business_name}! I am your LoanIQ Credit Assistant. "
            f"I can help you discover eligible loans, evaluate daily EMI affordability, compare lenders, "
            f"and optimize your repayments against your forecast cash flow.\n\n"
            f"Try asking:\n"
            f"• *'I need a ₹50,000 loan with ₹300 daily EMI'*\n"
            f"• *'Compare top 3 loans for me'*\n"
            f"• *'What is daily EMI and how does reducing balance work?'*\n"
            f"• *'Take me to forecast analytics'*"
        )
        response = AgentChatResponse(
            reply_text=default_reply,
            workflow_type="GENERAL",
            llm_used=False,
            suggested_prompts=["I need a ₹1 lakh loan", "Compare all loans", "Show forecast analytics"]
        )
        cls._save_turn(merchant_id, req.session_id or "default", history, text, default_reply)
        return response

    @classmethod
    def _run_openai_workflow(
        cls,
        req: AgentChatRequest,
        intent: str,
        profile: Any,
        history: List[Dict[str, str]]
    ) -> AgentChatResponse:
        """Execute LLM workflow using OpenAI Responses API with structured tools and bounded context."""
        api_key = settings.OPENAI_API_KEY.strip()
        model = settings.OPENAI_MODEL or "gpt-4o-mini"
        merchant_id = req.merchant_id

        # Pre-fetch merchant financial summary to bound the prompt context
        opt = ToolRegistry.optimize_existing_loans(merchant_id)
        fc = ToolRegistry.get_cashflow_forecast(merchant_id, 30)

        system_prompt = (
            f"You are the LoanIQ AI Financial Assistant for Indian small businesses. "
            f"Current Merchant: {profile.business_name} (ID: {merchant_id}, City: {profile.city}, Type: {profile.merchant_type}). "
            f"Monthly Sales: ₹{profile.monthly_sales_reference:,.0f}, Credit Score: {profile.credit_score}. "
            f"Active Loans: {opt['active_loans_count']}, Total Remaining Debt: ₹{opt['total_remaining_principal']:,.2f}, "
            f"Existing Daily EMI: ₹{opt['total_current_daily_emi']:.2f}. "
            f"30-day Avg Daily Net Cashflow: ₹{fc['avg_daily_net_cashflow']:.2f}. "
            f"Bound all responses to LoanIQ's product rules, deterministic calculations, and bounded finance knowledge. "
            f"NEVER claim guaranteed loan approval. Explain that acceptance probabilities are model estimates. "
            f"If the user asks for a loan amount or EMI, extract the values and formulate a navigation action to 'recommendations'."
        )

        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": req.message})

        # Call OpenAI Chat Completion
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 600
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                reply_text = data["choices"][0]["message"]["content"]

                # Extract UI Action if user asked for recommendations or comparison
                ui_action = None
                extracted = {}
                if intent == "LOAN_ACTION":
                    amt, emi, ten = extract_numeric_loan_requirement(req.message)
                    extracted = {"amount": amt or 100000.0, "emi": emi, "tenure": ten or 365}
                    ui_action = UIAction(action_type="NAVIGATE", target_page="recommendations", parameters=extracted)
                elif intent == "COMPARISON_EXPLANATION":
                    ui_action = UIAction(action_type="NAVIGATE", target_page="compare", parameters={})

                cls._save_turn(merchant_id, req.session_id or "default", history, req.message, reply_text)
                return AgentChatResponse(
                    reply_text=reply_text,
                    workflow_type=intent,
                    llm_used=True,
                    ui_action=ui_action,
                    extracted_data=extracted,
                    suggested_prompts=["Compare these products", "Simulate this loan", "View cashflow forecast"]
                )
            else:
                raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text}")

    @classmethod
    def _save_turn(cls, merchant_id: str, session_id: str, history: List[Dict[str, str]], user_msg: str, assistant_msg: str):
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        save_session_history(merchant_id, session_id, history[-20:])
