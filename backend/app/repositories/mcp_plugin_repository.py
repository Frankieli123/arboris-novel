"""MCP 插件仓储，负责插件配置的数据库操作。"""

import json
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.mcp_plugin import MCPPlugin
from .base import BaseRepository


class MCPPluginRepository(BaseRepository[MCPPlugin]):
    """MCP 插件仓储，负责插件配置的数据库操作。"""

    model = MCPPlugin

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    def _prepare_plugin_data(self, plugin_data: dict) -> dict:
        """确保 JSON 字段使用字符串形式存储到数据库中。"""
        data = dict(plugin_data) if plugin_data is not None else {}
        for key in ("headers", "config"):
            if key not in data:
                continue
            value = data[key]
            if value is None or isinstance(value, str):
                continue
            data[key] = json.dumps(value, ensure_ascii=False)
        return data

    async def update_fields(self, instance: MCPPlugin, **values) -> MCPPlugin:
        prepared_values = self._prepare_plugin_data(values)
        return await super().update_fields(instance, **prepared_values)

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

    async def get_default_plugins(self) -> list[MCPPlugin]:
        """获取所有默认插件（user_id = NULL）。
        
        默认插件是管理员配置的对所有用户生效的插件。
        
        Returns:
            所有默认插件的列表
        """
        stmt = select(MCPPlugin).where(MCPPlugin.user_id.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_plugins(self, user_id: int) -> list[MCPPlugin]:
        """获取用户自定义插件。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            该用户的自定义插件列表
        """
        stmt = select(MCPPlugin).where(MCPPlugin.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_available_plugins(self, user_id: int) -> list[MCPPlugin]:
        """获取用户可用的所有插件（默认插件 + 用户插件）。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            默认插件和该用户自定义插件的合并列表
        """
        stmt = select(MCPPlugin).where(
            or_(
                MCPPlugin.user_id.is_(None),  # 默认插件
                MCPPlugin.user_id == user_id   # 用户插件
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_default_plugin(self, plugin_data: dict) -> MCPPlugin:
        """创建默认插件（user_id = NULL）。
        
        Args:
            plugin_data: 插件配置数据
            
        Returns:
            创建的默认插件实例
        """
        prepared_data = self._prepare_plugin_data(plugin_data)
        plugin = MCPPlugin(
            user_id=None,  # 关键：设置为 NULL 标识默认插件
            **prepared_data
        )
        await self.add(plugin)
        return plugin

    async def create_user_plugin(self, user_id: int, plugin_data: dict) -> MCPPlugin:
        """创建用户插件。
        
        Args:
            user_id: 用户 ID
            plugin_data: 插件配置数据
            
        Returns:
            创建的用户插件实例
        """
        prepared_data = self._prepare_plugin_data(plugin_data)
        plugin = MCPPlugin(
            user_id=user_id,  # 关键：设置为用户ID
            **prepared_data
        )
        await self.add(plugin)
        return plugin
