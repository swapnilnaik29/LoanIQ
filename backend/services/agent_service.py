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
from backend.services.scope_gate import check_financial_scope, GENERIC_OUT_OF_SCOPE_RESPONSE
from backend.services.cache_service import get_cached_ai_response, set_cached_ai_response
from backend.services.translation import translate_single_text
from backend.services.openai_adapter import OpenAIResponsesAdapter

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


def detect_query_language(text: str) -> str:
    """
    Detects whether text is Marathi ('mr'), Hindi ('hi'), or English ('en').
    Uses Devanagari character presence and distinct lexical discriminant tokens.
    """
    if not text:
        return "en"

    # Check for Devanagari Unicode range (\u0900 - \u097F)
    devanagari_chars = [c for c in text if '\u0900' <= c <= '\u097f']
    if not devanagari_chars:
        return "en"

    # Distinct Marathi markers (lexical + unique character 'ळ')
    marathi_markers = [
        "आहे", "आहेत", "होते", "होती", "का", "किती", "मला", "माझ्या", "माझे", "माझी",
        "हप्ता", "पाहिजे", "द्या", "घेऊन जा", "दाखवा", "बदला", "भरू", "शकतो", "शकता",
        "कर्ज", "करा", "नाही", "काय", "कसे", "कोणते", "सांगा", "नका", "बघा", "उघडा",
        "आणि", "किंवा", "येथे", "कृपया", "करावे", "मिळेल", "लागेल", "होय", "जास्त", "अधिक", "सध्याच्या"
    ]
    marathi_score = sum(text.count(marker) for marker in marathi_markers) + (text.count('ळ') * 4)

    # Distinct Hindi markers
    hindi_markers = [
        "है", "हैं", "था", "थी", "थे", "क्या", "कितना", "कितनी", "कितने", "मुझे",
        "मेरे", "मेरी", "मेरा", "किस्त", "किस्तें", "चाहिए", "दीजिए", "ले चलो", "दिखाओ",
        "बदलो", "भर सकता", "भर सकते", "ऋण", "नहीं", "कैसे", "कौनसा", "बताओ", "और",
        "या", "यहाँ", "कृपया", "सकता", "सकते", "सकती", "हूँ", "होगा", "मिलेगा", "हाँ", "ज्यादा", "मौजूदा"
    ]
    hindi_score = sum(text.count(marker) for marker in hindi_markers)

    if marathi_score > hindi_score:
        return "mr"
    elif hindi_score > marathi_score:
        return "hi"
    else:
        if any(w in text for w in ["कर्ज", "हप्ता", "ईएमआय"]):
            return "mr"
        return "hi"


def extract_target_language(text: str) -> Optional[str]:
    """
    Extracts target language ('mr', 'hi', 'en') when user requests language change.
    Handles natural phrases in English, Hindi, and Marathi.
    """
    lower = text.lower()

    # Marathi switch phrases
    if any(k in lower for k in [
        "change language to marathi", "switch language to marathi", "set language to marathi",
        "change to marathi", "switch to marathi", "speak in marathi", "talk in marathi",
        "मराठी करा", "भाषा मराठी करा", "मराठी भाषा करा", "मराठीत बोला", "मराठी मध्ये", "मराठीत",
        "मराठी भाषा", "मराठी पाहिजे"
    ]):
        return "mr"

    # Hindi switch phrases
    if any(k in lower for k in [
        "change language to hindi", "switch language to hindi", "set language to hindi",
        "change to hindi", "switch to hindi", "speak in hindi", "talk in hindi",
        "हिंदी में बदलो", "हिंदी करो", "हिंदी भाषा", "भाषा हिंदी करो", "हिंदी में बताओ",
        "हिंदी में बात", "हिंदी में", "हिन्दी करो", "हिन्दी में बदलो"
    ]):
        return "hi"

    # English switch phrases
    if any(k in lower for k in [
        "change language to english", "switch language to english", "set language to english",
        "change to english", "switch to english", "speak in english", "talk in english",
        "अंग्रेजी में बदलो", "अंग्रेजी करो", "अंग्रेजी भाषा", "इंग्रजी करा", "इंग्लिश करा", "इंग्रजीत"
    ]):
        return "en"

    # General Regex: "change/switch/set language to/in (marathi|hindi|english)"
    m = re.search(r'(?:change|switch|set)\s*(?:the\s*)?language\s*(?:to|in)?\s*(marathi|hindi|english|mr|hi|en)', lower)
    if m:
        target = m.group(1)
        if "marathi" in target or target == "mr":
            return "mr"
        if "hindi" in target or target == "hi":
            return "hi"
        if "english" in target or target == "en":
            return "en"

    return None


