"""
MCP Tool Registry and Execution Engine for LoanIQ.
Exposes the 12 required MCP tools backed by shared domain services with merchant isolation,
parameter validation, and audit logging.
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.services.agent_service import ToolRegistry, ALLOWLISTED_PAGES
from backend.services.merchant_service import get_all_merchant_ids
from backend.database import log_tool_call


# Tool definitions metadata (MCP standard schema format)
MCP_TOOL_DEFINITIONS = [
    {
        "name": "get_merchant_profile",
        "description": "Fetch verified business profile, credit score, and baseline reference data for a merchant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string", "description": "Demo Merchant ID (e.g. M001..M004)"}
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "get_merchant_loans",
        "description": "Retrieve active or completed loan account records for a merchant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string", "description": "Merchant ID"},
                "status": {"type": "string", "enum": ["active", "completed", "all"], "default": "all"}
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "get_loan_products",
        "description": "List all 15 fictional loan products from the catalog with lender details and rate terms.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "check_product_eligibility",
        "description": "Evaluate explicit product rules (sales, business age, credit score, amount, tenure) for a merchant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "loan_id": {"type": "string"},
                "requested_amount": {"type": "number"},
                "tenure_days": {"type": "integer"}
            },
            "required": ["merchant_id", "loan_id", "requested_amount", "tenure_days"]
        }
    },
    {
        "name": "predict_loan_acceptance",
        "description": "Estimate historical lender acceptance probability using Calibrated Random Forest model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "loan_id": {"type": "string"},
                "requested_amount": {"type": "number"},
                "tenure_days": {"type": "integer"}
            },
            "required": ["merchant_id", "loan_id", "requested_amount", "tenure_days"]
        }
    },
    {
        "name": "recommend_loans",
        "description": "Evaluate and multi-factor rank loan products for a merchant based on eligibility, likelihood, and affordability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "requested_amount": {"type": "number", "default": 100000.0},
                "max_daily_emi": {"type": "number"}
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "compare_loans",
        "description": "Compare selected loan products side-by-side on EMI, total interest, fees, and acceptance likelihood.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "loan_ids": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["merchant_id", "loan_ids"]
        }
    },
    {
        "name": "get_cashflow_forecast",
        "description": "Retrieve daily sales inflow, expense, net cashflow, and closing cash balance forecasts for 3, 7, 15, or 30 days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "horizon_days": {"type": "integer", "enum": [3, 7, 15, 30], "default": 30}
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "simulate_loan",
        "description": "Simulate an additional loan against projected cash flow and evaluate safety-buffer breaches.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "loan_amount": {"type": "number"},
                "tenure_days": {"type": "integer"},
                "annual_interest_rate": {"type": "number"},
                "processing_fee_pct": {"type": "number", "default": 1.0}
            },
            "required": ["merchant_id", "loan_amount", "tenure_days", "annual_interest_rate"]
        }
    },
    {
        "name": "optimize_existing_loans",
        "description": "Aggregate active loan obligations, compare with cash flow, and recommend debt consolidation/refinancing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"}
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "get_page_context",
        "description": "Fetch authorized on-screen context data for a specific page to support AI explanation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "page_name": {"type": "string"},
                "selected_ids": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["merchant_id", "page_name"]
        }
    },
    {
        "name": "navigate_ui",
        "description": "Validate and generate a client navigation instruction to an allowlisted UI screen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"},
                "page": {"type": "string"},
                "parameters": {"type": "object"}
            },
            "required": ["merchant_id", "page"]
        }
    }
]


def execute_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    valid_merchants = get_all_merchant_ids()
    merchant_id = arguments.get("merchant_id", "")

    # Security check: validate merchant ID for merchant-scoped tools
    if tool_name != "get_loan_products":
        if not merchant_id or merchant_id not in valid_merchants:
            err = f"Security Error: Invalid or missing merchant_id '{merchant_id}'."
            log_tool_call(tool_name, merchant_id, json.dumps(arguments), "REJECTED")
            return {"error": err}

    try:
        if tool_name == "get_merchant_profile":
            res = ToolRegistry.get_merchant_profile(merchant_id)
        elif tool_name == "get_merchant_loans":
            res = ToolRegistry.get_merchant_loans(merchant_id, arguments.get("status", "all"))
        elif tool_name == "get_loan_products":
            res = ToolRegistry.get_loan_products()
        elif tool_name == "check_product_eligibility":
            res = ToolRegistry.check_product_eligibility(
                merchant_id,
                arguments.get("loan_id", ""),
                float(arguments.get("requested_amount", 0)),
                int(arguments.get("tenure_days", 0))
            )
        elif tool_name == "predict_loan_acceptance":
            res = ToolRegistry.predict_loan_acceptance(
                merchant_id,
                arguments.get("loan_id", ""),
                float(arguments.get("requested_amount", 0)),
                int(arguments.get("tenure_days", 0))
            )
        elif tool_name == "recommend_loans":
            res = ToolRegistry.recommend_loans(
                merchant_id,
                float(arguments.get("requested_amount", 100000.0)),
                float(arguments["max_daily_emi"]) if arguments.get("max_daily_emi") else None
            )
        elif tool_name == "compare_loans":
            res = ToolRegistry.compare_loans(merchant_id, arguments.get("loan_ids", []))
        elif tool_name == "get_cashflow_forecast":
            res = ToolRegistry.get_cashflow_forecast(merchant_id, int(arguments.get("horizon_days", 30)))
        elif tool_name == "simulate_loan":
            res = ToolRegistry.simulate_loan(
                merchant_id,
                float(arguments.get("loan_amount", 0)),
                int(arguments.get("tenure_days", 365)),
                float(arguments.get("annual_interest_rate", 15.0)),
                float(arguments.get("processing_fee_pct", 1.0))
            )
        elif tool_name == "optimize_existing_loans":
            res = ToolRegistry.optimize_existing_loans(merchant_id)
        elif tool_name == "get_page_context":
            page = arguments.get("page_name", "")
            if page not in ALLOWLISTED_PAGES:
                return {"error": f"Invalid page '{page}'. Allowlisted pages: {ALLOWLISTED_PAGES}"}
            res = ToolRegistry.get_page_context(merchant_id, page, arguments.get("selected_ids"))
        elif tool_name == "navigate_ui":
            page = arguments.get("page", "")
            if page not in ALLOWLISTED_PAGES:
                return {"error": f"Invalid page '{page}'. Allowlisted pages: {ALLOWLISTED_PAGES}"}
            action = ToolRegistry.navigate_ui(merchant_id, page, arguments.get("parameters", {}))
            res = action.model_dump()
        else:
            res = {"error": f"Unknown tool '{tool_name}'."}

        log_tool_call(tool_name, merchant_id, json.dumps(arguments), "SUCCESS")
        return res
    except Exception as e:
        log_tool_call(tool_name, merchant_id, json.dumps(arguments), f"FAILED: {str(e)}")
        return {"error": f"Tool execution error: {str(e)}"}

