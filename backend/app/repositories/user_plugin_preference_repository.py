"""用户插件偏好仓储，负责用户插件偏好的数据库操作。"""

from typing import Optional

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
        stmt = select(UserPluginPreference).where(
            and_(
                UserPluginPreference.user_id == user_id,
                UserPluginPreference.plugin_id == plugin_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_enabled_plugins(self, user_id: int) -> list[MCPPlugin]:
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
