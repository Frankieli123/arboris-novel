"""MCP 插件仓储，负责插件配置的数据库操作。"""

from typing import Optional

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
        stmt = select(MCPPlugin).where(MCPPlugin.plugin_name == plugin_name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_enabled(self) -> list[MCPPlugin]:
        """获取所有全局启用的插件。"""
        stmt = select(MCPPlugin).where(MCPPlugin.enabled == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_category(self, category: str) -> list[MCPPlugin]:
        """根据分类获取插件列表。"""
        stmt = select(MCPPlugin).where(MCPPlugin.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
