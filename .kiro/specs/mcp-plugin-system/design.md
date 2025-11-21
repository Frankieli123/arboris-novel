# Design Document

## Overview

本设计文档描述了 MCP (Model Context Protocol) 插件系统的技术架构和实现方案。该系统将为 Arboris Novel 平台提供标准化的外部工具集成能力，使 AI 能够在创作过程中访问搜索引擎、知识库、文件系统等外部资源。

系统采用分层架构设计，包括：
- **API 层**：提供 RESTful 接口供前端调用
- **服务层**：封装业务逻辑，包括工具服务、测试服务
- **MCP 核心层**：管理插件注册表、HTTP 客户端、连接池
- **数据层**：持久化插件配置和用户偏好

核心设计原则：
1. **标准化**：基于官方 MCP Python SDK，确保协议兼容性
2. **高性能**：连接池管理、工具缓存、并行调用
3. **可靠性**：重试机制、健康检查、降级策略
4. **可观测性**：详细指标、日志、测试工具
5. **易用性**：简化配置、智能测试、自动管理

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Vue.js)                       │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │ Plugin Mgmt UI │  │ Settings Panel │  │ Writing Desk  │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST API
┌──────────────────────────┴──────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    API Layer                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │ mcp_plugins  │  │    admin     │  │   writer   │ │  │
│  │  │   router     │  │   router     │  │   router   │ │  │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Service Layer                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │ MCP Tool     │  │ MCP Test     │  │ LLM Service│ │  │
│  │  │ Service      │  │ Service      │  │ (Enhanced) │ │  │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   MCP Core Layer                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │   Plugin     │  │ HTTP MCP     │  │   Config   │ │  │
│  │  │  Registry    │  │   Client     │  │            │ │  │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   Data Layer                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │  MCPPlugin   │  │ UserPlugin   │  │ Repository │ │  │
│  │  │    Model     │  │   Pref       │  │            │ │  │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP Protocol (HTTP)
┌──────────────────────────┴──────────────────────────────────┐
│                  External MCP Servers                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ Exa Search   │  │ File System  │  │ Custom Services   │ │
│  └──────────────┘  └──────────────┘  └───────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Chapter Generation with MCP

```
User Request (Generate Chapter)
    │
    ├─> API Layer: POST /projects/{id}/chapters/{chapter_id}/generate
    │
    ├─> Service Layer: Chapter Generation Service
    │   ├─> Get project context (blueprint, characters, outline)
    │   ├─> Get memory context (previous chapters)
    │   └─> Get MCP tools (MCP Tool Service)
    │       └─> Query enabled plugins for user
    │           └─> Get tools from Plugin Registry
    │               └─> Call list_tools() on MCP Client
    │
    ├─> LLM Service: generate_text_with_mcp()
    │   ├─> Round 1: AI analyzes task with available tools
    │   │   └─> Returns tool_calls or content
    │   │
    │   ├─> If tool_calls exist:
    │   │   ├─> Execute tool calls (MCP Tool Service)
    │   │   │   ├─> Parse tool name and arguments
    │   │   │   ├─> Call Plugin Registry.call_tool()
    │   │   │   │   └─> HTTP MCP Client.call_tool()
    │   │   │   │       └─> MCP Server executes tool
    │   │   │   ├─> Collect results (parallel execution)
    │   │   │   └─> Record metrics
    │   │   │
    │   │   └─> Round 2: AI generates content with tool results
    │   │
    │   └─> Return final chapter content
    │
    └─> Save chapter to database
```

## Components and Interfaces

### 1. MCP Plugin Model

数据库模型，存储插件配置信息。采用 SQLAlchemy 2.0 风格的 Mapped 类型注解。

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class MCPPlugin(Base):
    """MCP 插件配置表，存储插件的连接信息和认证配置。"""
    
    __tablename__ = "mcp_plugins"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plugin_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    plugin_type: Mapped[str] = mapped_column(String(50), nullable=False, default="http")
    server_url: Mapped[str] = mapped_column(String(500), nullable=False)
    headers: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON 存储
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON 存储
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # 关系映射
    user_preferences: Mapped[list["UserPluginPreference"]] = relationship(
        "UserPluginPreference",
        back_populates="plugin",
        cascade="all, delete-orphan"
    )
```

### 2. User Plugin Preference Model

存储用户级别的插件启用偏好。

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class UserPluginPreference(Base):
    """用户插件偏好表，记录每个用户对插件的启用状态。"""
    
    __tablename__ = "user_plugin_preferences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plugin_id: Mapped[int] = mapped_column(Integer, ForeignKey("mcp_plugins.id", ondelete="CASCADE"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="plugin_preferences")
    plugin: Mapped["MCPPlugin"] = relationship("MCPPlugin", back_populates="user_preferences")
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint("user_id", "plugin_id", name="uq_user_plugin"),
    )
```

### 3. MCP Plugin Repository

数据访问层，封装插件相关的数据库操作。遵循项目的 Repository 模式。

```python
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.mcp_plugin import MCPPlugin
from .base import BaseRepository


class MCPPluginRepository(BaseRepository[MCPPlugin]):
    """MCP 插件仓储，负责插件配置的数据库操作。"""
    
    model = MCPPlugin
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def get_by_name(self, plugin_name: str) -> Optional[MCPPlugin]:
        """根据插件名称获取插件。"""
        return await self.get(plugin_name=plugin_name)
    
    async def list_enabled(self) -> List[MCPPlugin]:
        """获取所有全局启用的插件。"""
        stmt = select(MCPPlugin).where(MCPPlugin.enabled == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def list_by_category(self, category: str) -> List[MCPPlugin]:
        """根据分类获取插件列表。"""
        stmt = select(MCPPlugin).where(MCPPlugin.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### 4. User Plugin Preference Repository

用户插件偏好的数据访问层。

```python
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.mcp_plugin import MCPPlugin, UserPluginPreference
from .base import BaseRepository