def classify_intent(text: str, page_context: Optional[PageContext]) -> str:
    # 0. Check language change
    if extract_target_language(text) is not None:
        return "CHANGE_LANGUAGE"

    lower = text.lower()

    # Pay more EMI / Prepayment feasibility query
    if any(k in lower for k in [
        "pay more emi", "can i pay more", "increase emi", "pay higher emi",
        "how much emi can i pay", "extra emi", "how much?", "how much emi",
        "prepay", "prepayment", "जास्त ईएमआय", "अधिक ईएमआय", "ईएमआय वाढवू", "जास्त हप्ता",
        "ज्यादा ईएमआई", "अधिक ईएमआई", "ईएमआई बढ़ा", "ज्यादा किस्त", "अधिक किस्त"
    ]):
        return "PAY_MORE_EMI"

    # Loan action intent
    if any(k in lower for k in ["need a loan", "want a loan", "get a loan", "apply for", "borrow", "lakh", "afford", "can pay", "suggest a loan", "recommend a loan", "recommend loan"]):
        return "LOAN_ACTION"

    # Comparison intent
    if any(k in lower for k in ["compare", "comparison", "difference between", "which is better", "which loan is best", "explain this loan", "explain screen", "explain on screen"]):
        return "COMPARISON_EXPLANATION"

    # Navigation intent
    if any(k in lower for k in [
        "take me to", "navigate to", "open page", "go to", "show me", "view page",
        "open forecast", "go to forecast", "show forecast",
        "open optimizer", "go to optimizer", "show optimizer",
        "open recommendations", "go to recommendations", "show offers",
        "open profile", "go to profile",
        "घेऊन जा", "उघडा", "दाखवा", "चला", "ले चलो", "खोलो"
    ]):
        return "NAVIGATION"

    # Finance Q&A intent
    if any(k in lower for k in ["what is", "how does", "how is", "explain", "meaning of", "penalty", "prepayment", "reducing balance", "daily emi"]):
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

        # 0. Check language change request first (deterministic, instant response)
        target_lang = extract_target_language(req.message)
        if target_lang:
            messages = {
                "mr": "भाषा यशस्वीरित्या मराठीत बदलली आहे. मी तुम्हाला कर्ज, ईएमआय आणि वित्तामध्ये कशी मदत करू शकतो?",
                "hi": "भाषा सफलतापूर्वक हिंदी में बदल दी गई है। मैं आपकी ऋण, ईएमआई और वित्त संबंधी क्या सहायता कर सकता हूँ?",
                "en": "Language has been successfully changed to English. How can I assist you with your loans, EMIs, and finances today?"
            }
            reply = messages.get(target_lang, messages["en"])
            ui_action = UIAction(
                action_type="CHANGE_LANGUAGE",
                target_page=req.page_context.current_page if req.page_context else "dashboard",
                parameters={"language": target_lang}
            )
            response = AgentChatResponse(
                reply_text=reply,
                workflow_type="CHANGE_LANGUAGE",
                llm_used=False,
                ui_action=ui_action,
                suggested_prompts=(
                    ["माझे सक्रिय कर्ज दाखवा", "३० दिवसांचा अंदाज", "नवीन कर्ज शोधा"] if target_lang == "mr"
                    else (["मेरे सक्रिय ऋण दिखाओ", "३० दिनों का पूर्वानुमान", "नया ऋण खोजें"] if target_lang == "hi"
                    else ["Show my active loans", "Check 30-day forecast", "Recommend loans"])
                )
            )
            cls._save_turn(merchant_id, req.session_id or "default", [], req.message, reply)
            return response

        # 1. Deterministic Scope Gate Check (Reject off-topic questions without external API calls)
        in_scope, refusal_msg = check_financial_scope(req.message)
        if not in_scope:
            return AgentChatResponse(
                reply_text=refusal_msg or GENERIC_OUT_OF_SCOPE_RESPONSE,
                workflow_type="OUT_OF_SCOPE",
                llm_used=False,
                suggested_prompts=["I need a ₹1 lakh loan", "Compare top loans", "Check my cashflow forecast"]
            )

        # 2. Language Gateway: Detect Language (Marathi vs Hindi vs English)
        detected_lang = detect_query_language(req.message)
        is_devanagari = (detected_lang in ["mr", "hi"])
        normalized_english_message = req.message
        if is_devanagari:
            try:
                normalized_english_message = translate_single_text(req.message, source_lang=detected_lang, target_lang="en")
            except Exception as e:
                print(f"Input translation warning: {e}")

        history = get_session_history(merchant_id, req.session_id or "default")
        intent = classify_intent(normalized_english_message, req.page_context)

        # Financial data version for safe response caching
        data_version = f"cs_{profile.credit_score}_sales_{int(profile.monthly_sales_reference)}"

        # 3. Check Merchant-Scoped Response Cache (Language-Isolated)
        cache_key_msg = f"{detected_lang}:{req.message}"
        cached_payload = get_cached_ai_response(merchant_id, intent, cache_key_msg, data_version=data_version)
        if cached_payload:
            return AgentChatResponse(**cached_payload)

        # 4. If OpenAI API Key is present, attempt Responses API Workflow with GPT-5.6 Luna
        response = None
        if OpenAIResponsesAdapter.is_configured():
            try:
                # If merchant speaks in Hindi or Marathi, pass original message and set strict language directive!
                llm_prompt = req.message if is_devanagari else normalized_english_message
                response = cls._run_openai_workflow(req, intent, profile, history, llm_prompt, detected_lang=detected_lang)
            except Exception as e:
                print(f"OpenAI Responses API call failed ({str(e)}). Falling back to deterministic agent workflow.")

        # 5. Deterministic Agent Workflows (Works completely API-key-free!)
        if not response:
            req_copy = AgentChatRequest(
                merchant_id=req.merchant_id,
                message=normalized_english_message,
                session_id=req.session_id,
                page_context=req.page_context
            )
            response = cls._run_deterministic_workflow(req_copy, intent, profile, history, detected_lang=detected_lang)

            # Output Gateway for deterministic fallback:
            # If the user asked in Hindi or Marathi and the reply isn't already in Devanagari, translate it!
            if is_devanagari and not any('\u0900' <= c <= '\u097f' for c in response.reply_text):
                try:
                    translated_reply = translate_single_text(response.reply_text, source_lang="en", target_lang=detected_lang)
                    response.reply_text = translated_reply
                except Exception as e:
                    print(f"Output translation warning: {e}")

        # 6. Store in safe response cache
        try:
            set_cached_ai_response(
                merchant_id=merchant_id,
                intent=intent,
                message=cache_key_msg,
                response_payload=response.model_dump(),
                data_version=data_version
            )
        except Exception as e:
            print(f"Response cache save error: {e}")

        cls._save_turn(merchant_id, req.session_id or "default", history, req.message, response.reply_text)
        return response

    @classmethod
    def _run_deterministic_workflow(
        cls,
        req: AgentChatRequest,
        intent: str,
        profile: Any,
        history: List[Dict[str, str]],
        detected_lang: str = "en"
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

        # Workflow: PAY_MORE_EMI (Loan Optimization & Surplus Capacity)
        if intent == "PAY_MORE_EMI":
            opt = ToolRegistry.optimize_existing_loans(merchant_id)
            fc = ToolRegistry.get_cashflow_forecast(merchant_id, 30)
            avg_daily_cf = fc["avg_daily_net_cashflow"]
            curr_emi = opt["total_current_daily_emi"]
            surplus = round(avg_daily_cf - curr_emi, 2)
            active_cnt = opt["active_loans_count"]

            if surplus > 50:
                safe_additional = round(surplus * 0.75, 2)
                if detected_lang == "mr":
                    reply = (
                        f"**होय, आपण आपल्या सध्याच्या कर्जासाठी दररोजचा ईएमआय सहजपणे वाढवू शकता.**\n\n"
                        f"• **सध्याचा एकूण दैनिक ईएमआय:** ₹{curr_emi:,.2f}/दिवस ({active_cnt} सक्रिय कर्ज खाती)\n"
                        f"• **३० दिवसांचा अंदाजित दैनिक निव्वळ रोख प्रवाह:** ₹{avg_daily_cf:,.2f}/दिवस\n"
                        f"• **उपलब्ध दैनिक रोख प्रवाह शिल्लक (सरप्लस):** ₹{surplus:,.2f}/दिवस\n\n"
                        f"💡 **सल्लागार क्षमता:** आपण दैनंदिन हप्ता सुरक्षितपणे **₹{safe_additional:,.2f}/दिवस** पर्यंत वाढवू शकता, "
                        f"ज्यामुळे दैनंदिन कामासाठी सुरक्षित राखीव रक्कम शिल्लक राहील. "
                        f"दैनिक हप्ता वाढवल्याने कर्जाचा कालावधी जलद संपेल आणि व्याजात मोठी बचत होईल."
                    )
                elif detected_lang == "hi":
                    reply = (
                        f"**हाँ, आप अपने मौजूदा ऋणों के लिए दैनिक ईएमआई आराम से बढ़ा सकते हैं।**\n\n"
                        f"• **वर्तमान कुल दैनिक ईएमआई:** ₹{curr_emi:,.2f}/दिन ({active_cnt} सक्रिय ऋण खाते)\n"
                        f"• **30 दिनों का अनुमानित दैनिक शुद्ध कैश-फ्लो:** ₹{avg_daily_cf:,.2f}/दिन\n"
                        f"• **उपलब्ध दैनिक नकदी अधिशेष (सरप्लस):** ₹{surplus:,.2f}/दिन\n\n"
                        f"💡 **सलाहकार क्षमता:** आप सुरक्षित रूप से अपने दैनिक भुगतान को **₹{safe_additional:,.2f}/दिन** तक बढ़ा सकते हैं, "
                        f"जिससे अप्रत्याशित व्यावसायिक खर्चों के लिए पर्याप्त सुरक्षा बफर बना रहेगा। "
                        f"दैनिक भुगतान बढ़ाने से शेष ऋण अवधि तेजी से घटेगी और कुल ब्याज की भारी बचत होगी।"
                    )
                else:
                    reply = (
                        f"**Yes, you can comfortably pay more daily EMI towards your existing loans.**\n\n"
                        f"• **Current Total Daily EMI:** ₹{curr_emi:,.2f}/day across {active_cnt} active loan account(s)\n"
                        f"• **30-Day Projected Daily Net Cashflow:** ₹{avg_daily_cf:,.2f}/day\n"
                        f"• **Daily Cashflow Surplus Available:** ₹{surplus:,.2f}/day\n\n"
                        f"💡 **Advisory Capacity:** You can safely increase your daily payment by up to **₹{safe_additional:,.2f}/day**, "
                        f"leaving a healthy reserve buffer for operational fluctuations. "
                        f"Increasing daily payments reduces remaining loan tenure and substantially cuts total interest costs."
                    )
            else:
                if detected_lang == "mr":
                    reply = (
                        f"तुमच्या ३० दिवसांच्या अंदाजानुसार (₹{avg_daily_cf:,.2f}/दिवस) आणि सक्रिय दैनिक ईएमआय (₹{curr_emi:,.2f}/दिवस) पाहता, "
                        f"तुमचा शिल्लक रोख बफर फक्त ₹{max(0.0, surplus):,.2f}/दिवस आहे. "
                        f"रोख प्रवाहावर ताण येऊ नये म्हणून सध्या दैनिक ईएमआय वाढवणे योग्य नाही."
                    )
                elif detected_lang == "hi":
                    reply = (
                        f"आपके 30 दिनों के पूर्वानुमान (₹{avg_daily_cf:,.2f}/दिन) और सक्रिय दैनिक ईएमआई (₹{curr_emi:,.2f}/दिन) के आधार पर, "
                        f"आपका शेष नकदी बफर केवल ₹{max(0.0, surplus):,.2f}/दिन है। "
                        f"कैश-फ्लो पर दबाव से बचने के लिए फिलहाल दैनिक ईएमआई बढ़ाना उचित नहीं है।"
                    )
                else:
                    reply = (
                        f"Based on your 30-day forecast (₹{avg_daily_cf:,.2f}/day) and active daily EMI (₹{curr_emi:,.2f}/day), "
                        f"your remaining cash buffer is ₹{max(0.0, surplus):,.2f}/day. "
                        f"Increasing your daily EMI is not recommended right now to prevent cashflow strain."
                    )

            ui_action = UIAction(action_type="NAVIGATE", target_page="optimizer", parameters={})
            response = AgentChatResponse(
                reply_text=reply,
                workflow_type="OPTIMIZATION",
                llm_used=False,
                ui_action=ui_action,
                suggested_prompts=(
                    ["कर्ज ऑप्टिमायझर दाखवा", "३० दिवसांचा रोख प्रवाह अंदाज", "कर्ज उत्पादने"] if detected_lang == "mr"
                    else (["ऋण अनुकूलक दिखाओ", "30-दिवसीय कैश-फ्लो पूर्वानुमान", "ऋण उत्पाद"] if detected_lang == "hi"
                    else ["Take me to loan optimizer", "Show 30-day forecast", "Compare all loan products"])
                )
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
        history: List[Dict[str, str]],
        reasoning_message: str,
        detected_lang: str = "en"
    ) -> AgentChatResponse:
        """Execute LLM workflow using OpenAI Responses API with GPT-5.6 Luna, structured tools, and bounded context."""
        merchant_id = req.merchant_id

        # Pre-fetch merchant financial summary to bound the prompt context
        opt = ToolRegistry.optimize_existing_loans(merchant_id)
        fc = ToolRegistry.get_cashflow_forecast(merchant_id, 30)

        daily_surplus = round(fc['avg_daily_net_cashflow'] - opt['total_current_daily_emi'], 2)
        safe_additional_emi = max(0.0, round(daily_surplus * 0.75, 2))

        # Dynamic Language Directive based on detected query language
        lang_instruction = ""
        if detected_lang == "mr":
            lang_instruction = (
                "\n\nCRITICAL LANGUAGE DIRECTIVE: The merchant is asking in Marathi (मराठी). "
                "You MUST formulate your entire final response directly in natural, polite, grammatically correct Marathi (मराठी). "
                "Do NOT respond in English or Hindi. Use standard Marathi banking terms: मुद्दल (Principal), दैनिक हप्ता / ईएमआय (Daily EMI), व्याजदर (Interest Rate), कालावधी (Tenure), रोख प्रवाह (Cashflow), बचत (Savings)."
            )
        elif detected_lang == "hi":
            lang_instruction = (
                "\n\nCRITICAL LANGUAGE DIRECTIVE: The merchant is asking in Hindi (हिंदी). "
                "You MUST formulate your entire final response directly in natural, polite, grammatically correct Hindi (हिंदी). "
                "Do NOT respond in English or Marathi. Use standard Hindi banking terms: मूलधन (Principal), दैनिक किस्त / ईएमआई (Daily EMI), ब्याज दर (Interest Rate), अवधि (Tenure), नकदी प्रवाह (Cashflow), बचत (Savings)."
            )
        else:
            lang_instruction = (
                "\n\nCRITICAL LANGUAGE DIRECTIVE: The merchant is asking in English. "
                "You MUST formulate your entire response in clear, professional English. Do NOT respond in Hindi or Marathi."
            )

        system_prompt = (
            f"You are the LoanIQ AI Financial Assistant for Indian small businesses. "
            f"Current Merchant: {profile.business_name} (ID: {merchant_id}, City: {profile.city}, Type: {profile.merchant_type}). "
            f"Monthly Sales: ₹{profile.monthly_sales_reference:,.0f}, Credit Score: {profile.credit_score}. "
            f"Active Loans: {opt['active_loans_count']}, Total Remaining Debt: ₹{opt['total_remaining_principal']:,.2f}, "
            f"Existing Daily EMI: ₹{opt['total_current_daily_emi']:.2f}. "
            f"30-day Avg Daily Net Cashflow: ₹{fc['avg_daily_net_cashflow']:.2f}. "
            f"Daily Cashflow Surplus above Existing EMI: ₹{daily_surplus:.2f}/day. "
            f"Safe Additional Daily EMI Capacity: ₹{safe_additional_emi:.2f}/day. "
            f"Bound all responses strictly to LoanIQ's product rules, deterministic calculations, and bounded finance knowledge. "
            f"NEVER claim guaranteed loan approval. Explain that acceptance probabilities are model estimates. "
            f"If the user asks for a loan amount or EMI, extract the values and call tool 'navigate_ui' to 'recommendations' with prefilled values. "
            f"If the user asks to navigate (e.g. 'take me to forecast', 'take me to optimizer', 'take me to loans', 'take me to profile', 'take me to dashboard', or in Marathi 'मला अंदाज पृष्ठावर घेऊन जा', or in Hindi 'मुझे पूर्वानुमान पेज पर ले चलो'), call baseline MCP tool 'navigate_ui' with that page. "
            f"If the merchant asks 'can I pay more emi for my current loan? how much?' or in Marathi 'मी माझ्या सध्याच्या कर्जासाठी अधिक ईएमआय भरू शकतो का? किती?' or in Hindi 'क्या मैं अपने मौजूदा लोन के लिए ज्यादा ईएमआई भर सकता हूँ? कितनी?': "
            f"confirm that their 30-day projected net cashflow is ₹{fc['avg_daily_net_cashflow']:,.2f}/day and current total daily EMI is ₹{opt['total_current_daily_emi']:,.2f}/day. "
            f"State clearly that they have an uncommitted daily surplus of ₹{daily_surplus:,.2f}/day and can safely afford up to ₹{safe_additional_emi:,.2f}/day in extra daily EMI to accelerate loan closure and save significant interest expense. "
            f"{lang_instruction}"
        )

        page_ctx_dict = req.page_context.model_dump() if req.page_context else None

        response = OpenAIResponsesAdapter.execute_responses_workflow(
            merchant_id=merchant_id,
            user_message=reasoning_message,
            system_prompt=system_prompt,
            conversation_history=history,
            page_context=page_ctx_dict
        )
        return response

    @classmethod
    def _save_turn(cls, merchant_id: str, session_id: str, history: List[Dict[str, str]], user_msg: str, assistant_msg: str):
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        save_session_history(merchant_id, session_id, history[-20:])
