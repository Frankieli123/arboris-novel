"""
HTTP MCP 客户端模块。

提供与单个 MCP 服务器通信的 HTTP 客户端实现。
基于官方 MCP Python SDK。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import MCPConfig

logger = logging.getLogger(__name__)


class HTTPMCPClient:
    """HTTP-based MCP client using official SDK.
    
    连接管理与 MuMu 项目保持一致风格：
    - 使用 streamablehttp_client + ClientSession 组合
    - 通过 _ensure_connected 懒加载并加锁，避免并发初始化问题
    - 通过 _cleanup 正确按栈顺序退出上下文，避免 TaskGroup 相关异常
    
    对外接口保持不变：构造函数、connect/disconnect/list_tools/call_tool/is_connected
    的签名不变，list_tools 仍返回 MCP SDK 的工具对象列表。
    """
    
    def __init__(
        self,
        server_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = MCPConfig.CONNECT_TIMEOUT_SECONDS,
    ) -> None:
        """初始化 HTTP MCP 客户端。
        
        Args:
            server_url: MCP 服务器的 URL
            headers: 可选的 HTTP 请求头（用于认证等）
            timeout: 连接超时时间（秒）
        """
        # 与 MuMu 保持一致：去掉尾部斜杠，避免重复 / 影响某些服务
        self.server_url = server_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        
        # MCP 会话与上下文栈
        self._session: Optional[ClientSession] = None
        self._context_stack: List[Any] = []
        self._initialized: bool = False
        # 连接锁，防止并发创建会话
        self._lock = asyncio.Lock()
    
    async def _ensure_connected(self) -> None:
        """确保已经与 MCP 服务器建立连接。
        
        参考 MuMu 实现，使用锁与上下文栈正确管理 stream 与 ClientSession，
        避免官方 MCP SDK 在 TaskGroup 中抛出的未处理异常。
        """
        async with self._lock:
            if self._session is not None and self._initialized:
                return
            try:
                safe_url = self.server_url.split("?", 1)[0]
                logger.info("正在连接到 MCP 服务器: %s", safe_url)
                
                # 使用官方 SDK 的 streamable_http_client 创建 HTTP 流
                stream_context = streamablehttp_client(
                    self.server_url,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                # 进入流上下文
                read_stream, write_stream, *_ = await stream_context.__aenter__()
                self._context_stack.append(("stream", stream_context))
                
                # 创建 ClientSession，并作为异步上下文管理器进入
                session_context = ClientSession(read_stream, write_stream)
                await session_context.__aenter__()
                self._session = session_context
                self._context_stack.append(("session", session_context))
                
                # 完成 MCP 协议握手
                await self._session.initialize()
                self._initialized = True
                
                logger.info("成功连接到 MCP 服务器: %s", safe_url)
            except Exception as exc:
                logger.error("连接 MCP 服务器失败: %s, 错误: %s", self.server_url, exc)
                await self._cleanup()
                raise
    
    async def _cleanup(self) -> None:
        """按栈顺序退出所有上下文并重置状态。"""
        # LIFO 顺序退出，参考 MuMu 对 anyio 相关异常的处理
        while self._context_stack:
            ctx_type, ctx = self._context_stack.pop()
            try:
                await ctx.__aexit__(None, None, None)
            except RuntimeError as exc:
                # 忽略 task/取消范围相关的提示性异常
                msg = str(exc).lower()
                if "cancel scope" in msg or "different task" in msg:
                    logger.debug("忽略 %s 上下文清理告警: %s", ctx_type, exc)
                else:
                    logger.error("清理 %s 上下文失败: %s", ctx_type, exc)
            except Exception as exc:
                logger.error("清理 %s 上下文失败: %s", ctx_type, exc)
        
        self._session = None
        self._initialized = False
    
    async def connect(self) -> None:
        """建立与 MCP 服务器的连接（保持原有接口）。"""
        await self._ensure_connected()
    
    async def disconnect(self) -> None:
        """关闭连接并清理资源。"""
        try:
            await self._cleanup()
            logger.info("已断开与 MCP 服务器的连接: %s", self.server_url)
        except Exception as exc:
            logger.error("断开连接时发生错误: %s", exc)
    
    async def list_tools(self) -> List[Any]:
        """获取服务器提供的工具列表。
        
        Returns:
            工具定义列表（MCP SDK 的工具对象列表）
        """
        # 懒加载连接，保持对外接口语义不变
        await self._ensure_connected()
        
        try:
            safe_url = self.server_url.split("?", 1)[0]
            logger.debug("正在获取工具列表: %s", safe_url)
            result = await self._session.list_tools()
            tools = result.tools if hasattr(result, "tools") else []
            logger.info("获取到 %d 个工具: %s", len(tools), safe_url)
            return tools
        except Exception as exc:
            logger.error("获取工具列表失败: %s, 错误: %s", self.server_url, exc)
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具调用。
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数（字典格式）
        """
        await self._ensure_connected()
        
        try:
            logger.debug("正在调用工具: %s, 参数: %s", tool_name, arguments)
            result = await self._session.call_tool(tool_name, arguments)
            
            # 提取结果内容，与原实现保持兼容
            if hasattr(result, "content"):
                content = result.content
                if isinstance(content, list) and content:
                    first = content[0]
                    if hasattr(first, "text"):
                        return first.text
                    return first
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
        return self._session is not None and self._initialized