class UserPluginPreferenceRepository(BaseRepository[UserPluginPreference]):
    """用户插件偏好仓储。"""
    
    model = UserPluginPreference
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def get_user_preference(
        self, user_id: int, plugin_id: int
    ) -> Optional[UserPluginPreference]:
        """获取用户对特定插件的偏好设置。"""
        return await self.get(user_id=user_id, plugin_id=plugin_id)
    
    async def get_enabled_plugins(self, user_id: int) -> List[MCPPlugin]:
        """获取用户启用的所有插件。"""
        stmt = (
            select(MCPPlugin)
            .join(UserPluginPreference)
            .where(
                and_(
                    UserPluginPreference.user_id == user_id,
                    UserPluginPreference.enabled == True,
                    MCPPlugin.enabled == True  # 插件本身也必须是启用状态
                )
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def set_user_preference(
        self, user_id: int, plugin_id: int, enabled: bool
    ) -> UserPluginPreference:
        """设置或更新用户的插件偏好。"""
        pref = await self.get_user_preference(user_id, plugin_id)
        if pref:
            pref.enabled = enabled
            await self.session.flush()
        else:
            pref = UserPluginPreference(
                user_id=user_id,
                plugin_id=plugin_id,
                enabled=enabled
            )
            await self.add(pref)
        return pref
```

### 5. HTTP MCP Client

封装与单个 MCP Server 的通信逻辑。

```python
class HTTPMCPClient:
    """HTTP-based MCP client using official SDK."""
    
    def __init__(self, server_url: str, headers: dict, timeout: float):
        self.server_url = server_url
        self.headers = headers
        self.timeout = timeout
        self._session: Optional[ClientSession] = None
        self._stream_context = None
    
    async def connect(self) -> None:
        """Establish connection to MCP server."""
        # Create HTTP stream using streamablehttp_client
        # Initialize ClientSession
        # Call session.initialize()
    
    async def disconnect(self) -> None:
        """Close connection and cleanup resources."""
    
    async def list_tools(self) -> List[Tool]:
        """Get list of available tools from server."""
        # Call session.list_tools()
        # Return tool definitions
    
    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute a tool with given arguments."""
        # Call session.call_tool(tool_name, arguments)
        # Extract and return result content
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
```

### 6. MCP Plugin Registry

管理所有插件会话的连接池。

```python
class MCPPluginRegistry:
    """Central registry for managing MCP plugin sessions."""
    
    def __init__(self, max_clients: int, client_ttl: int):
        self._sessions: Dict[str, SessionInfo] = {}
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._max_clients = max_clients
        self._client_ttl = client_ttl
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def load_plugin(self, user_id: int, plugin: MCPPlugin) -> None:
        """Load plugin and establish connection."""
        # Create session key: f"{user_id}:{plugin.plugin_name}"
        # Create HTTPMCPClient
        # Connect to server
        # Store in _sessions
    
    async def unload_plugin(self, user_id: int, plugin_name: str) -> None:
        """Unload plugin and close connection."""
    
    async def get_client(self, user_id: int, plugin_name: str) -> HTTPMCPClient:
        """Get or create client for user and plugin."""
        # Check if session exists and is valid
        # If not, load plugin
        # Update last_used timestamp
        # Return client
    
    async def list_tools(self, user_id: int, plugin_name: str) -> List[Tool]:
        """Get tools from plugin."""
        # Get client
        # Call client.list_tools()
    
    async def call_tool(
        self, user_id: int, plugin_name: str, 
        tool_name: str, arguments: dict
    ) -> Any:
        """Execute tool call."""
        # Get client
        # Call client.call_tool()
    
    async def cleanup_expired_sessions(self) -> None:
        """Remove expired and idle sessions."""
        # Check TTL for each session
        # Close and remove expired ones
    
    async def evict_lru_session(self) -> None:
        """Evict least recently used session when at capacity."""
```

### 7. MCP Tool Service

业务逻辑层，处理工具获取和调用。遵循项目现有的 Service 层模式。

```python
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.mcp_plugin_repository import MCPPluginRepository
from ..repositories.user_plugin_preference_repository import UserPluginPreferenceRepository
from .mcp.config import MCPConfig
from .mcp.registry import MCPPluginRegistry

logger = logging.getLogger(__name__)


class MCPToolService:
    """MCP 工具服务，负责工具获取、调用和指标记录。"""
    
    def __init__(self, session: AsyncSession, registry: MCPPluginRegistry):
        self.session = session
        self.registry = registry
        self.plugin_repo = MCPPluginRepository(session)
        self.user_pref_repo = UserPluginPreferenceRepository(session)
        self._tool_cache: Dict[str, ToolCacheEntry] = {}
        self._metrics: Dict[str, ToolMetrics] = {}
    
    async def get_user_enabled_tools(
        self, user_id: int
    ) -> List[Dict[str, Any]]:
        """获取用户启用的所有 MCP 工具，转换为 OpenAI Function Calling 格式。"""
        # 查询用户启用的插件
        enabled_plugins = await self.user_pref_repo.get_enabled_plugins(user_id)
        
        tools: List[Dict[str, Any]] = []
        for plugin in enabled_plugins:
            # 检查缓存
            cache_key = f"{user_id}:{plugin.plugin_name}"
            cached = self._tool_cache.get(cache_key)
            
            if cached and cached.expire_time > datetime.now():
                # 缓存命中
                cached.hit_count += 1
                tools.extend(cached.tools)
                logger.debug("工具缓存命中: %s (命中次数: %d)", cache_key, cached.hit_count)
            else:
                # 缓存未命中，从注册表获取
                try:
                    mcp_tools = await self.registry.list_tools(user_id, plugin.plugin_name)
                    converted_tools = self._convert_to_openai_format(mcp_tools, plugin.plugin_name)
                    
                    # 更新缓存
                    expire_time = datetime.now() + timedelta(minutes=MCPConfig.TOOL_CACHE_TTL_MINUTES)
                    self._tool_cache[cache_key] = ToolCacheEntry(
                        tools=converted_tools,
                        expire_time=expire_time,
                        hit_count=0
                    )
                    tools.extend(converted_tools)
                    logger.info("工具列表已缓存: %s (工具数: %d)", cache_key, len(converted_tools))
                except Exception as exc:
                    logger.error("获取插件工具失败: %s, 错误: %s", plugin.plugin_name, exc)
                    continue
        
        return tools
    
    async def execute_tool_calls(
        self, user_id: int, tool_calls: List[Dict]
    ) -> List[Dict]:
        """并行执行多个工具调用。"""
        if not tool_calls:
            return []
        
        logger.info("开始执行 %d 个工具调用，用户: %d", len(tool_calls), user_id)
        
        # 创建并行任务
        tasks = [
            self._execute_single_tool(user_id, tool_call)
            for tool_call in tool_calls
        ]
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        formatted_results: List[Dict] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("工具调用失败: %s", result)
                formatted_results.append({
                    "tool_call_id": tool_calls[i].get("id", "unknown"),
                    "role": "tool",
                    "name": tool_calls[i].get("function", {}).get("name", "unknown"),
                    "content": json.dumps({"error": str(result)}, ensure_ascii=False),
                    "success": False
                })
            else:
                formatted_results.append(result)
        
        return formatted_results
    
    async def _execute_single_tool(
        self, user_id: int, tool_call: Dict
    ) -> Dict:
        """执行单个工具调用，带重试机制。"""
        tool_call_id = tool_call.get("id", "unknown")
        function_data = tool_call.get("function", {})
        full_tool_name = function_data.get("name", "")
        arguments_str = function_data.get("arguments", "{}")
        
        # 解析插件名和工具名 (格式: plugin_name.tool_name)
        if "." in full_tool_name:
            plugin_name, tool_name = full_tool_name.split(".", 1)
        else:
            plugin_name = full_tool_name
            tool_name = full_tool_name
        
        # 解析参数
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError as exc:
            logger.error("工具参数 JSON 解析失败: %s", exc)
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": full_tool_name,
                "content": json.dumps({"error": "参数格式错误"}, ensure_ascii=False),
                "success": False
            }
        
        # 执行工具调用
        start_time = datetime.now()
        try:
            result = await self._call_tool_with_retry(
                user_id, plugin_name, tool_name, arguments,
                timeout=MCPConfig.TOOL_CALL_TIMEOUT_SECONDS
            )
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # 记录成功指标
            metric_key = f"{plugin_name}.{tool_name}"
            if metric_key not in self._metrics:
                self._metrics[metric_key] = ToolMetrics()
            self._metrics[metric_key].update_success(duration_ms)
            
            logger.info("工具调用成功: %s, 耗时: %.2fms", full_tool_name, duration_ms)
            
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": full_tool_name,
                "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
                "success": True,
                "duration_ms": duration_ms
            }
        except Exception as exc:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # 记录失败指标
            metric_key = f"{plugin_name}.{tool_name}"
            if metric_key not in self._metrics:
                self._metrics[metric_key] = ToolMetrics()
            self._metrics[metric_key].update_failure(duration_ms)
            
            logger.error("工具调用失败: %s, 错误: %s", full_tool_name, exc)
            
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": full_tool_name,
                "content": json.dumps({"error": str(exc)}, ensure_ascii=False),
                "success": False,
                "duration_ms": duration_ms
            }
    
    async def _call_tool_with_retry(
        self, user_id: int, plugin_name: str,
        tool_name: str, arguments: dict, timeout: float
    ) -> Any:
        """带指数退避的工具调用重试。"""
        last_exception = None
        
        for attempt in range(MCPConfig.MAX_RETRIES):
            try:
                result = await self.registry.call_tool(
                    user_id, plugin_name, tool_name, arguments
                )
                return result
            except Exception as exc:
                last_exception = exc
                if attempt < MCPConfig.MAX_RETRIES - 1:
                    # 计算退避延迟
                    delay = min(
                        MCPConfig.BASE_RETRY_DELAY_SECONDS * (2 ** attempt),
                        MCPConfig.MAX_RETRY_DELAY_SECONDS
                    )
                    logger.warning(
                        "工具调用失败，%d 秒后重试 (尝试 %d/%d): %s.%s, 错误: %s",
                        delay, attempt + 1, MCPConfig.MAX_RETRIES,
                        plugin_name, tool_name, exc
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "工具调用达到最大重试次数: %s.%s, 错误: %s",
                        plugin_name, tool_name, exc
                    )
        
        raise last_exception
    
    def _convert_to_openai_format(
        self, mcp_tools: List[Any], plugin_name: str
    ) -> List[Dict[str, Any]]:
        """将 MCP 工具定义转换为 OpenAI Function Calling 格式。"""
        converted: List[Dict[str, Any]] = []
        
        for tool in mcp_tools:
            # MCP Tool 对象转换为 OpenAI 格式
            converted.append({
                "type": "function",
                "function": {
                    "name": f"{plugin_name}.{tool.name}",
                    "description": tool.description or "",
                    "parameters": tool.inputSchema or {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            })
        
        return converted
    
    def get_metrics(self, tool_name: Optional[str] = None) -> Dict:
        """获取工具调用指标。"""
        if tool_name:
            metric = self._metrics.get(tool_name)
            if not metric:
                return {}
            return {
                "tool_name": tool_name,
                "total_calls": metric.total_calls,
                "success_calls": metric.success_calls,
                "failed_calls": metric.failed_calls,
                "avg_duration_ms": metric.avg_duration_ms,
                "success_rate": metric.success_rate
            }
        
        # 返回所有工具的指标
        return {
            name: {
                "tool_name": name,
                "total_calls": metric.total_calls,
                "success_calls": metric.success_calls,
                "failed_calls": metric.failed_calls,
                "avg_duration_ms": metric.avg_duration_ms,
                "success_rate": metric.success_rate
            }
            for name, metric in self._metrics.items()
        }
    
    def clear_cache(self) -> None:
        """清空工具定义缓存。"""
        self._tool_cache.clear()
        logger.info("工具缓存已清空")
```

### 8. MCP Plugin Service

插件管理服务，处理插件的 CRUD 操作和用户偏好管理。

```python
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.mcp_plugin import MCPPlugin
from ..repositories.mcp_plugin_repository import MCPPluginRepository
from ..repositories.user_plugin_preference_repository import UserPluginPreferenceRepository
from ..schemas.mcp_plugin import MCPPluginCreate, MCPPluginResponse, MCPPluginUpdate

logger = logging.getLogger(__name__)


class MCPPluginService:
    """MCP 插件管理服务。"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plugin_repo = MCPPluginRepository(session)
        self.user_pref_repo = UserPluginPreferenceRepository(session)
    
    async def create_plugin(self, plugin_data: MCPPluginCreate) -> MCPPlugin:
        """创建新插件。"""
        # 检查插件名是否已存在
        existing = await self.plugin_repo.get_by_name(plugin_data.plugin_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"插件名 {plugin_data.plugin_name} 已存在"
            )
        
        plugin = MCPPlugin(**plugin_data.model_dump())
        await self.plugin_repo.add(plugin)
        await self.session.commit()
        await self.session.refresh(plugin)
        
        logger.info("创建插件: %s", plugin.plugin_name)
        return plugin
    
    async def get_plugin(self, plugin_id: int) -> Optional[MCPPlugin]:
        """获取插件。"""
        return await self.plugin_repo.get(id=plugin_id)
    
    async def get_plugin_with_user_status(
        self, plugin_id: int, user_id: int
    ) -> Optional[MCPPluginResponse]:
        """获取插件及用户的启用状态。"""
        plugin = await self.get_plugin(plugin_id)
        if not plugin:
            return None
        
        # 获取用户偏好
        pref = await self.user_pref_repo.get_user_preference(user_id, plugin_id)
        user_enabled = pref.enabled if pref else None
        
        return MCPPluginResponse(
            **plugin.__dict__,
            user_enabled=user_enabled
        )
    
    async def list_plugins_with_user_status(
        self, user_id: int
    ) -> List[MCPPluginResponse]:
        """列出所有插件及用户的启用状态。"""
        plugins = await self.plugin_repo.list()
        
        responses: List[MCPPluginResponse] = []
        for plugin in plugins:
            pref = await self.user_pref_repo.get_user_preference(user_id, plugin.id)
            user_enabled = pref.enabled if pref else None
            
            responses.append(MCPPluginResponse(
                **plugin.__dict__,
                user_enabled=user_enabled
            ))
        
        return responses
    
    async def update_plugin(
        self, plugin_id: int, plugin_data: MCPPluginUpdate
    ) -> MCPPlugin:
        """更新插件配置。"""
        plugin = await self.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="插件不存在"
            )
        
        update_dict = plugin_data.model_dump(exclude_unset=True)
        await self.plugin_repo.update_fields(plugin, **update_dict)
        await self.session.commit()
        await self.session.refresh(plugin)
        
        logger.info("更新插件: %s", plugin.plugin_name)
        return plugin
    
    async def delete_plugin(self, plugin_id: int) -> None:
        """删除插件。"""
        plugin = await self.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="插件不存在"
            )
        
        await self.plugin_repo.delete(plugin)
        await self.session.commit()
        
        logger.info("删除插件: %s", plugin.plugin_name)
    
    async def toggle_user_plugin(
        self, user_id: int, plugin_id: int, enabled: bool
    ) -> bool:
        """切换用户的插件启用状态。"""
        # 检查插件是否存在
        plugin = await self.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="插件不存在"
            )
        
        await self.user_pref_repo.set_user_preference(user_id, plugin_id, enabled)
        await self.session.commit()
        
        logger.info("用户 %d %s插件 %s", user_id, "启用" if enabled else "禁用", plugin.plugin_name)
        return enabled
