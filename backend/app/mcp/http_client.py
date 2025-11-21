"""
HTTP MCP 客户端模块。

提供与单个 MCP 服务器通信的 HTTP 客户端实现。
基于官方 MCP Python SDK。
"""

import logging
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import MCPConfig

logger = logging.getLogger(__name__)


class HTTPMCPClient:
    """HTTP-based MCP client using official SDK.
    
    封装与单个 MCP Server 的通信逻辑，包括连接管理、工具列表获取和工具调用。
    """
    
    def __init__(self, server_url: str, headers: Optional[Dict[str, str]] = None, timeout: float = MCPConfig.CONNECT_TIMEOUT_SECONDS):
        """初始化 HTTP MCP 客户端。
        
        Args:
            server_url: MCP 服务器的 URL
            headers: 可选的 HTTP 请求头（用于认证等）
            timeout: 连接超时时间（秒）
        """
        self.server_url = server_url
        self.headers = headers or {}
        self.timeout = timeout
        self._session: Optional[ClientSession] = None
        self._stream_context = None
    
    async def connect(self) -> None:
        """建立与 MCP 服务器的连接。
        
        使用 streamablehttp_client 创建 HTTP 流，初始化 ClientSession，
        并完成 MCP 协议握手。
        
        Raises:
            Exception: 连接失败时抛出异常
        """
        try:
            logger.info("正在连接到 MCP 服务器: %s", self.server_url)
            
            # 创建 HTTP 流
            self._stream_context = streamablehttp_client(
                self.server_url,
                headers=self.headers,
                timeout=self.timeout
            )
            
            # 进入上下文管理器
            streams = await self._stream_context.__aenter__()
            
            # 初始化 ClientSession
            self._session = ClientSession(streams[0], streams[1])
            
            # 完成 MCP 协议握手
            await self._session.initialize()
            
            logger.info("成功连接到 MCP 服务器: %s", self.server_url)
            
        except Exception as exc:
            logger.error("连接 MCP 服务器失败: %s, 错误: %s", self.server_url, exc)
            await self.disconnect()
            raise
    
    async def disconnect(self) -> None:
        """关闭连接并清理资源。"""
        try:
            if self._session:
                # ClientSession 没有显式的 close 方法，由上下文管理器处理
                self._session = None
            
            if self._stream_context:
                await self._stream_context.__aexit__(None, None, None)
                self._stream_context = None
            
            logger.info("已断开与 MCP 服务器的连接: %s", self.server_url)
            
        except Exception as exc:
            logger.error("断开连接时发生错误: %s", exc)
    
    async def list_tools(self) -> List[Any]:
        """获取服务器提供的工具列表。
        
        Returns:
            工具定义列表
            
        Raises:
            RuntimeError: 如果未连接
            Exception: 调用失败时抛出异常
        """
        if not self.is_connected():
            raise RuntimeError("客户端未连接，请先调用 connect()")
        
        try:
            logger.debug("正在获取工具列表: %s", self.server_url)
            result = await self._session.list_tools()
            tools = result.tools if hasattr(result, 'tools') else []
            logger.info("获取到 %d 个工具: %s", len(tools), self.server_url)
            return tools
            
        except Exception as exc:
            logger.error("获取工具列表失败: %s, 错误: %s", self.server_url, exc)
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具调用。
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数（字典格式）
            
        Returns:
            工具执行结果
            
        Raises:
            RuntimeError: 如果未连接
            Exception: 调用失败时抛出异常
        """
        if not self.is_connected():
            raise RuntimeError("客户端未连接，请先调用 connect()")
        
        try:
            logger.debug("正在调用工具: %s, 参数: %s", tool_name, arguments)
            result = await self._session.call_tool(tool_name, arguments)
            
            # 提取结果内容
            if hasattr(result, 'content'):
                content = result.content
                # 如果 content 是列表，提取第一个元素的 text
                if isinstance(content, list) and len(content) > 0:
                    if hasattr(content[0], 'text'):
                        return content[0].text
                    return content[0]
                return content
            
            return result
            
        except Exception as exc:
            logger.error("工具调用失败: %s, 错误: %s", tool_name, exc)
            raise
    
    def is_connected(self) -> bool:
        """检查连接是否活跃。
        
        Returns:
            如果已连接返回 True，否则返回 False
        """
        return self._session is not None
