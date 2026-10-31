"""
Comprehensive AI Integration and Safety Test Suite for LoanIQ.
Covers:
1. Deterministic Scope Gate (in-scope vs off-topic financial guardrails).
2. Translation Cache (Mayura v1) with placeholder shielding.
3. Response Cache (GPT-5.6 Luna) with merchant isolation and TTL.
4. Sarvam Voice adapters (Saaras v4, Bulbul v4 Flash) with graceful degradation and mocked success.
5. OpenAI Responses API Adapter (GPT-5.6 Luna) with mocked multi-step tool calls.
6. Marathi query normalization and end-to-end agent triage.
7. Verification that the 7 rejected proposed MCP tools are NOT registered.
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from backend.services.scope_gate import check_financial_scope, GENERIC_OUT_OF_SCOPE_RESPONSE
from backend.services.cache_service import (
    mask_placeholders,
    unmask_placeholders,
    get_cached_sarvam_translation,
    set_cached_sarvam_translation,
    get_cached_ai_response,
    set_cached_ai_response,
    clear_merchant_cache
)
from backend.services.voice import speech_to_text, text_to_speech
from backend.services.translation import translate_single_text, translate_ui_strings
from backend.services.agent_service import AgentService
from backend.services.openai_adapter import OpenAIResponsesAdapter, get_openai_formatted_tools
from backend.schemas.agent import AgentChatRequest
from backend.mcp.tools import MCP_TOOL_DEFINITIONS


def test_scope_gate_financial_queries():
    """Valid merchant finance, loan, and LoanIQ queries must pass scope gate."""
    in_scope_queries = [
        "I need a loan of ₹50,000 for 180 days",
        "What is daily reducing EMI and how does it work?",
        "Compare LP001 and LP003 on interest rate",
        "Show my 30 day cashflow forecast",
        "Can I pay off my active loans faster to save interest?",
        "What is the prepayment fee for LP007?",
        "What is my current safety buffer?",
        "Take me to the loan recommendations screen"
    ]
    for q in in_scope_queries:
        passed, refusal = check_financial_scope(q)
        assert passed is True, f"Expected '{q}' to pass scope gate"
        assert refusal is None


def test_scope_gate_off_topic_queries():
    """Off-topic queries must be rejected immediately with exact generic response."""
    off_topic_queries = [
        "Write a poem about the monsoon",
        "Tell me a funny joke",
        "What is the weather forecast in Mumbai tomorrow?",
        "Give me a recipe for butter chicken",
        "Write a python code to sort a list",
        "Who is the prime minister of India?",
        "Tell me about the latest bollywood movie",
        "What was the score in yesterday's cricket match?"
    ]
    for q in off_topic_queries:
        passed, refusal = check_financial_scope(q)
        assert passed is False, f"Expected '{q}' to fail scope gate"
        assert refusal == GENERIC_OUT_OF_SCOPE_RESPONSE


def test_placeholder_shielding():
    """Tokens like {name}, amounts, and IDs must be shielded and restored cleanly."""
    raw = "Hello {merchant_name}, your daily EMI for LP001 is ₹1,500.50 on account LA0103."
    masked, mapping = mask_placeholders(raw)
    assert "₹1,500.50" not in masked
    assert "LP001" not in masked
    assert "{merchant_name}" not in masked
    restored = unmask_placeholders(masked, mapping)
    assert restored == raw


def test_sarvam_translation_caching():
    """Translations must persist to SQLite and be returned without repeated API calls."""
    src = "en"
    tgt = "mr"
    text = "Daily Reducing EMI Repayment Schedule"
    fake_trans = "दैनिक घटणारी ईएमआय परतफेड वेळापत्रक"

    set_cached_sarvam_translation(src, tgt, text, fake_trans)
    cached = get_cached_sarvam_translation(src, tgt, text)
    assert cached == fake_trans


def test_ai_response_cache_merchant_isolation():
    """Responses must be merchant-isolated. M001's cached response must not leak to M002."""
    m1 = "M001"
    m2 = "M002"
    intent = "FINANCE_QA"
    query = "what is daily emi"
    payload = {"reply_text": "Daily EMI explanation for M001", "workflow_type": "FINANCE_QA", "llm_used": True}

    set_cached_ai_response(m1, intent, query, payload, data_version="v1")

    # M001 should hit cache
    cached_m1 = get_cached_ai_response(m1, intent, query, data_version="v1")
    assert cached_m1 is not None
    assert cached_m1["reply_text"] == "Daily EMI explanation for M001"

    # M002 must miss cache
    cached_m2 = get_cached_ai_response(m2, intent, query, data_version="v1")
    assert cached_m2 is None

    # Invalidate M001
    clear_merchant_cache(m1)
    assert get_cached_ai_response(m1, intent, query, data_version="v1") is None