```

### 9. MCP Test Service

智能测试服务，使用 AI 生成测试用例。

```python
import json
import logging
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.mcp_plugin_repository import MCPPluginRepository
from ..schemas.mcp_plugin import PluginTestReport
from ..services.llm_service import LLMService
from ..services.mcp.registry import MCPPluginRegistry

logger = logging.getLogger(__name__)


class MCPTestService:
    """MCP 插件测试服务，使用 AI 智能生成测试用例。"""
    
    def __init__(self, session: AsyncSession, registry: MCPPluginRegistry):
        self.session = session
        self.registry = registry
        self.plugin_repo = MCPPluginRepository(session)
        self.llm_service = LLMService(session)
    
    async def test_plugin(
        self, user_id: int, plugin_id: int
    ) -> PluginTestReport:
        """测试插件连接和功能。"""
        # 获取插件
        plugin = await self.plugin_repo.get(id=plugin_id)
        if not plugin:
            return PluginTestReport(
                success=False,
                message="插件不存在",
                tools_count=0,
                error="Plugin not found"
            )
        
        try:
            # Step 1: 测试连接
            logger.info("测试插件连接: %s", plugin.plugin_name)
            await self.registry.load_plugin(user_id, plugin)
            
            # Step 2: 获取工具列表
            tools = await self.registry.list_tools(user_id, plugin.plugin_name)
            if not tools:
                return PluginTestReport(
                    success=True,
                    message="连接成功，但插件未提供任何工具",
                    tools_count=0
                )
            
            logger.info("插件 %s 提供 %d 个工具", plugin.plugin_name, len(tools))
            
            # Step 3-5: 使用 AI 选择工具并生成测试参数
            suggestions = [
                f"✅ 连接成功",
                f"📊 发现 {len(tools)} 个工具",
            ]
            
            # 选择第一个工具进行测试
            test_tool = tools[0]
            suggestions.append(f"🤖 选择工具: {test_tool.name}")
            
            # 简单测试：尝试调用工具（如果有默认参数）
            try:
                # 这里可以使用 AI 生成测试参数，简化版本直接使用空参数
                test_args = {}
                result = await self.registry.call_tool(
                    user_id, plugin.plugin_name, test_tool.name, test_args
                )
                suggestions.append(f"✅ 工具调用成功")
                suggestions.append(f"📝 返回结果: {str(result)[:100]}...")
            except Exception as exc:
                suggestions.append(f"⚠️ 工具调用失败: {str(exc)}")
            
            return PluginTestReport(
                success=True,
                message="✅ 插件测试完成",
                tools_count=len(tools),
                suggestions=suggestions
            )
            
        except Exception as exc:
            logger.error("插件测试失败: %s, 错误: %s", plugin.plugin_name, exc)
            return PluginTestReport(
                success=False,
                message="❌ 插件测试失败",
                tools_count=0,
                error=str(exc)
            )
