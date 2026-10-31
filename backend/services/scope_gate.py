"""
Deterministic Scope Gate for LoanIQ.
Enforces Section 9 & ai_prompt.md Section 3:
- Rejects general knowledge, coding, entertainment, politics, poetry, homework, and unrelated chat.
- Immediately returns the exact generic refusal without invoking OpenAI or Sarvam APIs.
"""

import re
from typing import Tuple, Optional

GENERIC_OUT_OF_SCOPE_RESPONSE = "Sorry, I can only assist with merchant finance, loans, repayments and LoanIQ services."

# In-scope finance and LoanIQ terms
FINANCE_TERMS = {
    "loan", "loans", "emi", "interest", "apr", "rate", "credit", "score", "repay", "repayment",
    "prepayment", "processing", "fee", "fees", "borrow", "borrowing", "lakh", "lac", "inr", "rupees",
    "cashflow", "cash flow", "sales", "expense", "expenses", "inflow", "balance", "forecast",
    "trajectory", "optimizer", "optimization", "accelerate", "consolidation", "refinance",
    "merchant", "business", "turnover", "buffer", "liquidity", "recommend", "recommendation",
    "compare", "comparison", "lender", "product", "lp001", "lp002", "lp003", "lp004", "lp005",
    "lp006", "lp007", "lp008", "lp009", "lp010", "lp011", "lp012", "lp013", "lp014", "lp015",
    "tenure", "principal", "debt", "obligation", "payoff", "pay off", "reducing balance",
    "loaniq", "dashboard", "navigate", "page", "screen", "profile", "history", "help",
    "hello", "hi", "namaste", "hey", "good morning", "good evening"
}

# Explicitly out-of-scope terms (general knowledge, coding, entertainment, trivia, politics)
OUT_OF_SCOPE_PATTERNS = [
    r"\b(?:poem|poetry|rhyme|haiku)\b",
    r"\b(?:joke|riddle|funny story)\b",
    r"\b(?:weather|temperature|forecast for tomorrow in)\b",
    r"\b(?:recipe|cook|cooking|ingredients)\b",
    r"\b(?:python code|javascript|html code|write a function|debug my code|c\+\+|java code|sql query for)\b",
    r"\b(?:movie|actor|actress|cinema|bollywood|hollywood|song|lyrics)\b",
    r"\b(?:cricket|ipl|football|fifa|world cup|match score|sports)\b",
    r"\b(?:election|prime minister|president|political party|politics|vote)\b",
    r"\b(?:capital of|who is|who was|biography of|history of world war)\b",
    r"\b(?:homework|essay on|write an essay|solve this math equation)\b",
    r"\b(?:game|gaming|play a game)\b"
]


def check_financial_scope(message: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether a merchant message is within LoanIQ financial scope.
    Returns:
        (True, None) if in-scope.
        (False, GENERIC_OUT_OF_SCOPE_RESPONSE) if out-of-scope.
    """
    if not message or not message.strip():
        return True, None

    text = message.strip().lower()

    # 1. Check for explicit out-of-scope trigger patterns
    for pat in OUT_OF_SCOPE_PATTERNS:
        if re.search(pat, text):
            # If the user explicitly asks for code, jokes, weather, recipes etc.
            # verify they are not asking a finance question that happened to match
            has_strong_finance = any(term in text for term in [
                "daily emi", "loan", "repay", "interest rate", "cashflow forecast",
                "borrow", "prepayment fee", "reducing balance", "sanctioned"
            ])
            if not has_strong_finance:
                return False, GENERIC_OUT_OF_SCOPE_RESPONSE

    # 2. Extract words and check if query has finance/LoanIQ context
    words = set(re.findall(r'\b[a-z0-9_\-\.\₹]+\b', text))
    has_finance_context = any(term in text for term in FINANCE_TERMS) or bool(words.intersection(FINANCE_TERMS))

    # Also check numbers or amounts like "50000", "₹5 lakh"
    has_amount = bool(re.search(r'(?:₹|rs\.?|inr)?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:lakh|lac|k)?', text))

    if has_finance_context or (has_amount and len(words) <= 6):
        return True, None

    # If it's a very long query with completely non-financial content
    if len(words) > 4 and not has_finance_context and not has_amount:
        return False, GENERIC_OUT_OF_SCOPE_RESPONSE

    # Fallback to in-scope for short or ambiguous conversational greetings
    return True, None

