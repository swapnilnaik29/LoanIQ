from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class UIAction(BaseModel):
    action_type: str = Field(..., description="Action type: 'NAVIGATE', 'PREFILL_FORM', 'HIGHLIGHT_PRODUCT', 'NONE'")
    target_page: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result_preview: str


class PageContext(BaseModel):
    current_page: str
    selected_product_ids: Optional[List[str]] = Field(default_factory=list)
    visible_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AgentChatRequest(BaseModel):
    merchant_id: str
    message: str
    session_id: Optional[str] = "default"
    page_context: Optional[PageContext] = None


class AgentChatResponse(BaseModel):
    reply_text: str
    workflow_type: str
    llm_used: bool
    ui_action: Optional[UIAction] = None
    suggested_prompts: List[str] = Field(default_factory=list)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)