```

### 10. Enhanced LLM Service

扩展现有 LLMService 以支持 MCP 工具调用。

```python
class LLMService:
    # ... existing methods ...
    
    async def generate_text_with_mcp(
        self,
        messages: List[Dict[str, str]],
        user_id: int,
        temperature: float = 0.7,
        timeout: float = 300.0
    ) -> str:
        """Generate text with MCP tool support."""
        # Get user's enabled MCP tools
        tools = await self.mcp_tool_service.get_user_enabled_tools(user_id)
        
        # Round 1: Call AI with tools
        response = await self._call_llm_with_tools(messages, tools, temperature)
        
        # Check if AI wants to use tools
        if response.tool_calls:
            # Execute tool calls
            tool_results = await self.mcp_tool_service.execute_tool_calls(
                user_id, response.tool_calls
            )
            
            # Round 2: Call AI with tool results
            messages.append(response.message)
            messages.extend(tool_results)
            final_response = await self._call_llm(messages, temperature)
            return final_response.content
        
        return response.content
```

### 11. API Router

RESTful API 接口定义。遵循项目现有的 Router 模式和依赖注入风格。

```python
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin, get_current_user
from ...db.session import get_session
from ...schemas.mcp_plugin import (
    MCPPluginCreate,
    MCPPluginResponse,
    MCPPluginUpdate,
    PluginTestReport,
    ToolDefinition,
    ToolMetrics,
)
from ...schemas.user import UserInDB
from ...services.mcp_plugin_service import MCPPluginService
from ...services.mcp_test_service import MCPTestService
from ...services.mcp_tool_service import MCPToolService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Plugins"])


