from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_mcp_list_tools():
    resp = client.get("/api/mcp/tools")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    tool_names = [t["name"] for t in tools]
    expected_tools = [
        "get_merchant_profile", "get_merchant_loans", "get_loan_products",
        "check_product_eligibility", "predict_loan_acceptance", "recommend_loans",
        "compare_loans", "get_cashflow_forecast", "simulate_loan",
        "optimize_existing_loans", "get_page_context", "navigate_ui"
    ]
    for et in expected_tools:
        assert et in tool_names


def test_mcp_call_tool_valid_and_security_check():
    # Valid call
    resp = client.post("/api/mcp/call", json={
        "name": "get_merchant_profile",
        "arguments": {"merchant_id": "M001"}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["isError"] is False
    assert data["result"]["merchant_id"] == "M001"

    # Security check: invalid merchant ID must be rejected
    resp_sec = client.post("/api/mcp/call", json={
        "name": "get_merchant_profile",
        "arguments": {"merchant_id": "ATTACKER_ID"}
    })
    assert resp_sec.status_code == 200
    assert resp_sec.json()["isError"] is True


def test_mcp_json_rpc_transport():
    # Initialize
    resp_init = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1
    })
    assert resp_init.status_code == 200
    assert resp_init.json()["result"]["serverInfo"]["name"] == "LoanIQ-MCP-Server"

    # Call tool via JSON-RPC
    resp_call = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_cashflow_forecast",
            "arguments": {"merchant_id": "M001", "horizon_days": 7}
        },
        "id": 2
    })
    assert resp_call.status_code == 200
    assert resp_call.json()["result"]["isError"] is False