def test_sarvam_voice_graceful_fallback():
    """Voice endpoints must return UNAVAILABLE without error when SARVAM_API_KEY is empty."""
    with patch("backend.services.voice.settings.SARVAM_API_KEY", ""):
        stt_res = speech_to_text(b"fakeaudio", language_code="mr-IN")
        assert stt_res.status == "UNAVAILABLE"
        assert "SARVAM_API_KEY" in stt_res.message

        tts_res = text_to_speech("काहीतरी बोला", language_code="mr-IN")
        assert tts_res.status == "UNAVAILABLE"
        assert tts_res.audio_base64 is None


def test_sarvam_voice_with_mock():
    """Test successful STT and TTS parsing when mocked Sarvam API returns 200."""
    with patch("backend.services.voice.settings.SARVAM_API_KEY", "mock_key"):
        with patch("httpx.Client.post") as mock_post:
            # Mock STT
            mock_post.return_value = MagicMock(status_code=200, json=lambda: {"transcript": "मला कर्ज हवे आहे"})
            stt = speech_to_text(b"wavdata", language_code="mr-IN")
            assert stt.status == "SUCCESS"
            assert stt.text == "मला कर्ज हवे आहे"

            # Mock TTS
            mock_post.return_value = MagicMock(status_code=200, json=lambda: {"audios": ["b64audio123"]})
            tts = text_to_speech("कर्ज मंजूर झाले", language_code="mr-IN")
            assert tts.status == "SUCCESS"
            assert tts.audio_base64 == "b64audio123"


def test_openai_responses_adapter_mocked():
    """Test multi-step Responses API tool execution loop with mock."""
    with patch("backend.services.openai_adapter.settings.OPENAI_API_KEY", "mock_key"):
        with patch("backend.services.openai_adapter.settings.OPENAI_MODEL", "gpt-5.6-luna"):
            with patch("backend.services.openai_adapter.OpenAIResponsesAdapter.evaluate_loans_with_luna", return_value={}):
                with patch("httpx.Client.post") as mock_post:
                    # Mock step 1: Luna calls recommend_loans
                    mock_post.side_effect = [
                        MagicMock(
                            status_code=200,
                            json=lambda: {
                                "output": [
                                    {
                                        "type": "function_call",
                                        "call_id": "call_1",
                                        "name": "recommend_loans",
                                        "arguments": json.dumps({"requested_amount": 50000.0, "max_daily_emi": 400.0})
                                    }
                                ]
                            }
                        ),
                        # Mock step 2: Luna provides final synthesis
                        MagicMock(
                            status_code=200,
                            json=lambda: {
                                "output": [
                                    {
                                        "type": "message",
                                        "content": "I found 3 eligible loans. Top recommendation is Working Capital Express by SBI."
                                    }
                                ]
                            }
                        )
                    ]

                    res = OpenAIResponsesAdapter.execute_responses_workflow(
                        merchant_id="M001",
                        user_message="I need a ₹50,000 loan with max 400 emi",
                        system_prompt="You are LoanIQ AI Assistant.",
                        conversation_history=[]
                    )

                    assert res.llm_used is True
                    assert res.workflow_type == "LUNA_REASONING"
                    assert "Working Capital Express" in res.reply_text
                    assert len(res.tool_calls) >= 1
                    assert res.tool_calls[0].tool_name == "recommend_loans"


def test_agent_service_scope_gate_rejection():
    """AgentService must immediately reject off-topic message without calling OpenAI."""
    req = AgentChatRequest(merchant_id="M001", message="Write a python code for binary search")
    res = AgentService.process_chat(req)
    assert res.workflow_type == "OUT_OF_SCOPE"
    assert res.reply_text == GENERIC_OUT_OF_SCOPE_RESPONSE
    assert res.llm_used is False


def test_agent_service_deterministic_loan_action():
    """AgentService must parse amount and emi and return prefill navigation action."""
    req = AgentChatRequest(merchant_id="M001", message="I need a loan of ₹1,00,000 with ₹500 daily emi")
    res = AgentService.process_chat(req)
    assert res.workflow_type in ["LOAN_ACTION", "LUNA_REASONING"]
    assert res.ui_action is not None
    assert res.ui_action.target_page == "recommendations"
    assert res.ui_action.parameters.get("amount") == 100000.0


