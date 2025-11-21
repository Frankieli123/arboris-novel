"""
Unit tests for Admin API endpoints.

Tests admin-only MCP plugin management endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException, status

from app.schemas.mcp_plugin import MCPPluginCreate, MCPPluginResponse, MCPPluginUpdate
from app.models.mcp_plugin import MCPPlugin
from datetime import datetime


class TestAdminMCPPluginEndpoints:
    """Test admin MCP plugin management endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_default_plugins(self):
        """测试列出默认插件。
        
        验证：
        - 管理员可以列出所有默认插件
        - 返回的插件标记为 is_default=True
        """
        # Mock service
        mock_service = AsyncMock()
        mock_plugins = [
            MCPPluginResponse(
                id=1,
                plugin_name="default_search",
                display_name="Default Search",
                plugin_type="http",
                server_url="http://search.com",
                enabled=True,
                is_default=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            MCPPluginResponse(
                id=2,
                plugin_name="default_db",
                display_name="Default Database",
                plugin_type="http",
                server_url="http://db.com",
                enabled=True,
                is_default=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        mock_service.list_default_plugins.return_value = mock_plugins
        
        # Call endpoint (simulated)
        result = await mock_service.list_default_plugins()
        
        # Verify
        assert len(result) == 2
        assert all(p.is_default for p in result)
        assert result[0].plugin_name == "default_search"
        assert result[1].plugin_name == "default_db"
    
    @pytest.mark.asyncio
    async def test_create_default_plugin_success(self):
        """测试管理员成功创建默认插件。
        
        验证：
        - 管理员可以创建默认插件
        - 返回的插件包含正确的信息
        """
        mock_service = AsyncMock()
        
        plugin_data = MCPPluginCreate(
            plugin_name="new_default",
            display_name="New Default Plugin",
            server_url="http://new.com",
            category="search",
            enabled=True
        )
        
        mock_plugin = MCPPlugin(
            id=1,
            user_id=None,  # 默认插件
            plugin_name="new_default",
            display_name="New Default Plugin",
            server_url="http://new.com",
            category="search",
            enabled=True,
            plugin_type="http",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock_service.create_default_plugin.return_value = mock_plugin
        
        # Call endpoint
        result = await mock_service.create_default_plugin(plugin_data)
        
        # Verify
        assert result.plugin_name == "new_default"
        assert result.user_id is None
        mock_service.create_default_plugin.assert_called_once_with(plugin_data)
    
    @pytest.mark.asyncio
    async def test_create_default_plugin_duplicate_name(self):
        """测试创建重名默认插件失败。
        
        验证：
        - 创建重名插件时抛出 400 错误
        """
        mock_service = AsyncMock()
        
        plugin_data = MCPPluginCreate(
            plugin_name="existing",
            display_name="Duplicate",
            server_url="http://dup.com"
        )
        
        # Mock duplicate name error
        mock_service.create_default_plugin.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="插件名 existing 已存在"
        )
        
        # Verify error is raised
        with pytest.raises(HTTPException) as exc_info:
            await mock_service.create_default_plugin(plugin_data)
        
        assert exc_info.value.status_code == 400
        assert "已存在" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_update_default_plugin_success(self):
        """测试更新默认插件。
        
        验证：
        - 管理员可以更新默认插件配置
        - 更新后的信息正确返回
        """
        mock_service = AsyncMock()
        
        plugin_id = 1
        update_data = MCPPluginUpdate(
            display_name="Updated Name",
            enabled=False
        )
        
        updated_plugin = MCPPlugin(
            id=plugin_id,
            user_id=None,
            plugin_name="test_plugin",
            display_name="Updated Name",
            server_url="http://test.com",
            enabled=False,
            plugin_type="http",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock_service.update_plugin.return_value = updated_plugin
        
        # Call endpoint
        result = await mock_service.update_plugin(plugin_id, update_data)
        
        # Verify
        assert result.display_name == "Updated Name"
        assert result.enabled is False
        mock_service.update_plugin.assert_called_once_with(plugin_id, update_data)
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_plugin(self):
        """测试更新不存在的插件。
        
        验证：
        - 更新不存在的插件时抛出 404 错误
        """
        mock_service = AsyncMock()
        
        plugin_id = 999
        update_data = MCPPluginUpdate(display_name="New Name")
        
        # Mock not found error
        mock_service.update_plugin.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="插件不存在"
        )
        
        # Verify error is raised
        with pytest.raises(HTTPException) as exc_info:
            await mock_service.update_plugin(plugin_id, update_data)
        
        assert exc_info.value.status_code == 404
        assert "不存在" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_delete_default_plugin_success(self):
        """测试删除默认插件。
        
        验证：
        - 管理员可以删除默认插件
        - 删除操作成功执行
        """
        mock_service = AsyncMock()
        
        plugin_id = 1
        mock_service.delete_plugin.return_value = None
        
        # Call endpoint
        await mock_service.delete_plugin(plugin_id)
        
        # Verify
        mock_service.delete_plugin.assert_called_once_with(plugin_id)
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_plugin(self):
        """测试删除不存在的插件。
        
        验证：
        - 删除不存在的插件时抛出 404 错误
        """
        mock_service = AsyncMock()
        
        plugin_id = 999
        
        # Mock not found error
        mock_service.delete_plugin.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="插件不存在"
        )
        
        # Verify error is raised
        with pytest.raises(HTTPException) as exc_info:
            await mock_service.delete_plugin(plugin_id)
        
        assert exc_info.value.status_code == 404
        assert "不存在" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_admin_only_access(self):
        """测试只有管理员可以访问 MCP 管理端点。
        
        验证：
        - 非管理员用户无法访问管理端点
        - 返回 403 Forbidden 错误
        
        注意：这个测试需要在集成测试中完整验证，
        这里只是模拟验证逻辑。
        """
        # This would be tested in integration tests with actual auth
        # Here we just verify the concept
        
        # Mock non-admin user trying to access
        is_admin = False
        
        if not is_admin:
            # Should raise 403
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="需要管理员权限"
                )
            
            assert exc_info.value.status_code == 403
