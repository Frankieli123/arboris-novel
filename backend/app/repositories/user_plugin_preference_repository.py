"""用户插件偏好仓储，负责用户插件偏好的数据库操作。"""

from typing import Optional

from sqlalchemy import and_, or_, select
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
        stmt = select(UserPluginPreference).where(
            and_(
                UserPluginPreference.user_id == user_id,
                UserPluginPreference.plugin_id == plugin_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_user_preferences(self, user_id: int) -> list[UserPluginPreference]:
        """获取用户的所有插件偏好设置。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户的所有插件偏好列表
        """
        stmt = select(UserPluginPreference).where(
            UserPluginPreference.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_plugins(self, user_id: int) -> list[MCPPlugin]:
        """获取用户启用的所有插件（考虑偏好设置）。
        
        此方法实现以下逻辑：
        1. 获取所有可用插件（默认插件 + 用户插件）
        2. 获取用户的偏好设置
        3. 对于每个插件：
           - 如果有用户偏好，使用偏好设置
           - 否则使用插件的默认 enabled 状态
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户启用的插件列表
        """
        # 1. 获取所有可用插件（默认 + 用户）
        all_plugins_stmt = select(MCPPlugin).where(
            or_(
                MCPPlugin.user_id.is_(None),  # 默认插件
                MCPPlugin.user_id == user_id   # 用户插件
            )
        )
        all_plugins_result = await self.session.execute(all_plugins_stmt)
        all_plugins = list(all_plugins_result.scalars().all())
        
        # 2. 获取用户偏好
        prefs_stmt = select(UserPluginPreference).where(
            UserPluginPreference.user_id == user_id
        )
        prefs_result = await self.session.execute(prefs_stmt)
        prefs = {p.plugin_id: p.enabled for p in prefs_result.scalars().all()}
        
        # 3. 过滤启用的插件
        # 规则：用户偏好优先于全局设置
        #      - 如果有用户偏好，使用偏好设置
        #      - 否则使用插件的全局 enabled 状态
        enabled_plugins = []
        for plugin in all_plugins:
            # 如果有用户偏好，使用偏好设置（用户偏好优先）
            if plugin.id in prefs:
                if prefs[plugin.id]:
                    enabled_plugins.append(plugin)
            # 否则使用插件的默认 enabled 状态
            elif plugin.enabled:
                enabled_plugins.append(plugin)
        
        return enabled_plugins

    async def set_user_preference(
        self, user_id: int, plugin_id: int, enabled: bool
    ) -> UserPluginPreference:
        """设置或更新用户的插件偏好。
        
        Args:
            user_id: 用户 ID
            plugin_id: 插件 ID
            enabled: 是否启用
            
        Returns:
            更新后的偏好设置
        """
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
