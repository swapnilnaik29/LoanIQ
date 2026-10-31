"""
OpenAI Responses API Adapter for LoanIQ.
Integrates GPT-5.6 Luna via the OpenAI Responses API (POST /v1/responses).
Enforces:
- Model: gpt-5.6-luna (no silent escalation)
- Structured function calling using the 12 baseline MCP tools
- Reasoning effort: low/medium (per config)
- Bounded context and prompt prefix stability for prompt caching
"""

import json
from typing import Dict, Any, List, Optional, Tuple
import httpx
from backend.config import settings
from backend.schemas.agent import AgentChatResponse, UIAction, ToolCallRecord


def get_openai_formatted_tools() -> List[Dict[str, Any]]:
    """Converts the 12 baseline MCP tool definitions to OpenAI tool format."""
    from backend.mcp.tools import MCP_TOOL_DEFINITIONS
    tools = []
    for t in MCP_TOOL_DEFINITIONS:
        tools.append({
            "type": "function",
            "name": t["name"],
            "description": t["description"],
            "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
        })
    return tools


class OpenAIResponsesAdapter:
    """Client for OpenAI Responses API with GPT-5.6 Luna."""

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())

    @classmethod
    def execute_responses_workflow(
        cls,
        merchant_id: str,
        user_message: str,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        page_context: Optional[Dict[str, Any]] = None
    ) -> AgentChatResponse:
        """
        Executes a multi-step tool-calling interaction with GPT-5.6 Luna via the Responses API.
        """
        api_key = settings.OPENAI_API_KEY.strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured.")

        model = settings.OPENAI_MODEL or "gpt-5.6-luna"
        reasoning_effort = settings.OPENAI_REASONING_EFFORT or "low"

        # Construct input items for Responses API
        # Stable system instructions first for prompt caching
        input_items = [
            {"role": "system", "content": system_prompt}
        ]

        # Recent conversation turns (bounded)
        for turn in conversation_history[-6:]:
            input_items.append({"role": turn["role"], "content": turn["content"]})

        # Context item if on-screen data is present
        if page_context:
            input_items.append({
                "role": "system",
                "content": f"Current On-Screen Context: {json.dumps(page_context)}"
            })

        input_items.append({"role": "user", "content": user_message})

        tools = get_openai_formatted_tools()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        tool_records: List[ToolCallRecord] = []
        final_ui_action: Optional[UIAction] = None
        extracted_data: Dict[str, Any] = {}

        # Up to 3 tool turns
        for step in range(3):
            payload = {
                "model": model,
                "input": input_items,
                "tools": tools,
                "reasoning": {"effort": reasoning_effort},
                "max_output_tokens": 800
            }

            try:
                with httpx.Client(timeout=25.0) as client:
                    resp = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)

                    # If Responses API endpoint returns 404 or unsupported on current tier, fallback to chat/completions
                    if resp.status_code == 404:
                        return cls._execute_chat_completions_fallback(
                            api_key, model, input_items, tools, merchant_id
                        )

                    if resp.status_code != 200:
                        raise RuntimeError(f"OpenAI Responses API error ({resp.status_code}): {resp.text}")

                    data = resp.json()
            except httpx.RequestError as exc:
                raise RuntimeError(f"OpenAI connection error: {str(exc)}")

            # Parse output from Responses API
            # Responses API output items contain message and/or function_call
            output = data.get("output", [])
            tool_calls_requested = []

            assistant_text = ""
            for item in output:
                if item.get("type") == "message":
                    content = item.get("content", "")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and "text" in block:
                                assistant_text += block["text"]
                            elif isinstance(block, str):
                                assistant_text += block
                    elif isinstance(content, str):
                        assistant_text += content
                elif item.get("type") == "function_call":
                    tool_calls_requested.append(item)

            # If no function calls requested, we have our final synthesized response
            if not tool_calls_requested:
                return AgentChatResponse(
                    reply_text=assistant_text.strip() or "Analysis completed.",
                    workflow_type="LUNA_REASONING",
                    llm_used=True,
                    ui_action=final_ui_action,
                    extracted_data=extracted_data,
                    tool_calls=tool_records,
                    suggested_prompts=["Compare these options", "Check cashflow forecast", "Simulate ₹50,000 loan"]
                )

            # Append all model output items (including reasoning blocks and function calls) to next turn's input
            input_items.extend(output)

            # Execute requested tool calls through shared MCP registry
            from backend.mcp.tools import execute_mcp_tool
            for call in tool_calls_requested:
                tool_name = call.get("name")
                raw_args = call.get("arguments", "{}")
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                # Guarantee merchant isolation
                args["merchant_id"] = merchant_id

                tool_result = execute_mcp_tool(tool_name, args)
                preview = str(tool_result)[:140]

                tool_records.append(ToolCallRecord(
                    tool_name=tool_name,
                    arguments=args,
                    result_preview=preview
                ))

                if tool_name == "navigate_ui":
                    target_page = tool_result.get("target_page", "dashboard")
                    params = dict(tool_result.get("parameters", {}))
                    amt = params.get("amount") or params.get("requested_amount")
                    emi = params.get("emi") or params.get("max_daily_emi")
                    if amt is not None:
                        params["amount"] = float(amt)
                        params["requested_amount"] = float(amt)
                    if emi is not None:
                        params["emi"] = float(emi)
                        params["max_daily_emi"] = float(emi)
                    final_ui_action = UIAction(action_type="NAVIGATE", target_page=target_page, parameters=params)
                    extracted_data = dict(params)
                elif tool_name == "recommend_loans":
                    amt = float(args.get("requested_amount", 100000.0))
                    emi = float(args.get("max_daily_emi")) if args.get("max_daily_emi") is not None else None
                    extracted_data = {"amount": amt, "requested_amount": amt, "emi": emi, "max_daily_emi": emi}
                    final_ui_action = UIAction(action_type="NAVIGATE", target_page="recommendations", parameters=extracted_data)

                # Append tool result to conversation for next Responses API turn
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": json.dumps(tool_result)
                })

        return AgentChatResponse(
            reply_text=assistant_text or "Here are your loan advisory results based on verified backend data.",
            workflow_type="LUNA_REASONING",
            llm_used=True,
            ui_action=final_ui_action,
            extracted_data=extracted_data,
            tool_calls=tool_records,
            suggested_prompts=["Compare these options", "Check cashflow forecast"]
        )

    @classmethod
    def _execute_chat_completions_fallback(
        cls,
        api_key: str,
        model: str,
        input_items: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        merchant_id: str
    ) -> AgentChatResponse:
        """
        Chat Completions compatibility fallback for models or environments
        where /v1/responses is routed through standard tool-calling protocol.
        """
        chat_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in tools]
        messages = []
        for it in input_items:
            role = it.get("role", "user")
            if role in ["system", "user", "assistant"]:
                messages.append({"role": role, "content": it.get("content", "")})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "tools": chat_tools,
            "temperature": 0.2,
            "max_tokens": 800
        }

        with httpx.Client(timeout=25.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI fallback error ({resp.status_code}): {resp.text}")
            data = resp.json()
            choice = data["choices"][0]["message"]
            reply_text = choice.get("content") or ""

            tool_records = []
            final_ui_action = None
            extracted = {}

            if choice.get("tool_calls"):
                from backend.mcp.tools import execute_mcp_tool
                for tc in choice["tool_calls"]:
                    fn = tc["function"]
                    t_name = fn["name"]
                    t_args = json.loads(fn.get("arguments", "{}"))
                    t_args["merchant_id"] = merchant_id
                    t_res = execute_mcp_tool(t_name, t_args)
                    tool_records.append(ToolCallRecord(
                        tool_name=t_name,
                        arguments=t_args,
                        result_preview=str(t_res)[:140]
                    ))
                    if t_name in ["navigate_ui", "recommend_loans"]:
                        final_ui_action = UIAction(action_type="NAVIGATE", target_page="recommendations", parameters=t_args)

            return AgentChatResponse(
                reply_text=reply_text or "Analysis completed using verified LoanIQ product records.",
                workflow_type="LUNA_REASONING",
                llm_used=True,
                ui_action=final_ui_action,
                extracted_data=extracted,
                tool_calls=tool_records,
                suggested_prompts=["Compare these products", "Check 30-day forecast"]
            )

    @classmethod
    def evaluate_loans_with_luna(
        cls,
        merchant_summary: Dict[str, Any],
        candidate_loans: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, str]]:
        """
        Uses GPT-5.6 Luna to evaluate candidate loan products, providing:
        - affordability_status: Nuanced, context-aware financial risk assessment with cashflow margins.
        - recommendation_fit: Tailored 1-2 sentence credit fit explanation for this specific merchant.
        """
        api_key = settings.OPENAI_API_KEY.strip()
        if not api_key:
            return {}

        model = settings.OPENAI_MODEL or "gpt-5.6-luna"
        reasoning_effort = settings.OPENAI_REASONING_EFFORT or "low"

        system_prompt = (
            "You are an expert SME credit underwriting and financial advisory system for Indian merchants.\n"
            f"Merchant Profile:\n{json.dumps(merchant_summary, indent=2)}\n\n"
            "Task: Evaluate each candidate loan product for this merchant.\n"
            "Return STRICTLY valid JSON with a root object containing the key 'evaluations'.\n"
            "'evaluations' must map each loan_id (e.g. 'LP001') to an object with exactly two keys:\n"
            "1. 'affordability_status': A concise, professional, nuanced financial risk assessment (under 8 words). "
            "If the net daily margin after new EMI is negative, describe the specific risk and shortfall clearly (e.g. 'High Risk (Negative Margin: -₹55/day)', 'Moderate Working Capital Risk', 'Tight Debt Servicing Deficit'). "
            "If positive, specify the safety buffer (e.g. 'Comfortable (₹120/day safety buffer)').\n"
            "2. 'recommendation_fit': A crisp, high-value 1-2 sentence credit fit explanation tailored to this merchant's cashflow and lender advantages. "
            "Do NOT output generic repetitive checklists like 'Competitive low interest rate; Minimal 1% processing fee'. "
            "Instead explain distinct trade-offs (e.g., lowest borrowing cost and zero prepayment penalty vs. daily cash monitoring requirements, high approval confidence vs. higher APR, flexibility for inventory cycles).\n"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Candidate Loans:\n{json.dumps(candidate_loans)}\n\nOutput only valid JSON with root key 'evaluations'."}
            ],
            "reasoning": {"effort": reasoning_effort},
            "max_output_tokens": 1200
        }

        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    output_items = data.get("output", [])
                    raw_text = ""
                    for it in output_items:
                        if it.get("type") == "message":
                            for part in it.get("content", []):
                                if isinstance(part, dict) and "text" in part:
                                    raw_text += part["text"]
                                elif isinstance(part, str):
                                    raw_text += part
                    cleaned_text = raw_text.strip()
                    if cleaned_text.startswith("```"):
                        lines = cleaned_text.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        cleaned_text = "\n".join(lines).strip()

                    parsed = json.loads(cleaned_text)
                    return parsed.get("evaluations", {})
        except Exception as e:
            print(f"Luna loan evaluation error: {e}")

        return {}
