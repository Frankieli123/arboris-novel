"""
MCP 插件注册表模块。

管理所有 MCP 插件会话的连接池，提供会话复用、LRU 驱逐、TTL 清理等功能。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .config import MCPConfig
from .http_client import HTTPMCPClient

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """会话信息。
    
    存储每个插件会话的客户端实例、创建时间和最后使用时间。
    """
    client: HTTPMCPClient
    created_at: datetime
    last_used: datetime
    plugin_name: str
    user_id: int


class MCPPluginRegistry:
    """MCP 插件注册表。
    
    管理所有插件会话的连接池，支持：
    - 会话复用：同一用户的同一插件复用会话
    - LRU 驱逐：达到容量上限时驱逐最久未使用的会话
    - TTL 清理：定期清理过期的空闲会话
    - 细粒度锁：每个用户使用独立的锁避免并发冲突
    """
    
    def __init__(
        self,
        max_clients: int = MCPConfig.MAX_CLIENTS,
        client_ttl: int = MCPConfig.CLIENT_TTL_SECONDS
    ):
        """初始化插件注册表。
        
        Args:
            max_clients: 最大并发客户端连接数
            client_ttl: 客户端会话 TTL（秒）
        """
        self._sessions: Dict[str, SessionInfo] = {}
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._max_clients = max_clients
        self._client_ttl = client_ttl
        self._cleanup_task: Optional[asyncio.Task] = None
        self._global_lock = asyncio.Lock()
        
        logger.info(
            "初始化 MCP 插件注册表: max_clients=%d, client_ttl=%ds",
            max_clients, client_ttl
        )
    
    def _get_session_key(self, user_id: int, plugin_name: str) -> str:
        """生成会话键。
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
            
        Returns:
            会话键字符串
        """
        return f"{user_id}:{plugin_name}"
    
    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """获取用户级别的锁。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            该用户的锁对象
        """
        user_key = str(user_id)
        if user_key not in self._user_locks:
            self._user_locks[user_key] = asyncio.Lock()
        return self._user_locks[user_key]
    
    async def load_plugin(
        self,
        user_id: int,
        plugin_name: str,
        server_url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """加载插件并创建客户端实例。
        
        参考 MuMu 的实现风格：
        - 此处仅负责创建并缓存 HTTPMCPClient，不在这里发起网络连接
        - 实际的连接建立与重连逻辑由 HTTPMCPClient._ensure_connected 负责
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
            server_url: MCP 服务器 URL
            headers: 可选的 HTTP 请求头
        """
        session_key = self._get_session_key(user_id, plugin_name)
        user_lock = self._get_user_lock(user_id)
        
        async with user_lock:
            # 检查是否已存在
            if session_key in self._sessions:
                logger.debug("插件会话已存在: %s", session_key)
                return
            
            # 检查是否需要驱逐
            if len(self._sessions) >= self._max_clients:
                await self.evict_lru_session()
            
            # 创建客户端（不在此处连接远端 MCP Server）
            client = HTTPMCPClient(server_url, headers)
            
            # 存储会话信息
            now = datetime.now()
            self._sessions[session_key] = SessionInfo(
                client=client,
                created_at=now,
                last_used=now,
                plugin_name=plugin_name,
                user_id=user_id
            )
            
            logger.info("插件已加载: %s (总会话数: %d)", session_key, len(self._sessions))
    
    async def unload_plugin(self, user_id: int, plugin_name: str) -> None:
        """卸载插件并关闭连接。
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
        """
        session_key = self._get_session_key(user_id, plugin_name)
        user_lock = self._get_user_lock(user_id)
        
        async with user_lock:
            session_info = self._sessions.get(session_key)
            if not session_info:
                logger.debug("插件会话不存在: %s", session_key)
                return
            
            # 断开连接
            await session_info.client.disconnect()
            
            # 移除会话
            del self._sessions[session_key]
            
            logger.info("插件已卸载: %s (总会话数: %d)", session_key, len(self._sessions))
    
    async def get_client(
        self,
        user_id: int,
        plugin_name: str,
        server_url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> HTTPMCPClient:
        """获取或创建客户端。
        
        如果会话不存在或已失效，则创建新会话。
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
            server_url: MCP 服务器 URL
            headers: 可选的 HTTP 请求头
            
        Returns:
            HTTP MCP 客户端实例
        """
        session_key = self._get_session_key(user_id, plugin_name)
        user_lock = self._get_user_lock(user_id)

        # 首先在持有 user_lock 的情况下尝试获取已有会话
        async with user_lock:
            session_info = self._sessions.get(session_key)

            # 如果已存在会话，直接复用客户端。
            # 连接是否建立交由 HTTPMCPClient._ensure_connected 负责，
            # 这里不再根据 is_connected 主动删除会话，避免在加载阶段阻塞用户锁。
            if session_info:
                session_info.last_used = datetime.now()
                logger.debug("复用插件会话: %s", session_key)
                return session_info.client

        # 会话不存在时，在锁外创建新客户端，避免同一 user_lock 的重入死锁。
        # load_plugin 内部会自行获取 user_lock 以保证线程安全。
        await self.load_plugin(user_id, plugin_name, server_url, headers)
        return self._sessions[session_key].client
    
    async def list_tools(
        self,
        user_id: int,
        plugin_name: str,
        server_url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> List[Any]:
        """获取插件提供的工具列表。
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
            server_url: MCP 服务器 URL
            headers: 可选的 HTTP 请求头
            
        Returns:
            工具定义列表
        """
        client = await self.get_client(user_id, plugin_name, server_url, headers)
        try:
            # 为列出工具增加超时控制，避免远端 MCP 服务器无响应导致请求一直挂起
            return await asyncio.wait_for(
                client.list_tools(),
                timeout=MCPConfig.LIST_TOOLS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            logger.error(
                "获取工具列表超时: user_id=%s, plugin=%s, url=%s (timeout=%ss)",
                user_id,
                plugin_name,
                server_url,
                MCPConfig.LIST_TOOLS_TIMEOUT_SECONDS,
            )
            raise TimeoutError(
                f"获取工具列表超时 ({MCPConfig.LIST_TOOLS_TIMEOUT_SECONDS}s)"
            ) from exc
    
    async def call_tool(
        self,
        user_id: int,
        plugin_name: str,
        server_url: str,
        tool_name: str,
        arguments: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Any:
        """执行工具调用。
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
            server_url: MCP 服务器 URL
            tool_name: 工具名称
            arguments: 工具参数
            headers: 可选的 HTTP 请求头
            
        Returns:
            工具执行结果
        """
        client = await self.get_client(user_id, plugin_name, server_url, headers)
        try:
            # 为工具调用增加超时控制，避免远端 MCP 服务器在执行工具时无响应
            return await asyncio.wait_for(
                client.call_tool(tool_name, arguments),
                timeout=MCPConfig.TOOL_CALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            logger.error(
                "工具调用超时: user_id=%s, plugin=%s, tool=%s, url=%s (timeout=%ss)",
                user_id,
                plugin_name,
                tool_name,
                server_url,
                MCPConfig.TOOL_CALL_TIMEOUT_SECONDS,
            )
            raise TimeoutError(
                f"工具调用超时 ({MCPConfig.TOOL_CALL_TIMEOUT_SECONDS}s)"
            ) from exc
    
    async def cleanup_expired_sessions(self) -> None:
        """清理过期和空闲的会话。
        
        遍历所有会话，关闭并移除超过 TTL 的会话。
        """
        now = datetime.now()
        ttl_delta = timedelta(seconds=self._client_ttl)
        expired_keys: List[str] = []
        
        async with self._global_lock:
            for session_key, session_info in self._sessions.items():
                # 检查是否过期
                if now - session_info.last_used > ttl_delta:
                    expired_keys.append(session_key)
                # 检查连接状态
                elif not session_info.client.is_connected():
                    expired_keys.append(session_key)
        
        # 清理过期会话
        for session_key in expired_keys:
            parts = session_key.split(":", 1)
            if len(parts) == 2:
                user_id = int(parts[0])
                plugin_name = parts[1]
                await self.unload_plugin(user_id, plugin_name)
        
        if expired_keys:
            logger.info("清理了 %d 个过期会话", len(expired_keys))
    
    async def evict_lru_session(self) -> None:
        """驱逐最久未使用的会话。
        
        当会话数量达到上限时调用。
        """
        if not self._sessions:
            return
        
        # 找到最久未使用的会话
        lru_key = min(
            self._sessions.keys(),
            key=lambda k: self._sessions[k].last_used
        )
        
        parts = lru_key.split(":", 1)
        if len(parts) == 2:
            user_id = int(parts[0])
            plugin_name = parts[1]
            logger.info("驱逐 LRU 会话: %s", lru_key)
            await self.unload_plugin(user_id, plugin_name)
    
    async def start_cleanup_task(self) -> None:
        """启动定期清理任务。"""
        if self._cleanup_task is not None:
            logger.warning("清理任务已在运行")
            return
        
        async def cleanup_loop():
            """清理任务循环。"""
            while True:
                try:
                    await asyncio.sleep(MCPConfig.CLEANUP_INTERVAL_SECONDS)
                    await self.cleanup_expired_sessions()
                except asyncio.CancelledError:
                    logger.info("清理任务已取消")
                    break
                except Exception as exc:
                    logger.error("清理任务发生错误: %s", exc)
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("清理任务已启动")
    
    async def shutdown(self) -> None:
        """关闭注册表并清理所有资源。"""
        logger.info("正在关闭 MCP 插件注册表...")
        
        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        # 关闭所有会话
        session_keys = list(self._sessions.keys())
        for session_key in session_keys:
            parts = session_key.split(":", 1)
            if len(parts) == 2:
                user_id = int(parts[0])
                plugin_name = parts[1]
                await self.unload_plugin(user_id, plugin_name)
        
        logger.info("MCP 插件注册表已关闭")
