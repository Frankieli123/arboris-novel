"""
Property-based tests for LLM Service MCP functionality.

Tests graceful degradation when MCP tools fail.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Set required environment variables before importing app modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-property-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.mcp_plugin import MCPPlugin, UserPluginPreference
from app.models.user import User
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


@st.composite
def message_list(draw):
    """Generate random message list for LLM."""
    num_messages = draw(st.integers(min_value=1, max_value=5))
    messages = []
    
    for i in range(num_messages):
        role = draw(st.sampled_from(["system", "user", "assistant"]))
        content = draw(st.text(min_size=10, max_size=200))
        messages.append({
            "role": role,
            "content": content
        })
    
    return messages


@st.composite
def tool_call_response(draw):
    """Generate a tool call response from AI."""
    num_tools = draw(st.integers(min_value=1, max_value=3))
    tool_calls = []
    
    for i in range(num_tools):
        tool_calls.append({
            "id": f"call_{i}",
            "type": "function",
            "function": {
                "name": f"test-plugin.tool_{i}",
                "arguments": json.dumps({"param": draw(st.text(min_size=1, max_size=50))})
            }
        })
    
    return {
        "content": "",
        "tool_calls": tool_calls,
        "finish_reason": "tool_calls"
    }


class TestLLMServiceGracefulDegradation:
    """Test suite for graceful degradation property."""
    
    # Feature: mcp-plugin-system, Property 19: Graceful Degradation
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        messages=message_list()
    )
    async def test_graceful_degradation_all_tools_fail(self, user_id, messages):
        """
        **Feature: mcp-plugin-system, Property 19: Graceful Degradation**
        **Validates: Requirements 5.5**
        
        Property: For any user request with MCP tools enabled, if all tool calls fail,
        the system should gracefully degrade to normal generation mode and still
        produce a response without raising an exception.
        
        This test verifies that:
        1. When all tools fail, system doesn't crash
        2. System falls back to normal generation
        3. A response is still generated
        4. No exception is raised to the user
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool that will be available
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Create LLM service with mocked MCP tool service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock the LLM calls
            # First call: AI decides to use tools
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
            
            # Mock _call_llm_with_tools to return tool calls
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(return_value=tool_call_resp)):
                # Mock tool execution to fail
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(return_value=[
                    {
                        "tool_call_id": "call_1",
                        "role": "tool",
                        "name": "test-plugin.test_tool",
                        "content": json.dumps({"error": "Tool failed"}),
                        "success": False
                    }
                ])):
                    # Mock fallback generation to succeed
                    fallback_response = "This is a fallback response generated without tools."
                    with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                        # Call generate_text_with_mcp
                        result = await llm_service.generate_text_with_mcp(
                            messages=messages,
                            user_id=user_id,
                            temperature=0.7,
                            timeout=300.0
                        )
                        
                        # Verify graceful degradation occurred
                        assert result is not None, \
                            "Should return a response even when all tools fail"
                        
                        assert isinstance(result, str), \
                            "Response should be a string"
                        
                        assert len(result) > 0, \
                            "Response should not be empty"
                        
                        assert result == fallback_response, \
                            "Should return fallback response when all tools fail"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        messages=message_list()
    )
    async def test_graceful_degradation_no_mcp_service(self, user_id, messages):
        """
        **Feature: mcp-plugin-system, Property 19: Graceful Degradation**
        **Validates: Requirements 5.5**
        
        Property: For any user request, if MCP tool service is not initialized,
        the system should gracefully degrade to normal generation mode.
        
        This test verifies that:
        1. When MCP service is None, system doesn't crash
        2. System falls back to normal generation immediately
        3. A response is still generated
        """
        async with DatabaseContext() as test_db:
            # Create LLM service WITHOUT MCP tool service
            llm_service = LLMService(test_db, mcp_tool_service=None)
            
            # Mock normal generation to succeed
            normal_response = "This is a normal response without MCP tools."
            with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=normal_response)):
                # Call generate_text_with_mcp
                result = await llm_service.generate_text_with_mcp(
                    messages=messages,
                    user_id=user_id,
                    temperature=0.7,
                    timeout=300.0
                )
                
                # Verify graceful degradation occurred
                assert result is not None, \
                    "Should return a response when MCP service is not available"
                
                assert isinstance(result, str), \
                    "Response should be a string"
                
                assert result == normal_response, \
                    "Should use normal generation when MCP service is None"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        messages=message_list()
    )
    async def test_graceful_degradation_tool_fetch_fails(self, user_id, messages):
        """
        **Feature: mcp-plugin-system, Property 19: Graceful Degradation**
        **Validates: Requirements 5.5**
        
        Property: For any user request, if fetching MCP tools fails,
        the system should gracefully degrade to normal generation mode.
        
        This test verifies that:
        1. When tool fetching fails, system doesn't crash
        2. System falls back to normal generation
        3. A response is still generated
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create LLM service with MCP tool service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock tool fetching to fail
            with patch.object(tool_service, 'get_user_enabled_tools', new=AsyncMock(side_effect=Exception("Failed to fetch tools"))):
                # Mock fallback generation to succeed
                fallback_response = "This is a fallback response after tool fetch failure."
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                    # Call generate_text_with_mcp
                    result = await llm_service.generate_text_with_mcp(
                        messages=messages,
                        user_id=user_id,
                        temperature=0.7,
                        timeout=300.0
                    )
                    
                    # Verify graceful degradation occurred
                    assert result is not None, \
                        "Should return a response when tool fetching fails"
                    
                    assert isinstance(result, str), \
                        "Response should be a string"
                    
                    assert result == fallback_response, \
                        "Should use fallback generation when tool fetching fails"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        messages=message_list()
    )
    async def test_graceful_degradation_no_tools_enabled(self, user_id, messages):
        """
        **Feature: mcp-plugin-system, Property 19: Graceful Degradation**
        **Validates: Requirements 5.5**
        
        Property: For any user request, if no MCP tools are enabled,
        the system should use normal generation mode.
        
        This test verifies that:
        1. When no tools are enabled, system uses normal generation
        2. No tool calls are attempted
        3. A response is still generated
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create LLM service with MCP tool service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock tool fetching to return empty list
            with patch.object(tool_service, 'get_user_enabled_tools', new=AsyncMock(return_value=[])):
                # Mock normal generation to succeed
                normal_response = "This is a normal response with no tools enabled."
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=normal_response)):
                    # Call generate_text_with_mcp
                    result = await llm_service.generate_text_with_mcp(
                        messages=messages,
                        user_id=user_id,
                        temperature=0.7,
                        timeout=300.0
                    )
                    
                    # Verify normal generation was used
                    assert result is not None, \
                        "Should return a response when no tools are enabled"
                    
                    assert isinstance(result, str), \
                        "Response should be a string"
                    
                    assert result == normal_response, \
                        "Should use normal generation when no tools are enabled"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        messages=message_list()
    )
    async def test_graceful_degradation_first_llm_call_fails(self, user_id, messages):
        """
        **Feature: mcp-plugin-system, Property 19: Graceful Degradation**
        **Validates: Requirements 5.5**
        
        Property: For any user request, if the first LLM call (with tools) fails,
        the system should gracefully degrade to normal generation mode.
        
        This test verifies that:
        1. When first LLM call fails, system doesn't crash
        2. System falls back to normal generation
        3. A response is still generated
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool that will be available
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Create LLM service with mocked MCP tool service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock the first LLM call to fail
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(side_effect=Exception("LLM call failed"))):
                # Mock fallback generation to succeed
                fallback_response = "This is a fallback response after first LLM call failure."
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                    # Call generate_text_with_mcp
                    result = await llm_service.generate_text_with_mcp(
                        messages=messages,
                        user_id=user_id,
                        temperature=0.7,
                        timeout=300.0
                    )
                    
                    # Verify graceful degradation occurred
                    assert result is not None, \
                        "Should return a response when first LLM call fails"
                    
                    assert isinstance(result, str), \
                        "Response should be a string"
                    
                    assert result == fallback_response, \
                        "Should use fallback generation when first LLM call fails"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        messages=message_list()
    )
    async def test_graceful_degradation_tool_execution_fails(self, user_id, messages):
        """
        **Feature: mcp-plugin-system, Property 19: Graceful Degradation**
        **Validates: Requirements 5.5**
        
        Property: For any user request, if tool execution throws an exception,
        the system should gracefully degrade to normal generation mode.
        
        This test verifies that:
        1. When tool execution fails with exception, system doesn't crash
        2. System falls back to normal generation
        3. A response is still generated
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool that will be available
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Create LLM service with mocked MCP tool service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock the LLM calls
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
            
            # Mock _call_llm_with_tools to return tool calls
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(return_value=tool_call_resp)):
                # Mock tool execution to throw exception
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(side_effect=Exception("Tool execution crashed"))):
                    # Mock fallback generation to succeed
                    fallback_response = "This is a fallback response after tool execution failure."
                    with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                        # Call generate_text_with_mcp
                        result = await llm_service.generate_text_with_mcp(
                            messages=messages,
                            user_id=user_id,
                            temperature=0.7,
                            timeout=300.0
                        )
                        
                        # Verify graceful degradation occurred
                        assert result is not None, \
                            "Should return a response when tool execution fails"
                        
                        assert isinstance(result, str), \
                            "Response should be a string"
                        
                        assert result == fallback_response, \
                            "Should use fallback generation when tool execution fails"


