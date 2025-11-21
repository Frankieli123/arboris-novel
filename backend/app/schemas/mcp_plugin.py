from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPPluginBase(BaseModel):
    """MCP 插件基础数据结构。"""

    plugin_name: str = Field(..., description="插件唯一标识符")
    display_name: str = Field(..., description="插件显示名称")
    plugin_type: str = Field(default="http", description="插件类型")
    server_url: str = Field(..., description="MCP 服务器地址")
    headers: Optional[Dict[str, str]] = Field(default=None, description="认证请求头")
    enabled: bool = Field(default=True, description="全局启用状态")
    category: Optional[str] = Field(default=None, description="插件分类")
    config: Optional[Dict[str, Any]] = Field(default=None, description="额外配置")


class MCPPluginCreate(MCPPluginBase):
    """创建插件时使用的模型。"""

    pass


class MCPPluginUpdate(BaseModel):
    """更新插件时使用的模型。"""

    display_name: Optional[str] = Field(default=None, description="插件显示名称")
    server_url: Optional[str] = Field(default=None, description="MCP 服务器地址")
    headers: Optional[Dict[str, str]] = Field(default=None, description="认证请求头")
    enabled: Optional[bool] = Field(default=None, description="全局启用状态")
    category: Optional[str] = Field(default=None, description="插件分类")
    config: Optional[Dict[str, Any]] = Field(default=None, description="额外配置")


class MCPPluginResponse(MCPPluginBase):
    """对外暴露的插件信息。"""

    id: int = Field(..., description="插件 ID")
    user_enabled: Optional[bool] = Field(default=None, description="用户级别的启用状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class ToolDefinition(BaseModel):
    """工具定义，OpenAI Function Calling 格式。"""

    type: str = Field(default="function", description="工具类型")
    function: Dict[str, Any] = Field(..., description="函数定义")


class ToolCallResult(BaseModel):
    """工具调用结果。"""

    tool_call_id: str = Field(..., description="工具调用 ID")
    role: str = Field(default="tool", description="角色")
    name: str = Field(..., description="工具名称")
    content: str = Field(..., description="工具返回内容")
    success: bool = Field(..., description="是否成功")
    duration_ms: Optional[float] = Field(default=None, description="执行耗时（毫秒）")


class ToolMetrics(BaseModel):
    """工具调用指标。"""

    tool_name: str = Field(..., description="工具名称")
    total_calls: int = Field(..., description="总调用次数")
    success_calls: int = Field(..., description="成功次数")
    failed_calls: int = Field(..., description="失败次数")
    avg_duration_ms: float = Field(..., description="平均耗时（毫秒）")
    success_rate: float = Field(..., description="成功率")


class PluginTestReport(BaseModel):
    """插件测试报告。"""

    success: bool = Field(..., description="测试是否成功")
    message: str = Field(..., description="测试结果消息")
    tools_count: int = Field(..., description="工具数量")
    suggestions: List[str] = Field(default_factory=list, description="测试建议")
    error: Optional[str] = Field(default=None, description="错误信息")
