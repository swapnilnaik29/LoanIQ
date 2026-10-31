"""
FastAPI MCP (Model Context Protocol) Server Integration.
Provides JSON-RPC 2.0 and REST endpoints for external MCP clients and AI agent integration.
"""

import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from backend.mcp.tools import MCP_TOOL_DEFINITIONS, execute_mcp_tool

mcp_router = APIRouter(prefix="/mcp", tags=["Model Context Protocol"])


class MCPToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Any] = None


@mcp_router.get("/tools")
def list_tools():
    """Returns the list of registered MCP tools."""
    return {"tools": MCP_TOOL_DEFINITIONS}


@mcp_router.post("/call")
def call_tool(req: MCPToolCallRequest):
    """Executes a named MCP tool with arguments."""
    result = execute_mcp_tool(req.name, req.arguments)
    if "error" in result:
        return {"isError": True, "content": [{"type": "text", "text": result["error"]}]}
    return {"isError": False, "content": [{"type": "text", "text": json.dumps(result)}], "result": result}


@mcp_router.post("")
@mcp_router.post("/")
async def json_rpc_endpoint(req: Request):
    """
    Standard MCP JSON-RPC 2.0 transport handler.
    Supports initialize, ping, tools/list, and tools/call.
    """
    try:
        body = await req.json()
    except Exception:
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {}) or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "LoanIQ-MCP-Server", "version": "1.0.0"}
            }
        }
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOL_DEFINITIONS}}
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        res = execute_mcp_tool(tool_name, args)
        if "error" in res:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"isError": True, "content": [{"type": "text", "text": res["error"]}]}
            }
        import json as json_mod
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"isError": False, "content": [{"type": "text", "text": json_mod.dumps(res)}]}
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"}
        }
