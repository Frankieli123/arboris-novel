"""MCP 插件测试服务。

参考 MuMu 项目的测试行为：
- 主要验证 MCP 插件的连接与工具列表获取是否正常
- 不在此处执行复杂的 AI 测试用例与多轮调用，保持测试快速、可靠
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..mcp.registry import MCPPluginRegistry
from ..repositories.mcp_plugin_repository import MCPPluginRepository
from ..schemas.mcp_plugin import PluginTestReport

logger = logging.getLogger(__name__)


class MCPTestService:
    """MCP 插件测试服务，使用 AI 智能生成测试用例。"""
    
    def __init__(self, session: AsyncSession, registry: MCPPluginRegistry):
        self.session = session
        self.registry = registry
        self.plugin_repo = MCPPluginRepository(session)
    
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
    
    async def test_plugin(
        self, user_id: int, plugin_id: int
    ) -> PluginTestReport:
        """测试插件连接和工具列表获取情况（MuMu 风格的简化测试）。
        
        只验证：
        - 是否能成功建立 MCP 会话
        - 是否能在合理时间内获取工具列表
        不再尝试实际调用某个工具，以保证测试快速、稳定。
        """
        # 获取插件
        plugin = await self.plugin_repo.get(id=plugin_id)
        if not plugin:
            return PluginTestReport(
                success=False,
                message="插件不存在",
                tools_count=0,
                suggestions=[],
                error="Plugin not found",
            )

        start_time = datetime.now()

        try:
            headers = self._get_plugin_headers(plugin)

            # Step 1: 确保插件客户端已创建（不在此处强制连接远端）
            logger.info("测试插件连接: %s", plugin.plugin_name)
            await self.registry.load_plugin(
                user_id,
                plugin.plugin_name,
                plugin.server_url,
                headers,
            )

            # Step 2: 尝试获取工具列表（内部已带超时控制）
            tools = await self.registry.list_tools(
                user_id,
                plugin.plugin_name,
                plugin.server_url,
                headers,
            )

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            tools_count = len(tools) if tools else 0

            suggestions: List[str] = [
                f"响应时间: {duration_ms:.2f}ms",
            ]

            if tools_count == 0:
                message = "连接成功，但插件未提供任何工具"
            else:
                message = "连接测试成功"
                suggestions.append(f"发现 {tools_count} 个工具")

                # 最多展示前 5 个工具名称，保持输出简洁
                for i, tool in enumerate(tools[:5], 1):
                    name = getattr(tool, "name", None) or str(tool)
                    suggestions.append(f"工具 {i}: {name}")

                if tools_count > 5:
                    suggestions.append(f"... 还有 {tools_count - 5} 个工具")

            logger.info("插件 %s 测试完成，工具数: %d", plugin.plugin_name, tools_count)

            return PluginTestReport(
                success=True,
                message=message,
                tools_count=tools_count,
                suggestions=suggestions,
                error=None,
            )

        except Exception as exc:
            logger.error("插件测试失败: %s, 错误: %s", plugin.plugin_name, exc)
            return PluginTestReport(
                success=False,
                message="插件测试失败",
                tools_count=0,
                suggestions=[],
                error=str(exc),
            )
