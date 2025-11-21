"""MCP 工具服务。

负责工具获取、调用和指标记录。
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..mcp.config import MCPConfig
from ..mcp.registry import MCPPluginRegistry
from ..repositories.mcp_plugin_repository import MCPPluginRepository
from ..repositories.user_plugin_preference_repository import UserPluginPreferenceRepository

logger = logging.getLogger(__name__)


@dataclass
class ToolCacheEntry:
    """缓存的工具定义。"""
    tools: List[Dict[str, Any]]
    expire_time: datetime
    hit_count: int = 0


@dataclass
class ToolMetrics:
    """工具调用指标。"""
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    
    @property
    def avg_duration_ms(self) -> float:
        """平均执行时间（毫秒）。"""
        return self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """成功率。"""
        return self.success_calls / self.total_calls if self.total_calls > 0 else 0.0
    
    def update_success(self, duration_ms: float) -> None:
        """更新成功指标。"""
        self.total_calls += 1
        self.success_calls += 1
        self.total_duration_ms += duration_ms
    
    def update_failure(self, duration_ms: float) -> None:
        """更新失败指标。"""
        self.total_calls += 1
        self.failed_calls += 1
        self.total_duration_ms += duration_ms


class MCPToolService:
    """MCP 工具服务，负责工具获取、调用和指标记录。"""
    
    def __init__(self, session: AsyncSession, registry: MCPPluginRegistry):
        self.session = session
        self.registry = registry
        self.plugin_repo = MCPPluginRepository(session)
        self.user_pref_repo = UserPluginPreferenceRepository(session)
        self._tool_cache: Dict[str, ToolCacheEntry] = {}
        self._metrics: Dict[str, ToolMetrics] = {}
    
    def _get_plugin_headers(self, plugin) -> Optional[Dict[str, Any]]:
        """将插件的 headers 字段解析为字典。"""
        headers = getattr(plugin, "headers", None)
        if headers is None or isinstance(headers, dict):
            return headers
        if isinstance(headers, str):
            value = headers.strip()
            if not value:
                return None
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
                logger.warning(
                    "插件 %s headers 反序列化结果不是字典: %s",
                    plugin.plugin_name,
                    type(parsed).__name__,
                )
            except json.JSONDecodeError as exc:
                logger.warning(
                    "插件 %s headers 不是有效 JSON，已忽略: %s",
                    plugin.plugin_name,
                    exc,
                )
        return None
    
    async def get_user_enabled_tools(
        self, user_id: int
    ) -> List[Dict[str, Any]]:
        """获取用户启用的所有 MCP 工具，转换为 OpenAI Function Calling 格式。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            OpenAI Function Calling 格式的工具列表
        """
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
                    mcp_tools = await self.registry.list_tools(
                        user_id,
                        plugin.plugin_name,
                        plugin.server_url,
                        self._get_plugin_headers(plugin)
                    )
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
        """并行执行多个工具调用。
        
        Args:
            user_id: 用户 ID
            tool_calls: 工具调用列表
            
        Returns:
            工具调用结果列表
        """
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
        """执行单个工具调用，带重试机制。
        
        Args:
            user_id: 用户 ID
            tool_call: 工具调用信息
            
        Returns:
            工具调用结果
        """
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
        
        # 获取插件信息
        plugin = await self.plugin_repo.get_by_name(plugin_name)
        if not plugin:
            logger.error("插件不存在: %s", plugin_name)
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": full_tool_name,
                "content": json.dumps({"error": "插件不存在"}, ensure_ascii=False),
                "success": False
            }
        
        # 执行工具调用
        start_time = datetime.now()
        try:
            result = await self._call_tool_with_retry(
                user_id, plugin, tool_name, arguments,
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
        self, user_id: int, plugin: Any,
        tool_name: str, arguments: dict, timeout: float
    ) -> Any:
        """带指数退避的工具调用重试。
        
        Args:
            user_id: 用户 ID
            plugin: 插件对象
            tool_name: 工具名称
            arguments: 工具参数
            timeout: 超时时间
            
        Returns:
            工具执行结果
            
        Raises:
            Exception: 达到最大重试次数后仍失败
        """
        last_exception = None
        
        for attempt in range(MCPConfig.MAX_RETRIES):
            try:
                result = await self.registry.call_tool(
                    user_id,
                    plugin.plugin_name,
                    plugin.server_url,
                    tool_name,
                    arguments,
                    self._get_plugin_headers(plugin)
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
                        plugin.plugin_name, tool_name, exc
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "工具调用达到最大重试次数: %s.%s, 错误: %s",
                        plugin.plugin_name, tool_name, exc
                    )
        
        raise last_exception
    
    def _convert_to_openai_format(
        self, mcp_tools: List[Any], plugin_name: str
    ) -> List[Dict[str, Any]]:
        """将 MCP 工具定义转换为 OpenAI Function Calling 格式。
        
        Args:
            mcp_tools: MCP 工具定义列表
            plugin_name: 插件名称
            
        Returns:
            OpenAI Function Calling 格式的工具列表
        """
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
        """获取工具调用指标。
        
        Args:
            tool_name: 可选的工具名称，如果不提供则返回所有工具的指标
            
        Returns:
            工具指标字典
        """
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
    
    async def get_plugin_tools(
        self, user_id: int, plugin_name: str
    ) -> List[Dict[str, Any]]:
        """获取指定插件的工具列表。
        
        Args:
            user_id: 用户 ID
            plugin_name: 插件名称
            
        Returns:
            OpenAI Function Calling 格式的工具列表
        """
        # 获取插件信息
        plugin = await self.plugin_repo.get_by_name(plugin_name)
        if not plugin:
            logger.error("插件不存在: %s", plugin_name)
            return []
        
        # 检查缓存
        cache_key = f"{user_id}:{plugin_name}"
        cached = self._tool_cache.get(cache_key)
        
        if cached and cached.expire_time > datetime.now():
            # 缓存命中
            cached.hit_count += 1
            logger.debug("工具缓存命中: %s (命中次数: %d)", cache_key, cached.hit_count)
            return cached.tools
        
        # 缓存未命中，从注册表获取
        try:
            mcp_tools = await self.registry.list_tools(
                user_id,
                plugin.plugin_name,
                plugin.server_url,
                self._get_plugin_headers(plugin)
            )
            converted_tools = self._convert_to_openai_format(mcp_tools, plugin.plugin_name)
            
            # 更新缓存
            expire_time = datetime.now() + timedelta(minutes=MCPConfig.TOOL_CACHE_TTL_MINUTES)
            self._tool_cache[cache_key] = ToolCacheEntry(
                tools=converted_tools,
                expire_time=expire_time,
                hit_count=0
            )
            logger.info("工具列表已缓存: %s (工具数: %d)", cache_key, len(converted_tools))
            return converted_tools
        except Exception as exc:
            logger.error("获取插件工具失败: %s, 错误: %s", plugin.plugin_name, exc)
            raise
    
    def clear_cache(self) -> None:
        """清空工具定义缓存。"""
        self._tool_cache.clear()
        logger.info("工具缓存已清空")
