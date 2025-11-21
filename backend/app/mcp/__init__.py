"""
MCP (Model Context Protocol) 插件系统模块。

该模块提供了与 MCP 服务器通信的核心功能，包括：
- HTTP 客户端：与 MCP 服务器建立连接和通信
- 插件注册表：管理插件会话和连接池
- 配置管理：MCP 系统的配置常量
"""

from .config import MCPConfig
from .http_client import HTTPMCPClient
from .registry import MCPPluginRegistry

__all__ = [
    "MCPConfig",
    "HTTPMCPClient",
    "MCPPluginRegistry",
]
