"""MCP 适配器子模块。

从 MuMu 项目复用的通用适配器体系：
- BaseMCPAdapter / AdapterType / ToolCallResult
- FunctionCallingAdapter
- PromptInjectionAdapter
- UniversalMCPAdapter
"""

from .base import BaseMCPAdapter, AdapterType, ToolCallResult
from .function_calling import FunctionCallingAdapter
from .prompt_injection import PromptInjectionAdapter
from .universal import UniversalMCPAdapter

__all__ = [
    "BaseMCPAdapter",
    "AdapterType",
    "ToolCallResult",
    "FunctionCallingAdapter",
    "PromptInjectionAdapter",
    "UniversalMCPAdapter",
]
