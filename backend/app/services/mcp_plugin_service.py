"""MCP 插件管理服务。"""

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
