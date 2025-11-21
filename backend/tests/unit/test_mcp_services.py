"""
Unit tests for MCP Plugin Service layer.

Tests business logic, error handling, and service interactions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.mcp_plugin_service import MCPPluginService
from app.services.mcp_tool_service import MCPToolService
from app.models.mcp_plugin import MCPPlugin
from app.schemas.mcp_plugin import MCPPluginCreate, MCPPluginUpdate
from fastapi import HTTPException


class TestMCPPluginService:
    """Test MCPPluginService business logic."""
    
    @pytest.mark.asyncio
    async def test_create_plugin_success(self):
        """Test successful plugin creation."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        
        # Mock repository methods
        mock_repo.get_by_name.return_value = None  # No existing plugin
        mock_plugin = MCPPlugin(
            id=1,
            plugin_name="test_plugin",
            display_name="Test Plugin",
            server_url="http://localhost:8000"
        )
        mock_repo.add.return_value = mock_plugin
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_repo
            
            plugin_data = MCPPluginCreate(
                plugin_name="test_plugin",
                display_name="Test Plugin",
                server_url="http://localhost:8000"
            )
            
            result = await service.create_plugin(plugin_data)
            
            assert result.plugin_name == "test_plugin"
            mock_repo.add.assert_called_once()
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_plugin_duplicate_name(self):
        """Test that creating a plugin with duplicate name raises error."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        
        # Mock existing plugin
        existing_plugin = MCPPlugin(
            id=1,
            plugin_name="existing",
            display_name="Existing",
            server_url="http://localhost:8000"
        )
        mock_repo.get_by_name.return_value = existing_plugin
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_repo
            
            plugin_data = MCPPluginCreate(
                plugin_name="existing",
                display_name="New",
                server_url="http://localhost:8001"
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await service.create_plugin(plugin_data)
            
            assert exc_info.value.status_code == 400
            assert "已存在" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_update_plugin_success(self):
        """Test successful plugin update."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        
        existing_plugin = MCPPlugin(
            id=1,
            plugin_name="test",
            display_name="Original",
            server_url="http://localhost:8000"
        )
        mock_repo.get.return_value = existing_plugin
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_repo
            
            update_data = MCPPluginUpdate(display_name="Updated")
            
            result = await service.update_plugin(1, update_data)
            
            mock_repo.update_fields.assert_called_once()
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_plugin(self):
        """Test updating a plugin that doesn't exist."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_repo
            
            update_data = MCPPluginUpdate(display_name="Updated")
            
            with pytest.raises(HTTPException) as exc_info:
                await service.update_plugin(999, update_data)
            
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_plugin_success(self):
        """Test successful plugin deletion."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        
        plugin = MCPPlugin(
            id=1,
            plugin_name="test",
            display_name="Test",
            server_url="http://localhost:8000"
        )
        mock_repo.get.return_value = plugin
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_repo
            
            await service.delete_plugin(1)
            
            mock_repo.delete.assert_called_once_with(plugin)
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_plugin(self):
        """Test deleting a plugin that doesn't exist."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_repo
            
            with pytest.raises(HTTPException) as exc_info:
                await service.delete_plugin(999)
            
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_toggle_user_plugin_enable(self):
        """Test enabling a plugin for a user."""
        mock_session = AsyncMock()
        mock_plugin_repo = AsyncMock()
        mock_pref_repo = AsyncMock()
        
        plugin = MCPPlugin(
            id=1,
            plugin_name="test",
            display_name="Test",
            server_url="http://localhost:8000"
        )
        mock_plugin_repo.get.return_value = plugin
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_plugin_repo), \
             patch('app.services.mcp_plugin_service.UserPluginPreferenceRepository', return_value=mock_pref_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_plugin_repo
            service.user_pref_repo = mock_pref_repo
            
            result = await service.toggle_user_plugin(1, 1, True)
            
            assert result is True
            mock_pref_repo.set_user_preference.assert_called_once_with(1, 1, True)
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_toggle_nonexistent_plugin(self):
        """Test toggling a plugin that doesn't exist."""
        mock_session = AsyncMock()
        mock_plugin_repo = AsyncMock()
        mock_pref_repo = AsyncMock()
        mock_plugin_repo.get.return_value = None
        
        with patch('app.services.mcp_plugin_service.MCPPluginRepository', return_value=mock_plugin_repo), \
             patch('app.services.mcp_plugin_service.UserPluginPreferenceRepository', return_value=mock_pref_repo):
            service = MCPPluginService(mock_session)
            service.plugin_repo = mock_plugin_repo
            service.user_pref_repo = mock_pref_repo
            
            with pytest.raises(HTTPException) as exc_info:
                await service.toggle_user_plugin(1, 999, True)
            
            assert exc_info.value.status_code == 404


