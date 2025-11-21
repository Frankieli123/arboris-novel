"""MCP 插件管理服务。"""

import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
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
    
    async def create_plugin(self, plugin_data: MCPPluginCreate, user_id: Optional[int] = None) -> MCPPlugin:
        """创建新插件。
        
        Args:
            plugin_data: 插件配置数据
            user_id: 用户 ID，如果为 None 则创建默认插件
            
        Returns:
            创建的插件实例
            
        Raises:
            HTTPException: 409 - 插件名称冲突
        """
        plugin_dict = plugin_data.model_dump()
        
        try:
            if user_id is None:
                # 创建默认插件
                plugin = await self.plugin_repo.create_default_plugin(plugin_dict)
            else:
                # 创建用户插件
                plugin = await self.plugin_repo.create_user_plugin(user_id, plugin_dict)
            
            await self.session.commit()
            await self.session.refresh(plugin)
            
            plugin_type = "默认插件" if user_id is None else f"用户 {user_id} 的插件"
            logger.info("创建%s: %s", plugin_type, plugin.plugin_name)
            return plugin
            
        except IntegrityError as e:
            await self.session.rollback()
            
            # 判断是默认插件还是用户插件的冲突
            if user_id is None:
                error_msg = f"默认插件 '{plugin_data.plugin_name}' 已存在"
                logger.warning("创建默认插件失败，名称冲突: %s", plugin_data.plugin_name)
            else:
                error_msg = f"用户插件 '{plugin_data.plugin_name}' 已存在"
                logger.warning(
                    "创建用户插件失败，名称冲突: user_id=%d plugin_name=%s",
                    user_id,
                    plugin_data.plugin_name
                )
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            ) from e
    
    async def create_default_plugin(self, plugin_data: MCPPluginCreate) -> MCPPlugin:
        """创建默认插件（仅管理员）。
        
        默认插件对所有用户生效。
        
        Args:
            plugin_data: 插件配置数据
            
        Returns:
            创建的默认插件实例
        """
        return await self.create_plugin(plugin_data, user_id=None)
    
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
    
    async def list_default_plugins(self) -> List[MCPPluginResponse]:
        """列出所有默认插件。
        
        默认插件是管理员配置的对所有用户生效的插件（user_id = NULL）。
        
        Returns:
            所有默认插件的响应列表
        """
        plugins = await self.plugin_repo.get_default_plugins()
        
        responses: List[MCPPluginResponse] = []
        for plugin in plugins:
            responses.append(MCPPluginResponse(
                **plugin.__dict__,
                is_default=True,
                user_enabled=None
            ))
        
        logger.info("列出 %d 个默认插件", len(responses))
        return responses
    
    async def list_plugins_with_user_status(
        self, user_id: int
    ) -> List[MCPPluginResponse]:
        """列出所有可用插件及用户的启用状态。
        
        包括默认插件和用户自定义插件，并标注用户的启用偏好。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            所有可用插件的响应列表，包含用户状态
        """
        # 获取所有可用插件（默认 + 用户）
        plugins = await self.plugin_repo.get_all_available_plugins(user_id)
        
        # 获取用户偏好
        prefs = await self.user_pref_repo.get_user_preferences(user_id)
        pref_map = {p.plugin_id: p.enabled for p in prefs}
        
        responses: List[MCPPluginResponse] = []
        for plugin in plugins:
            # 标注是否为默认插件
            is_default = plugin.user_id is None
            
            # 标注用户状态
            if plugin.id in pref_map:
                user_enabled = pref_map[plugin.id]
            else:
                user_enabled = plugin.enabled  # 使用默认值
            
            responses.append(MCPPluginResponse(
                **plugin.__dict__,
                is_default=is_default,
                user_enabled=user_enabled
            ))
        
        logger.info("列出用户 %d 的 %d 个可用插件", user_id, len(responses))
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
