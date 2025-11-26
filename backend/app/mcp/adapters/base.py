"""MCP 适配器基类（从 MuMu 复用，移植到 Arboris）"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List
from dataclasses import dataclass


class AdapterType(Enum):
    """适配器类型"""
    FUNCTION_CALLING = "function_calling"  # 标准 Function Calling
    PROMPT_INJECTION = "prompt_injection"  # 提示词注入
    REACT = "react"  # ReAct 模式
    XML = "xml"  # XML 标记


@dataclass
class ToolCallResult:
    """工具调用结果"""

    tool_calls: List[Dict[str, Any]]  # 解析出的工具调用
    raw_response: str  # 原始 AI 响应
    has_tool_calls: bool  # 是否包含工具调用
    needs_continuation: bool = False  # 是否需要继续对话


class BaseMCPAdapter(ABC):
    """MCP 适配器基类"""

    def __init__(self) -> None:
        self.adapter_type: AdapterType = AdapterType.PROMPT_INJECTION

    @abstractmethod
    def format_tools_for_prompt(
        self,
        tools: List[Dict[str, Any]],
        user_message: str,
    ) -> str:
        """将工具列表格式化为提示词。"""
        raise NotImplementedError

    @abstractmethod
    def parse_tool_calls(self, ai_response: str) -> ToolCallResult:
        """从 AI 响应中解析工具调用。"""
        raise NotImplementedError

    @abstractmethod
    def build_continuation_prompt(
        self,
        original_message: str,
        ai_response: str,
        tool_results: List[Dict[str, Any]],
    ) -> str:
        """构建包含工具结果的继续对话提示词。"""
        raise NotImplementedError

    def supports_native_tools(self) -> bool:
        """是否支持原生工具调用（如 Function Calling）。"""
        return False

    def get_adapter_type(self) -> AdapterType:
        """获取适配器类型。"""
        return self.adapter_type