# Edge case tests
class TestLLMServiceMCPEdgeCases:
    """Test edge cases for LLM service MCP integration."""
    
    @pytest.mark.asyncio
    async def test_successful_tool_call_no_degradation(self):
        """Test that successful tool calls don't trigger degradation."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(1, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Create LLM service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock successful tool call flow
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
                    # Mock second LLM call to succeed
                    final_response = "This is the final response with tool results."
                    with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=final_response)):
                        # Call generate_text_with_mcp
                        result = await llm_service.generate_text_with_mcp(
                            messages=[{"role": "user", "content": "test"}],
                            user_id=1,
                            temperature=0.7,
                            timeout=300.0
                        )
                        
                        # Verify successful flow (no degradation)
                        assert result == final_response, \
                            "Should return final response with tool results"
    
    @pytest.mark.asyncio
    async def test_partial_tool_success_no_degradation(self):
        """Test that partial tool success doesn't trigger degradation."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(1, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Create LLM service
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock tool calls with mixed success
            tool_call_resp = {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "test-plugin.test_tool",
                            "arguments": "{}"
                        }
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "test-plugin.test_tool",
                            "arguments": "{}"
                        }
                    }
                ],
                "finish_reason": "tool_calls"
            }
            
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(return_value=tool_call_resp)):
                # Mock partial tool success (one succeeds, one fails)
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(return_value=[
                    {
                        "tool_call_id": "call_1",
                        "role": "tool",
                        "name": "test-plugin.test_tool",
                        "content": json.dumps({"result": "success"}),
                        "success": True
                    },
                    {
                        "tool_call_id": "call_2",
                        "role": "tool",
                        "name": "test-plugin.test_tool",
                        "content": json.dumps({"error": "failed"}),
                        "success": False
                    }
                ])):
                    # Mock second LLM call to succeed
                    final_response = "This is the final response with partial tool results."
                    with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=final_response)):
                        # Call generate_text_with_mcp
                        result = await llm_service.generate_text_with_mcp(
                            messages=[{"role": "user", "content": "test"}],
                            user_id=1,
                            temperature=0.7,
                            timeout=300.0
                        )
                        
                        # Verify no degradation (at least one tool succeeded)
                        assert result == final_response, \
                            "Should continue with tool results when at least one succeeds"
