from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_check():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_model_status():
    resp = client.get("/api/model/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["forecaster_loaded"] is True
    assert data["acceptance_model_loaded"] is True
    assert data["predictions_available"] is True
    assert "integrations_status" in data


def test_demo_auth():
    # Valid login
    resp = client.post("/api/auth/login", json={"merchant_id": "M001"})
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    assert resp.json()["merchant_id"] == "M001"

    # Invalid login rejected
    resp_invalid = client.post("/api/auth/login", json={"merchant_id": "INVALID_999"})
    assert resp_invalid.status_code == 401

    # Logout
    resp_logout = client.post("/api/auth/logout")
    assert resp_logout.status_code == 200


def test_merchant_profile_and_loans():
    resp = client.get("/api/merchants/M001/profile")
    assert resp.status_code == 200
    assert resp.json()["merchant_id"] == "M001"

    resp_loans = client.get("/api/merchants/M001/loans?status=active")
    assert resp_loans.status_code == 200
    loans = resp_loans.json()
    assert len(loans) == 2


def test_merchant_forecast_horizons():
    for h in [3, 7, 15, 30]:
        resp = client.get(f"/api/merchants/M001/forecast?horizon={h}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["horizon_selected"] == h
        assert len(data["rows"]) == h


def test_loan_recommendations_and_comparison():
    resp = client.get("/api/merchants/M001/recommendations?requested_amount=100000&tenure_days=365")
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) == 15

    # Comparison
    comp_resp = client.post("/api/loans/compare", json={
        "merchant_id": "M001",
        "loan_ids": ["LP001", "LP002"],
        "requested_amount": 100000.0,
        "tenure_days": 365
    })
    assert comp_resp.status_code == 200
    data = comp_resp.json()
    assert len(data["products"]) == 2


def test_agent_chat_deterministic():
    # Chat without external API key must still work and route intents
    from unittest.mock import patch
    with patch("backend.services.agent_service.OpenAIResponsesAdapter.is_configured", return_value=False):
        resp = client.post("/api/assistant/chat", json={
            "merchant_id": "M001",
            "message": "I need a 50,000 loan and can pay 300 daily EMI"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_type"] == "LOAN_ACTION"
        assert data["ui_action"] is not None
        assert data["ui_action"]["target_page"] == "recommendations"


def test_translation_endpoint():
    resp = client.post("/api/translation/translate", json={
        "source_lang": "en",
        "target_lang": "en",
        "strings": {"greeting": "Hello", "farewell": "Goodbye"}
    })
    assert resp.status_code == 200
    assert resp.json()["translations"]["greeting"] == "Hello"


def test_translation_caching_and_graceful_fallback():
    # Calling translation to Marathi/Hindi without API key should fall back to original strings
    from unittest.mock import patch
    with patch("backend.services.translation.settings.SARVAM_API_KEY", ""):
        with patch("backend.services.translation.settings.GOOGLE_TRANSLATE_API_KEY", ""):
            resp = client.post("/api/translation/translate", json={
                "source_lang": "en",
                "target_lang": "mr",
                "strings": {"uncached_key_1": "Uncached Test Text 999", "uncached_key_2": "Uncached Dashboard 888"}
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "uncached_key_1" in data["translations"]
            # Without API key and uncached, it returns original strings gracefully without 500 error
            assert data["translations"]["uncached_key_1"] == "Uncached Test Text 999"


def test_agent_various_natural_language_queries():
    from unittest.mock import patch
    with patch("backend.services.agent_service.OpenAIResponsesAdapter.is_configured", return_value=False):
        # Lakh pattern
        resp1 = client.post("/api/assistant/chat", json={
            "merchant_id": "M001",
            "message": "I need a 5 lakh loan with 2000 daily EMI"
        })
        assert resp1.status_code == 200
        assert resp1.json()["extracted_data"]["amount"] == 500000.0
        assert resp1.json()["extracted_data"]["emi"] == 2000.0

        # Finance Q&A query
        resp2 = client.post("/api/assistant/chat", json={
            "merchant_id": "M001",
            "message": "What is daily EMI and how does it work?"
        })
        assert resp2.status_code == 200
        assert "Daily EMI" in resp2.json()["reply_text"]
        assert resp2.json()["workflow_type"] == "FINANCE_QA"
