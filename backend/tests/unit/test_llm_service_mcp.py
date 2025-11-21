"""
Unit tests for LLM Service MCP integration.

Tests the generate_with_mcp() method and related functionality.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Set required environment variables before importing app modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.mcp_plugin import MCPPlugin
from app.services.llm_service import LLMService
from app.services.mcp_tool_service import MCPToolService
from app.services.mcp_plugin_service import MCPPluginService
from app.schemas.mcp_plugin import MCPPluginCreate
from app.mcp.registry import MCPPluginRegistry
from app.db.base import Base


# Test database context manager
class DatabaseContext:
    """Context manager for creating test database sessions."""
    
    def __init__(self):
        self.engine = None
        self.session = None
    
    async def __aenter__(self):
        """Create database and session."""
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
        self.session = async_session()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session and dispose engine."""
        if self.session:
            await self.session.close()
        if self.engine:
            await self.engine.dispose()


def create_mock_registry():
    """Create a mock MCP Plugin Registry."""
    registry = MagicMock(spec=MCPPluginRegistry)
    registry.load_plugin = AsyncMock()
    registry.unload_plugin = AsyncMock()
    registry.get_client = AsyncMock()
    registry.list_tools = AsyncMock(return_value=[])
    registry.call_tool = AsyncMock(return_value={"result": "success"})
    return registry


class TestGenerateWithMCPDegradation:
    """Test suite for generate_with_mcp() degradation scenarios."""
    
    @pytest.mark.asyncio
    async def test_degradation_when_no_tools_available(self):
        """
        Test that system degrades to normal generation when no tools are available.
        
        Requirements: 9.5
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock get_user_enabled_tools to return empty list
            with patch.object(tool_service, 'get_user_enabled_tools', new=AsyncMock(return_value=[])):
                # Mock normal generation
                normal_response = "Normal generation response"
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=normal_response)):
                    result = await llm_service.generate_with_mcp(
                        prompt="Test prompt",
                        user_id=1,
                        enable_mcp=True
                    )
                    
                    assert result["content"] == normal_response
                    assert result["mcp_enhanced"] is False
                    assert result["tool_calls_made"] == 0
                    assert result["tools_used"] == []
                    assert result["finish_reason"] == "stop"
    
    @pytest.mark.asyncio
    async def test_degradation_when_tool_fetch_fails(self):
        """
        Test that system degrades to normal generation when tool fetching fails.
        
        Requirements: 9.5
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock get_user_enabled_tools to raise exception
            with patch.object(tool_service, 'get_user_enabled_tools', new=AsyncMock(side_effect=Exception("Tool fetch failed"))):
                # Mock normal generation
                normal_response = "Fallback response"
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=normal_response)):
                    result = await llm_service.generate_with_mcp(
                        prompt="Test prompt",
                        user_id=1,
                        enable_mcp=True
                    )
                    
                    assert result["content"] == normal_response
                    assert result["mcp_enhanced"] is False
                    assert result["tool_calls_made"] == 0
                    assert result["finish_reason"] == "stop"
    
    @pytest.mark.asyncio
    async def test_degradation_when_all_tools_fail(self):
        """
        Test that system degrades to normal generation when all tool calls fail.
        
        Requirements: 9.5
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create and enable a plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            await plugin_service.toggle_user_plugin(1, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock AI to request tool call
            tool_call_resp = {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "test-plugin.test_tool",
                        "arguments": "{}"
                    }
                }],
                "finish_reason": "tool_calls"
            }
            
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(return_value=tool_call_resp)):
                # Mock all tools to fail
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(return_value=[
                    {
                        "tool_call_id": "call_1",
                        "role": "tool",
                        "name": "test-plugin.test_tool",
                        "content": json.dumps({"error": "Tool failed"}),
                        "success": False
                    }
                ])):
                    # Mock fallback generation
                    fallback_response = "Fallback after tool failure"
                    with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                        result = await llm_service.generate_with_mcp(
                            prompt="Test prompt",
                            user_id=1,
                            enable_mcp=True
                        )
                        
                        assert result["content"] == fallback_response
                        assert result["mcp_enhanced"] is True  # Tools were available
                        assert result["finish_reason"] == "stop"


class TestGenerateWithMCPMultiRound:
    """Test suite for multi-round tool calling."""
    
    @pytest.mark.asyncio
    async def test_multi_round_tool_calling(self):
        """
        Test that system supports multiple rounds of tool calling.
        
        Requirements: 9.3, 9.4
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create and enable a plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            await plugin_service.toggle_user_plugin(1, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock multiple rounds of tool calls
            call_count = 0
            
            async def mock_call_llm(messages, **kwargs):
                nonlocal call_count
                call_count += 1
                
                if call_count == 1:
                    # First round: AI requests tool
                    return {
                        "content": "",
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "test-plugin.test_tool",
                                "arguments": "{}"
                            }
                        }],
                        "finish_reason": "tool_calls"
                    }
                elif call_count == 2:
                    # Second round: AI requests another tool
                    return {
                        "content": "",
                        "tool_calls": [{
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "test-plugin.test_tool",
                                "arguments": "{}"
                            }
                        }],
                        "finish_reason": "tool_calls"
                    }
                else:
                    # Final round: AI returns content
                    return {
                        "content": "Final response",
                        "finish_reason": "stop"
                    }
            
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(side_effect=mock_call_llm)):
                # Mock successful tool execution
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(return_value=[
                    {
                        "tool_call_id": "call_1",
                        "role": "tool",
                        "name": "test-plugin.test_tool",
                        "content": json.dumps({"result": "success"}),
                        "success": True
                    }
                ])):
                    result = await llm_service.generate_with_mcp(
                        prompt="Test prompt",
                        user_id=1,
                        enable_mcp=True,
                        max_tool_rounds=3
                    )
                    
                    assert result["content"] == "Final response"
                    assert result["mcp_enhanced"] is True
                    assert result["tool_calls_made"] == 2  # Two rounds of tool calls
                    assert result["finish_reason"] == "stop"
    
    @pytest.mark.asyncio
    async def test_max_tool_rounds_limit(self):
        """
        Test that system respects max_tool_rounds limit.
        
        Requirements: 9.3, 9.4
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create and enable a plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            await plugin_service.toggle_user_plugin(1, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock AI to always request tools (never finish)
            async def mock_call_llm(messages, **kwargs):
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "test-plugin.test_tool",
                            "arguments": "{}"
                        }
                    }],
                    "finish_reason": "tool_calls"
                }
            
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(side_effect=mock_call_llm)):
                # Mock successful tool execution
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(return_value=[
                    {
                        "tool_call_id": "call_1",
                        "role": "tool",
                        "name": "test-plugin.test_tool",
                        "content": json.dumps({"result": "success"}),
                        "success": True
                    }
                ])):
                    result = await llm_service.generate_with_mcp(
                        prompt="Test prompt",
                        user_id=1,
                        enable_mcp=True,
                        max_tool_rounds=2  # Limit to 2 rounds
                    )
                    
                    # Should stop after 2 rounds even though AI keeps requesting tools
                    assert result["tool_calls_made"] == 2
                    assert result["mcp_enhanced"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