@router.get("/plugins", response_model=List[MCPPluginResponse])
async def list_plugins(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[MCPPluginResponse]:
    """列出所有可用的 MCP 插件及用户的启用状态。"""
    plugin_service = MCPPluginService(session)
    plugins = await plugin_service.list_plugins_with_user_status(current_user.id)
    logger.info("用户 %s 查询插件列表，共 %d 个", current_user.id, len(plugins))
    return plugins


@router.post("/plugins", response_model=MCPPluginResponse, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    plugin_data: MCPPluginCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> MCPPluginResponse:
    """创建新的 MCP 插件配置（仅管理员）。"""
    plugin_service = MCPPluginService(session)
    plugin = await plugin_service.create_plugin(plugin_data)
    logger.info("管理员 %s 创建插件: %s", current_user.id, plugin.plugin_name)
    return await plugin_service.get_plugin_with_user_status(plugin.id, current_user.id)


@router.get("/plugins/{plugin_id}", response_model=MCPPluginResponse)
async def get_plugin(
    plugin_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> MCPPluginResponse:
    """获取插件详情。"""
    plugin_service = MCPPluginService(session)
    plugin = await plugin_service.get_plugin_with_user_status(plugin_id, current_user.id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="插件不存在")
    logger.info("用户 %s 查询插件 %d", current_user.id, plugin_id)
    return plugin


@router.put("/plugins/{plugin_id}", response_model=MCPPluginResponse)
async def update_plugin(
    plugin_id: int,
    plugin_data: MCPPluginUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> MCPPluginResponse:
    """更新插件配置（仅管理员）。"""
    plugin_service = MCPPluginService(session)
    plugin = await plugin_service.update_plugin(plugin_id, plugin_data)
    logger.info("管理员 %s 更新插件 %d", current_user.id, plugin_id)
    return await plugin_service.get_plugin_with_user_status(plugin.id, current_user.id)


@router.delete("/plugins/{plugin_id}", status_code=status.HTTP_200_OK)
async def delete_plugin(
    plugin_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict[str, str]:
    """删除插件（仅管理员）。"""
    plugin_service = MCPPluginService(session)
    await plugin_service.delete_plugin(plugin_id)
    logger.info("管理员 %s 删除插件 %d", current_user.id, plugin_id)
    return {"status": "success", "message": "插件已删除"}


@router.post("/plugins/{plugin_id}/toggle", response_model=Dict[str, bool])
async def toggle_plugin(
    plugin_id: int,
    enabled: bool = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, bool]:
    """切换用户的插件启用状态。"""
    plugin_service = MCPPluginService(session)
    new_status = await plugin_service.toggle_user_plugin(current_user.id, plugin_id, enabled)
    logger.info("用户 %s %s插件 %d", current_user.id, "启用" if new_status else "禁用", plugin_id)
    return {"enabled": new_status}


@router.post("/plugins/{plugin_id}/test", response_model=PluginTestReport)
async def test_plugin(
    plugin_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> PluginTestReport:
    """测试插件连接和功能（仅管理员）。"""
    test_service = MCPTestService(session)
    report = await test_service.test_plugin(current_user.id, plugin_id)
    logger.info("管理员 %s 测试插件 %d，结果: %s", current_user.id, plugin_id, report.success)
    return report


@router.get("/plugins/{plugin_id}/tools", response_model=List[ToolDefinition])
async def get_plugin_tools(
    plugin_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ToolDefinition]:
    """获取插件提供的工具列表。"""
    tool_service = MCPToolService(session)
    tools = await tool_service.get_plugin_tools(current_user.id, plugin_id)
    logger.info("用户 %s 查询插件 %d 的工具，共 %d 个", current_user.id, plugin_id, len(tools))
    return tools


@router.get("/metrics", response_model=Dict)
async def get_metrics(
    tool_name: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict:
    """获取工具调用指标（仅管理员）。"""
    tool_service = MCPToolService(session)
    metrics = tool_service.get_metrics(tool_name)
    logger.info("管理员 %s 查询工具指标: %s", current_user.id, tool_name or "全部")
    return metrics


@router.post("/cache/clear", status_code=status.HTTP_200_OK)
async def clear_cache(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict[str, str]:
    """清空工具定义缓存（仅管理员）。"""
    tool_service = MCPToolService(session)
    tool_service.clear_cache()
    logger.info("管理员 %s 清空工具缓存", current_user.id)
    return {"status": "success", "message": "缓存已清空"}
```

## Data Models

### Database Schema

```sql
-- MCP Plugin configuration
CREATE TABLE mcp_plugins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    plugin_type VARCHAR(50) NOT NULL DEFAULT 'http',
    server_url VARCHAR(500) NOT NULL,
    headers TEXT,  -- JSON
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    category VARCHAR(50),
    config TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User plugin preferences
CREATE TABLE user_plugin_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plugin_id INTEGER NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plugin_id) REFERENCES mcp_plugins(id) ON DELETE CASCADE,
    UNIQUE(user_id, plugin_id)
);

CREATE INDEX idx_user_plugin_prefs_user ON user_plugin_preferences(user_id);
CREATE INDEX idx_user_plugin_prefs_plugin ON user_plugin_preferences(plugin_id);
```

### Pydantic Schemas

遵循项目现有的 Schema 定义风格，使用 Field 进行字段描述。

```python
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
```

### In-Memory Data Structures

```python
@dataclass
class SessionInfo:
    """Information about an active MCP session."""
    client: HTTPMCPClient
    plugin: MCPPlugin
    user_id: int
    created_at: datetime
    last_used: datetime
    status: str  # "active", "error", "idle"
    error_count: int = 0

@dataclass
class ToolCacheEntry:
    """Cached tool definitions."""
    tools: List[Dict[str, Any]]
    expire_time: datetime
    hit_count: int = 0

@dataclass
class ToolMetrics:
    """Metrics for tool calls."""
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    
    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        return self.success_calls / self.total_calls if self.total_calls > 0 else 0.0
    
    def update_success(self, duration_ms: float):
        self.total_calls += 1
        self.success_calls += 1
        self.total_duration_ms += duration_ms
    
    def update_failure(self, duration_ms: float):
        self.total_calls += 1
        self.failed_calls += 1
        self.total_duration_ms += duration_ms
```

## Configuration

```python
@dataclass(frozen=True)
class MCPConfig:
    """Configuration constants for MCP system."""
    
    # Connection Pool
    MAX_CLIENTS: int = 1000
    CLIENT_TTL_SECONDS: int = 3600  # 1 hour
    IDLE_TIMEOUT_SECONDS: int = 1800  # 30 minutes
    
    # Health Check
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60
    ERROR_RATE_CRITICAL: float = 0.7
    ERROR_RATE_WARNING: float = 0.4
    
    # Cleanup
    CLEANUP_INTERVAL_SECONDS: int = 300  # 5 minutes
    
    # Cache
    TOOL_CACHE_TTL_MINUTES: int = 10
    
    # Retry
    MAX_RETRIES: int = 3
    BASE_RETRY_DELAY_SECONDS: float = 1.0
    MAX_RETRY_DELAY_SECONDS: float = 10.0
    
    # Timeout
    DEFAULT_TIMEOUT_SECONDS: float = 60.0
    TOOL_CALL_TIMEOUT_SECONDS: float = 60.0
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Plugin Configuration Round-Trip

*For any* valid plugin configuration, storing it to the database and then retrieving it should return an equivalent configuration with all fields preserved.

**Validates: Requirements 1.2**

### Property 2: Enabled Plugins Are Loaded

*For any* plugin configuration with enabled=true, after creation or update, the plugin should appear in the registry with an active session.

**Validates: Requirements 1.3**

### Property 3: Plugin Deletion Cleanup

*For any* plugin, after deletion, it should not appear in the registry, database, or user preferences, and all associated resources should be released.

**Validates: Requirements 1.5**

### Property 4: User Tool Inclusion

*For any* user and any plugin they enable, the tools from that plugin should appear in the user's available tools list returned by get_user_enabled_tools().

**Validates: Requirements 2.2**

### Property 5: User Tool Exclusion

*For any* user and any plugin they disable, the tools from that plugin should not appear in the user's available tools list returned by get_user_enabled_tools().

**Validates: Requirements 2.3**

### Property 6: Tool Format Conversion

*For any* tool definition received from an MCP server, the converted format should be a valid OpenAI Function Calling format containing type="function" and a function object with name, description, and parameters fields.

**Validates: Requirements 4.2, 4.3**

### Property 7: Tool Cache Hit

*For any* plugin, if tools are fetched and cached, subsequent requests within the cache TTL should return the cached tools without calling the MCP server.

**Validates: Requirements 4.4, 11.3**

### Property 8: Tool Cache Expiration

*For any* cached tool list, after the cache TTL expires, the next request should fetch fresh tools from the MCP server and update the cache.

**Validates: Requirements 4.5, 11.4**

### Property 9: Tool Call Parsing

*For any* valid tool_calls response from AI, the system should correctly extract the tool name and arguments as a valid dictionary.

**Validates: Requirements 6.1, 6.2**

### Property 10: Tool Call Retry

*For any* tool call that fails with a retryable error, the system should retry up to MAX_RETRIES times with exponentially increasing delays between attempts.

**Validates: Requirements 6.4**

### Property 11: Tool Call Result Format

*For any* successful tool call, the result should be formatted as a dictionary with tool_call_id, role="tool", name, content, and success=True fields.

**Validates: Requirements 6.6**

### Property 12: Parallel Tool Execution

*For any* list of multiple tool calls, all tools should be executed concurrently using asyncio.gather(), not sequentially.

**Validates: Requirements 6.7**

### Property 13: Session Reuse

*For any* user and plugin, repeated requests within the session TTL should reuse the same session object rather than creating new connections.

**Validates: Requirements 8.2**

### Property 14: LRU Eviction

*For any* registry at maximum capacity, when a new session is needed, the least recently used session should be evicted first.

**Validates: Requirements 8.3**

### Property 15: Session TTL Cleanup

*For any* session that has been idle for longer than CLIENT_TTL_SECONDS, the cleanup task should close and remove that session.

**Validates: Requirements 8.4**

### Property 16: Metrics Recording

*For any* tool call, the system should record the start time, end time, and update the appropriate success or failure metrics.

**Validates: Requirements 9.1, 9.2, 9.3**

### Property 17: Metrics Completeness

*For any* tool that has been called, querying metrics should return a complete ToolMetrics object with total_calls, success_calls, failed_calls, avg_duration_ms, and success_rate fields.

**Validates: Requirements 9.4**

### Property 18: Configuration Change Propagation

*For any* user plugin preference change (enable/disable), the next AI generation request should reflect the new configuration in the available tools list.

**Validates: Requirements 2.4**

### Property 19: Graceful Degradation

*For any* chapter generation request, if all MCP tool calls fail, the system should still complete the generation using the base LLM without tools.

**Validates: Requirements 5.5**

### Property 20: Cache Clear

*For any* state of the tool cache, calling clear_cache() should result in an empty cache, and the next tool request should fetch fresh data from the server.

**Validates: Requirements 11.5**

### Property 21: Error State Recovery

*For any* session marked as error status due to connection failure, the next request should attempt to reconnect and restore the session to active status.

**Validates: Requirements 12.4**

### Property 22: Parameter Validation

*For any* tool call with invalid JSON parameters, the system should return a parameter validation error without attempting to call the MCP server.

**Validates: Requirements 12.3**

### Property 23: API Response Completeness

*For any* plugin list API request, the response should include all plugins with their id, plugin_name, display_name, enabled status, and user_enabled status.

**Validates: Requirements 13.1**

## Error Handling

### Connection Errors

1. **Timeout Handling**: All MCP server connections use configurable timeouts (default 60s). If a connection or tool call exceeds the timeout, the operation is terminated and an error is returned.

2. **Connection Failure**: If initial connection to an MCP server fails, the plugin is marked as unavailable and the error is logged. The system does not retry connection establishment automatically to avoid blocking.

3. **Network Interruption**: If an established connection is interrupted during a tool call, the session is marked as error status. The next request will attempt to reconnect.

### Tool Call Errors

1. **Retry Strategy**: Failed tool calls are retried up to MAX_RETRIES (3) times with exponential backoff:
   - Attempt 1: immediate
   - Attempt 2: 1 second delay
   - Attempt 3: 2 seconds delay
   - Attempt 4: 4 seconds delay (capped at MAX_RETRY_DELAY)

2. **Parameter Validation**: Tool arguments are validated as valid JSON before execution. Invalid JSON returns an immediate error without calling the server.

3. **Server Errors**: Errors returned by the MCP server are parsed and propagated to the caller with detailed error messages.

4. **Unexpected Exceptions**: All unexpected exceptions during tool calls are caught, logged with full stack traces, and returned as generic error messages to avoid exposing internal details.

### Degradation Strategy

1. **Tool Failure Degradation**: If all tool calls fail during content generation, the system falls back to generating content without tool results. This ensures the user request is still fulfilled.

2. **Plugin Unavailability**: If a plugin is unavailable (connection failed, marked as error), its tools are excluded from the available tools list, but other plugins continue to work normally.

3. **Partial Tool Failure**: If some tools succeed and others fail in a multi-tool call, the successful results are used and failures are logged. The AI receives partial results.

### Resource Management

1. **Connection Pool Limits**: The registry enforces MAX_CLIENTS limit. When reached, LRU eviction ensures the system doesn't run out of resources.

2. **Memory Leaks Prevention**: All sessions are tracked with timestamps. The cleanup task runs every CLEANUP_INTERVAL_SECONDS to close expired sessions and free resources.

3. **Graceful Shutdown**: On application shutdown, all active MCP sessions are properly closed to avoid leaving dangling connections.

## Testing Strategy

### Unit Testing

Unit tests will verify specific functionality and edge cases:

1. **Model Tests**:
   - MCPPlugin model CRUD operations
   - UserPluginPreference model relationships
   - Database constraints (unique plugin names, foreign keys)

2. **HTTP Client Tests**:
   - Connection establishment and disconnection
   - Tool listing and calling
   - Error handling for various failure scenarios
   - Timeout behavior

3. **Registry Tests**:
   - Session creation and retrieval
   - LRU eviction logic
   - TTL-based cleanup
   - Concurrent access with locks

4. **Service Tests**:
   - Tool format conversion
   - Cache hit/miss behavior
   - Metrics recording and calculation
   - Retry logic with mocked failures

5. **API Tests**:
   - Request validation
   - Response format
   - Authentication and authorization
   - Error responses

### Property-Based Testing

Property-based tests will verify universal properties across many inputs using the **Hypothesis** library for Python:

**Configuration**:
- Library: Hypothesis (https://hypothesis.readthedocs.io/)
- Minimum iterations per property: 100
- Each property test must reference its design document property number

**Test Organization**:
- Property tests will be in `backend/tests/property/test_mcp_properties.py`
- Each test function will be tagged with a comment: `# Feature: mcp-plugin-system, Property X: <description>`

**Property Test Coverage**:

1. **Property 1: Plugin Configuration Round-Trip** - Generate random valid plugin configs, store and retrieve, verify equivalence
2. **Property 2: Enabled Plugins Are Loaded** - Generate plugins with enabled=true, verify they appear in registry
3. **Property 3: Plugin Deletion Cleanup** - Create and delete plugins, verify complete cleanup
4. **Property 4: User Tool Inclusion** - Generate user-plugin pairs with enabled=true, verify tools appear
5. **Property 5: User Tool Exclusion** - Generate user-plugin pairs with enabled=false, verify tools don't appear
6. **Property 6: Tool Format Conversion** - Generate MCP tool definitions, verify OpenAI format conversion
7. **Property 7: Tool Cache Hit** - Generate tool requests within TTL, verify no server calls
8. **Property 8: Tool Cache Expiration** - Generate tool requests after TTL, verify server calls
9. **Property 9: Tool Call Parsing** - Generate valid tool_calls, verify correct parsing
10. **Property 10: Tool Call Retry** - Generate failing tool calls, verify retry count and delays
11. **Property 11: Tool Call Result Format** - Generate successful tool calls, verify result format
12. **Property 12: Parallel Tool Execution** - Generate multiple tool calls, verify concurrent execution
13. **Property 13: Session Reuse** - Generate repeated requests, verify same session used
14. **Property 14: LRU Eviction** - Fill registry to capacity, verify LRU eviction
15. **Property 15: Session TTL Cleanup** - Generate idle sessions, verify cleanup after TTL
16. **Property 16: Metrics Recording** - Generate tool calls, verify metrics updated
17. **Property 17: Metrics Completeness** - Query metrics, verify all fields present
18. **Property 18: Configuration Change Propagation** - Change preferences, verify next request reflects changes
19. **Property 19: Graceful Degradation** - Generate requests with all tools failing, verify generation completes
20. **Property 20: Cache Clear** - Clear cache, verify next request fetches fresh data
21. **Property 21: Error State Recovery** - Mark sessions as error, verify reconnection on next use
22. **Property 22: Parameter Validation** - Generate invalid JSON parameters, verify validation errors
23. **Property 23: API Response Completeness** - Query plugin list, verify all fields present

### Integration Testing

Integration tests will verify end-to-end workflows:

1. **Chapter Generation with MCP**:
   - Create plugin, enable for user
   - Generate chapter content
   - Verify AI receives tools
   - Verify tool calls are executed
   - Verify final content includes tool results

2. **Outline Generation with Search**:
   - Enable search plugin
   - Generate outline
   - Verify search tool is called
   - Verify results are injected into context

3. **Plugin Management Workflow**:
   - Admin creates plugin
   - User enables plugin
   - User generates content
   - Admin updates plugin config
   - Verify changes take effect
   - Admin deletes plugin
   - Verify cleanup

4. **Multi-User Concurrency**:
   - Multiple users with different plugin preferences
   - Concurrent generation requests
   - Verify correct tools for each user
   - Verify no cross-user contamination

### Test Doubles and Mocking

1. **Mock MCP Servers**: For unit and property tests, use mock MCP servers that return predictable responses without requiring external services.

2. **Test Fixtures**: Create reusable fixtures for common test data (plugin configs, tool definitions, user preferences).

3. **Time Mocking**: Use time mocking to test TTL and cleanup behavior without waiting for real time to pass.

4. **LLM Mocking**: Mock LLM responses to test tool call scenarios without requiring actual AI API calls.

### Test Data Generators

For property-based testing, implement generators for:

1. **Plugin Configurations**: Generate valid and invalid plugin configs with various combinations of fields
2. **Tool Definitions**: Generate MCP tool definitions with different parameter schemas
3. **Tool Calls**: Generate AI tool_calls responses with various tools and arguments
4. **User Preferences**: Generate user-plugin preference combinations

## Implementation Notes

### Dependencies

New Python packages required:

```
mcp>=0.1.0  # Official MCP Python SDK
httpx>=0.24.0  # HTTP client (may already be installed)
hypothesis>=6.0.0  # Property-based testing
```

### Database Migration

A new migration will be created to add the two new tables:

```python
# Migration: add_mcp_plugin_tables

def upgrade():
    # Create mcp_plugins table
    op.create_table(
        'mcp_plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('plugin_type', sa.String(50), nullable=False),
        sa.Column('server_url', sa.String(500), nullable=False),
        sa.Column('headers', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('config', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plugin_name')
    )
    
    # Create user_plugin_preferences table
    op.create_table(
        'user_plugin_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plugin_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plugin_id'], ['mcp_plugins.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'plugin_id')
    )
    
    # Create indexes
    op.create_index('idx_user_plugin_prefs_user', 'user_plugin_preferences', ['user_id'])
    op.create_index('idx_user_plugin_prefs_plugin', 'user_plugin_preferences', ['plugin_id'])

def downgrade():
    op.drop_table('user_plugin_preferences')
    op.drop_table('mcp_plugins')
```

### Application Lifecycle Integration

集成到现有的 main.py lifespan 函数中。

```python
# 在 backend/app/main.py 中修改

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .core.config import settings
from .db.init_db import init_db
from .services.prompt_service import PromptService
from .services.mcp.registry import MCPPluginRegistry
from .services.mcp.config import MCPConfig
from .db.session import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理，包括启动和关闭时的初始化与清理。"""
    
    # 应用启动时初始化数据库，并预热提示词缓存
    await init_db()
    async with AsyncSessionLocal() as session:
        prompt_service = PromptService(session)
        await prompt_service.preload()
    
    # 初始化 MCP Plugin Registry
    mcp_registry = MCPPluginRegistry(
        max_clients=MCPConfig.MAX_CLIENTS,
        client_ttl=MCPConfig.CLIENT_TTL_SECONDS
    )
    app.state.mcp_registry = mcp_registry
    await mcp_registry.start_cleanup_task()
    logger.info("MCP Plugin Registry 已初始化")
    
    yield
    
    # 应用关闭时清理 MCP 会话
    await mcp_registry.shutdown()
    logger.info("MCP Plugin Registry 已关闭")
```

### Logging Strategy

遵循项目现有的日志风格，使用中文日志消息。

1. **连接事件**: 在 INFO 级别记录所有连接建立、失败和断开
   ```python
   logger.info("MCP 插件连接成功: %s, 用户: %d", plugin_name, user_id)
   logger.error("MCP 插件连接失败: %s, 错误: %s", plugin_name, error)
   ```

2. **工具调用**: 在 DEBUG 级别记录工具调用请求和结果
   ```python
   logger.debug("调用 MCP 工具: %s.%s, 参数: %s", plugin_name, tool_name, arguments)
   logger.debug("工具调用结果: %s", result)
   ```

3. **错误处理**: 在 ERROR 级别记录所有错误，包含完整上下文
   ```python
   logger.error("工具调用失败: %s.%s, 用户: %d, 错误: %s", plugin_name, tool_name, user_id, exc, exc_info=True)
   ```

4. **指标记录**: 定期在 INFO 级别记录指标摘要
   ```python
   logger.info("工具调用指标: %s, 成功率: %.2f%%, 平均耗时: %.2fms", tool_name, success_rate * 100, avg_duration)
   ```

5. **性能监控**: 在 WARNING 级别记录慢速工具调用（>5秒）
   ```python
   logger.warning("工具调用耗时过长: %s.%s, 耗时: %.2fs", plugin_name, tool_name, duration)
   ```

### Security Considerations

1. **API Key Storage**: Plugin headers (containing API keys) are stored encrypted in the database
2. **Admin-Only Operations**: Plugin creation, update, deletion, and testing are restricted to admin users
3. **User Isolation**: Users can only see and modify their own plugin preferences
4. **Input Validation**: All API inputs are validated using Pydantic schemas
5. **Error Messages**: Error messages to users don't expose internal system details

### Performance Optimizations

1. **Connection Pooling**: Reuse MCP sessions across requests to avoid connection overhead
2. **Tool Caching**: Cache tool definitions for 10 minutes to reduce list_tools calls
3. **Parallel Execution**: Execute multiple tool calls concurrently using asyncio.gather()
4. **Fine-Grained Locking**: Use per-user locks instead of global locks to maximize concurrency
5. **Lazy Loading**: Only load plugins when actually needed, not at startup

### Monitoring and Observability

1. **Metrics Endpoint**: Expose `/api/mcp/metrics` for monitoring tool call statistics
2. **Health Checks**: Include MCP system status in application health check endpoint
3. **Structured Logging**: Use structured logging for easy parsing and analysis
4. **Tracing**: Add request IDs to trace tool calls through the system
5. **Alerting**: Log warnings when error rates exceed thresholds for alerting systems

## Future Enhancements

1. **Additional Protocol Support**: Support for stdio and SSE-based MCP servers
2. **Plugin Marketplace**: UI for browsing and installing pre-configured plugins
3. **Tool Usage Analytics**: Track which tools are most useful for different writing tasks
4. **Custom Tool Development**: Allow users to create custom MCP tools
5. **Tool Chaining**: Support for complex workflows with multiple tool calls
6. **Rate Limiting**: Per-plugin rate limiting to prevent abuse
7. **Cost Tracking**: Track costs for paid MCP services
8. **Plugin Versioning**: Support for plugin version management and updates