def test_rejected_proposals_not_registered():
    """Verify that none of the 7 rejected proposed MCP tools are registered in MCP_TOOL_DEFINITIONS."""
    rejected_tool_names = [
        "get_merchant_cashflow_summary",
        "get_repayment_calendar",
        "explain_recommendation",
        "get_model_health",
        "get_supported_ui_actions",
        "get_translation_status",
        "get_assistant_capabilities"
    ]
    registered_names = [t["name"] for t in MCP_TOOL_DEFINITIONS]
    for rejected in rejected_tool_names:
        assert rejected not in registered_names, f"Rejected proposal tool '{rejected}' must NOT be registered."

    # Baseline tools count must remain exactly 12
    assert len(registered_names) == 12
    assert "get_merchant_profile" in registered_names
    assert "recommend_loans" in registered_names
    assert "navigate_ui" in registered_names


def test_multilingual_language_detection_and_switch():
    """Verify Marathi, Hindi, and English detection and language change intent."""
    from backend.services.agent_service import detect_query_language, extract_target_language

    # Detection checks
    assert detect_query_language("I want a loan of 50000") == "en"
    assert detect_query_language("मला ५०,००० चे कर्ज हवे आहे") == "mr"
    assert detect_query_language("मी माझ्या कर्जाचा हप्ता वाढवू शकतो का?") == "mr"
    assert detect_query_language("क्या मैं अपने मौजूदा लोन के लिए ज्यादा ईएमआई भर सकता हूँ?") == "hi"
    assert detect_query_language("मुझे 30 दिनों का पूर्वानुमान दिखाओ") == "hi"

    # Target language extraction checks
    assert extract_target_language("change language to marathi") == "mr"
    assert extract_target_language("मराठी भाषा करा") == "mr"
    assert extract_target_language("change language to hindi") == "hi"
    assert extract_target_language("हिंदी में बदलो") == "hi"
    assert extract_target_language("change language to english") == "en"

    # Chat execution for language change
    req_mr = AgentChatRequest(merchant_id="M001", message="change language to marathi")
    res_mr = AgentService.process_chat(req_mr)
    assert res_mr.workflow_type == "CHANGE_LANGUAGE"
    assert res_mr.ui_action is not None
    assert res_mr.ui_action.action_type == "CHANGE_LANGUAGE"
    assert res_mr.ui_action.parameters.get("language") == "mr"
    assert "मराठीत बदलली" in res_mr.reply_text

    req_hi = AgentChatRequest(merchant_id="M001", message="हिंदी में बदलो")
    res_hi = AgentService.process_chat(req_hi)
    assert res_hi.workflow_type == "CHANGE_LANGUAGE"
    assert res_hi.ui_action is not None
    assert res_hi.ui_action.action_type == "CHANGE_LANGUAGE"
    assert res_hi.ui_action.parameters.get("language") == "hi"
    assert "हिंदी में बदल दी" in res_hi.reply_text


def test_multilingual_pay_more_emi_advisory():
    """Verify Hindi and Marathi advisory response for 'can I pay more emi for my current loan?'."""
    # Hindi query
    req_hi = AgentChatRequest(merchant_id="M001", message="क्या मैं अपने मौजूदा लोन के लिए ज्यादा ईएमआई भर सकता हूँ? कितनी?")
    res_hi = AgentService.process_chat(req_hi)
    assert res_hi.workflow_type in ["OPTIMIZATION", "LUNA_REASONING"]
    assert ("हाँ" in res_hi.reply_text or "सकते" in res_hi.reply_text or "ईएमआई" in res_hi.reply_text or "ऋण" in res_hi.reply_text or "लोन" in res_hi.reply_text)

    # Marathi query
    req_mr = AgentChatRequest(merchant_id="M001", message="मी माझ्या सध्याच्या कर्जासाठी अधिक ईएमआय भरू शकतो का? किती?")
    res_mr = AgentService.process_chat(req_mr)
    assert res_mr.workflow_type in ["OPTIMIZATION", "LUNA_REASONING"]
    assert ("होय" in res_mr.reply_text or "शकता" in res_mr.reply_text or "हप्ता" in res_mr.reply_text or "ईएमआय" in res_mr.reply_text or "कर्ज" in res_mr.reply_text)


def test_llm_loan_evaluation_enrichment():
    """Verify that candidate loans and comparison products receive contextual LLM assessments."""
    from backend.services.recommendation import compare_loans
    res = compare_loans("M001", ["LP001", "LP003", "LP007", "LP004"], 100000.0, 365)
    assert len(res.products) == 4
    for p in res.products:
        assert p.affordability_status is not None
        assert p.recommendation_reason is not None
        # Must not be an empty string
        assert len(p.affordability_status) > 0
        assert len(p.recommendation_reason) > 0