class TestMCPToolService:
    """Test MCPToolService business logic."""
    
    @pytest.mark.asyncio
    async def test_tool_format_conversion(self):
        """Test converting MCP tools to OpenAI format."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        # Mock MCP tool
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search the web"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
        
        result = service._convert_to_openai_format([mock_tool], "test_plugin")
        
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "test_plugin.search"
        assert result[0]["function"]["description"] == "Search the web"
        assert "parameters" in result[0]["function"]
    
    @pytest.mark.asyncio
    async def test_tool_format_conversion_no_description(self):
        """Test converting tool with no description."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        mock_tool = MagicMock()
        mock_tool.name = "tool"
        mock_tool.description = None
        mock_tool.inputSchema = {"type": "object", "properties": {}}
        
        result = service._convert_to_openai_format([mock_tool], "plugin")
        
        assert result[0]["function"]["description"] == ""
    
    @pytest.mark.asyncio
    async def test_tool_format_conversion_no_schema(self):
        """Test converting tool with no input schema."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        mock_tool = MagicMock()
        mock_tool.name = "tool"
        mock_tool.description = "Test"
        mock_tool.inputSchema = None
        
        result = service._convert_to_openai_format([mock_tool], "plugin")
        
        # Should have default schema
        assert result[0]["function"]["parameters"]["type"] == "object"
        assert result[0]["function"]["parameters"]["properties"] == {}
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test clearing the tool cache."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        # Add some cache entries
        service._tool_cache["key1"] = MagicMock()
        service._tool_cache["key2"] = MagicMock()
        
        service.clear_cache()
        
        assert len(service._tool_cache) == 0
    
    @pytest.mark.asyncio
    async def test_get_metrics_for_specific_tool(self):
        """Test getting metrics for a specific tool."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        # Create mock metrics
        from app.services.mcp_tool_service import ToolMetrics
        metrics = ToolMetrics()
        metrics.update_success(100.0)
        metrics.update_success(200.0)
        metrics.update_failure(150.0)
        
        service._metrics["plugin.tool"] = metrics
        
        result = service.get_metrics("plugin.tool")
        
        assert result["tool_name"] == "plugin.tool"
        assert result["total_calls"] == 3
        assert result["success_calls"] == 2
        assert result["failed_calls"] == 1
        assert result["avg_duration_ms"] == 150.0
        assert result["success_rate"] == pytest.approx(2/3)
    
    @pytest.mark.asyncio
    async def test_get_metrics_for_nonexistent_tool(self):
        """Test getting metrics for a tool that hasn't been called."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        result = service.get_metrics("nonexistent.tool")
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_get_all_metrics(self):
        """Test getting metrics for all tools."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        # Create metrics for multiple tools
        from app.services.mcp_tool_service import ToolMetrics
        
        metrics1 = ToolMetrics()
        metrics1.update_success(100.0)
        service._metrics["plugin1.tool1"] = metrics1
        
        metrics2 = ToolMetrics()
        metrics2.update_success(200.0)
        service._metrics["plugin2.tool2"] = metrics2
        
        result = service.get_metrics()
        
        assert len(result) == 2
        assert "plugin1.tool1" in result
        assert "plugin2.tool2" in result
    
    @pytest.mark.asyncio
    async def test_execute_empty_tool_calls(self):
        """Test executing empty tool calls list."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        result = await service.execute_tool_calls(1, [])
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_tool_call_with_invalid_json_parameters(self):
        """Test tool call with invalid JSON parameters."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        
        service = MCPToolService(mock_session, mock_registry)
        
        tool_call = {
            "id": "call_123",
            "function": {
                "name": "plugin.tool",
                "arguments": "invalid json {"
            }
        }
        
        result = await service._execute_single_tool(1, tool_call)
        
        assert result["success"] is False
        assert "参数格式错误" in result["content"]
    
    @pytest.mark.asyncio
    async def test_tool_call_without_plugin_separator(self):
        """Test tool call with name that doesn't have plugin.tool format."""
        mock_session = AsyncMock()
        mock_registry = AsyncMock()
        mock_plugin_repo = AsyncMock()
        
        # Mock plugin lookup
        mock_plugin = MCPPlugin(
            id=1,
            plugin_name="toolname",
            display_name="Tool",
            server_url="http://localhost:8000"
        )
        mock_plugin_repo.get_by_name.return_value = mock_plugin
        
        service = MCPToolService(mock_session, mock_registry)
        service.plugin_repo = mock_plugin_repo
        
        tool_call = {
            "id": "call_123",
            "function": {
                "name": "toolname",  # No dot separator
                "arguments": "{}"
            }
        }
        
        # Should use the name as both plugin and tool
        mock_registry.call_tool.return_value = {"result": "success"}
        
        result = await service._execute_single_tool(1, tool_call)
        
        # Should still work, using name for both plugin and tool
        assert result["tool_call_id"] == "call_123"


class TestToolMetrics:
    """Test ToolMetrics data class."""
    
    def test_initial_metrics(self):
        """Test initial metrics values."""
        from app.services.mcp_tool_service import ToolMetrics
        
        metrics = ToolMetrics()
        
        assert metrics.total_calls == 0
        assert metrics.success_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.total_duration_ms == 0.0
        assert metrics.avg_duration_ms == 0.0
        assert metrics.success_rate == 0.0
    
    def test_update_success(self):
        """Test updating metrics with successful call."""
        from app.services.mcp_tool_service import ToolMetrics
        
        metrics = ToolMetrics()
        metrics.update_success(100.0)
        
        assert metrics.total_calls == 1
        assert metrics.success_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.total_duration_ms == 100.0
        assert metrics.avg_duration_ms == 100.0
        assert metrics.success_rate == 1.0
    
    def test_update_failure(self):
        """Test updating metrics with failed call."""
        from app.services.mcp_tool_service import ToolMetrics
        
        metrics = ToolMetrics()
        metrics.update_failure(50.0)
        
        assert metrics.total_calls == 1
        assert metrics.success_calls == 0
        assert metrics.failed_calls == 1
        assert metrics.total_duration_ms == 50.0
        assert metrics.avg_duration_ms == 50.0
        assert metrics.success_rate == 0.0
    
    def test_mixed_metrics(self):
        """Test metrics with mixed success and failure."""
        from app.services.mcp_tool_service import ToolMetrics
        
        metrics = ToolMetrics()
        metrics.update_success(100.0)
        metrics.update_success(200.0)
        metrics.update_failure(150.0)
        
        assert metrics.total_calls == 3
        assert metrics.success_calls == 2
        assert metrics.failed_calls == 1
        assert metrics.total_duration_ms == 450.0
        assert metrics.avg_duration_ms == 150.0
        assert metrics.success_rate == pytest.approx(2/3)
