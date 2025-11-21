"""
Property-based tests for generate_with_mcp() method.

Tests correctness properties for the new MCP integration.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Set required environment variables before importing app modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-property-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st, assume
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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


class TestProperty5DegradationConsistency:
    """
    **Feature: admin-mcp-defaults, Property 5: 工具调用降级一致性**
    **Validates: Requirements 9.5**
    
    Property: For any MCP tool call failure, the system should degrade to normal
    generation mode, and the result should be consistent with non-MCP generation.
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        prompt=st.text(min_size=10, max_size=200),
        temperature=st.floats(min_value=0.0, max_value=2.0),
    )
    async def test_degradation_consistency_no_tools(self, user_id, prompt, temperature):
        """
        Property: When no tools are available, generate_with_mcp should produce
        the same result as normal generation.
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock get_user_enabled_tools to return empty list
            with patch.object(tool_service, 'get_user_enabled_tools', new=AsyncMock(return_value=[])):
                # Mock normal generation
                expected_response = f"Response for: {prompt[:50]}"
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=expected_response)):
                    result = await llm_service.generate_with_mcp(
                        prompt=prompt,
                        user_id=user_id,
                        enable_mcp=True,
                        temperature=temperature
                    )
                    
                    # Property: Result should match normal generation
                    assert result["content"] == expected_response, \
                        "Content should match normal generation when no tools available"
                    
                    assert result["mcp_enhanced"] is False, \
                        "Should not be marked as MCP enhanced when no tools"
                    
                    assert result["tool_calls_made"] == 0, \
                        "Should have zero tool calls when no tools available"
                    
                    assert result["tools_used"] == [], \
                        "Should have empty tools_used list"
                    
                    assert result["finish_reason"] == "stop", \
                        "Should have stop finish reason"
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        prompt=st.text(min_size=10, max_size=200),
        temperature=st.floats(min_value=0.0, max_value=2.0),
    )
    async def test_degradation_consistency_tool_fetch_fails(self, user_id, prompt, temperature):
        """
        Property: When tool fetching fails, generate_with_mcp should degrade
        gracefully and produce a valid response.
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock get_user_enabled_tools to raise exception
            with patch.object(tool_service, 'get_user_enabled_tools', 
                            new=AsyncMock(side_effect=Exception("Tool fetch failed"))):
                # Mock fallback generation
                fallback_response = f"Fallback for: {prompt[:50]}"
                with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                    result = await llm_service.generate_with_mcp(
                        prompt=prompt,
                        user_id=user_id,
                        enable_mcp=True,
                        temperature=temperature
                    )
                    
                    # Property: Should degrade gracefully
                    assert result["content"] == fallback_response, \
                        "Should return fallback content when tool fetch fails"
                    
                    assert result["mcp_enhanced"] is False, \
                        "Should not be marked as MCP enhanced when tool fetch fails"
                    
                    assert result["tool_calls_made"] == 0, \
                        "Should have zero tool calls when tool fetch fails"
                    
                    assert isinstance(result["content"], str), \
                        "Content should be a string"
                    
                    assert len(result["content"]) > 0, \
                        "Content should not be empty"
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        prompt=st.text(min_size=10, max_size=200),
        num_tools=st.integers(min_value=1, max_value=5),
    )
    async def test_degradation_consistency_all_tools_fail(self, user_id, prompt, num_tools):
        """
        Property: When all tool calls fail, generate_with_mcp should degrade
        to normal generation and produce a valid response.
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tools
            mock_tools = []
            for i in range(num_tools):
                mock_tool = MagicMock()
                mock_tool.name = f"test_tool_{i}"
                mock_tool.description = f"Test tool {i}"
                mock_tool.inputSchema = {"type": "object", "properties": {}}
                mock_tools.append(mock_tool)
            
            mock_registry.list_tools = AsyncMock(return_value=mock_tools)
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock AI to request tool calls
            tool_calls = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": f"test-plugin.test_tool_{i}",
                        "arguments": "{}"
                    }
                }
                for i in range(num_tools)
            ]
            
            tool_call_resp = {
                "content": "",
                "tool_calls": tool_calls,
                "finish_reason": "tool_calls"
            }
            
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(return_value=tool_call_resp)):
                # Mock all tools to fail
                failed_results = [
                    {
                        "tool_call_id": f"call_{i}",
                        "role": "tool",
                        "name": f"test-plugin.test_tool_{i}",
                        "content": json.dumps({"error": "Tool failed"}),
                        "success": False
                    }
                    for i in range(num_tools)
                ]
                
                with patch.object(tool_service, 'execute_tool_calls', new=AsyncMock(return_value=failed_results)):
                    # Mock fallback generation
                    fallback_response = f"Fallback after all tools failed: {prompt[:30]}"
                    with patch.object(llm_service, '_stream_and_collect', new=AsyncMock(return_value=fallback_response)):
                        result = await llm_service.generate_with_mcp(
                            prompt=prompt,
                            user_id=user_id,
                            enable_mcp=True
                        )
                        
                        # Property: Should degrade to normal generation
                        assert result["content"] == fallback_response, \
                            "Should return fallback content when all tools fail"
                        
                        assert result["mcp_enhanced"] is True, \
                            "Should be marked as MCP enhanced (tools were available)"
                        
                        assert result["finish_reason"] == "stop", \
                            "Should have stop finish reason after degradation"
                        
                        assert isinstance(result["content"], str), \
                            "Content should be a string"
                        
                        assert len(result["content"]) > 0, \
                            "Content should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



class TestProperty6ToolListFormat:
    """
    **Feature: admin-mcp-defaults, Property 6: 工具列表格式正确性**
    **Validates: Requirements 9.2**
    
    Property: For any user-enabled MCP tools, each tool definition should conform
    to OpenAI Function Calling format specification.
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        num_tools=st.integers(min_value=1, max_value=10),
    )
    async def test_tool_list_format_correctness(self, user_id, num_tools):
        """
        Property: All tools returned by get_user_enabled_tools should have
        the correct OpenAI Function Calling format.
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tools with various configurations
            mock_tools = []
            for i in range(num_tools):
                mock_tool = MagicMock()
                mock_tool.name = f"tool_{i}"
                mock_tool.description = f"Description for tool {i}"
                mock_tool.inputSchema = {
                    "type": "object",
                    "properties": {
                        f"param_{j}": {"type": "string", "description": f"Parameter {j}"}
                        for j in range(i % 3 + 1)  # 1-3 parameters
                    },
                    "required": [f"param_0"]
                }
                mock_tools.append(mock_tool)
            
            mock_registry.list_tools = AsyncMock(return_value=mock_tools)
            
            # Get tools
            tools = await tool_service.get_user_enabled_tools(user_id)
            
            # Property: All tools should have correct format
            assert len(tools) == num_tools, \
                f"Should return {num_tools} tools"
            
            for i, tool in enumerate(tools):
                # Check top-level structure
                assert "type" in tool, \
                    f"Tool {i} should have 'type' field"
                assert tool["type"] == "function", \
                    f"Tool {i} type should be 'function'"
                
                assert "function" in tool, \
                    f"Tool {i} should have 'function' field"
                
                # Check function structure
                function = tool["function"]
                assert "name" in function, \
                    f"Tool {i} function should have 'name' field"
                assert "description" in function, \
                    f"Tool {i} function should have 'description' field"
                assert "parameters" in function, \
                    f"Tool {i} function should have 'parameters' field"
                
                # Check name format (should be plugin_name.tool_name)
                assert "." in function["name"], \
                    f"Tool {i} name should include plugin prefix"
                assert function["name"].startswith("test-plugin."), \
                    f"Tool {i} name should start with plugin name"
                
                # Check parameters structure
                params = function["parameters"]
                assert isinstance(params, dict), \
                    f"Tool {i} parameters should be a dict"
                assert "type" in params, \
                    f"Tool {i} parameters should have 'type' field"
                assert params["type"] == "object", \
                    f"Tool {i} parameters type should be 'object'"
                assert "properties" in params, \
                    f"Tool {i} parameters should have 'properties' field"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
    )
    async def test_tool_list_format_with_no_parameters(self, user_id):
        """
        Property: Tools with no parameters should still have valid format.
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool with no parameters
            mock_tool = MagicMock()
            mock_tool.name = "no_param_tool"
            mock_tool.description = "Tool with no parameters"
            mock_tool.inputSchema = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Get tools
            tools = await tool_service.get_user_enabled_tools(user_id)
            
            # Property: Tool should have valid format even with no parameters
            assert len(tools) == 1
            tool = tools[0]
            
            assert tool["type"] == "function"
            assert "function" in tool
            
            function = tool["function"]
            assert function["name"] == "test-plugin.no_param_tool"
            assert "parameters" in function
            
            params = function["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert isinstance(params["properties"], dict)
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        description_text=st.text(min_size=0, max_size=500),
    )
    async def test_tool_list_format_with_various_descriptions(self, user_id, description_text):
        """
        Property: Tools with various description formats should maintain valid structure.
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool with various description
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = description_text
            mock_tool.inputSchema = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Get tools
            tools = await tool_service.get_user_enabled_tools(user_id)
            
            # Property: Tool should have valid format regardless of description
            assert len(tools) == 1
            tool = tools[0]
            
            assert tool["type"] == "function"
            function = tool["function"]
            assert "description" in function
            assert function["description"] == description_text
            
            # All other required fields should still be present
            assert "name" in function
            assert "parameters" in function


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



class TestProperty7MultiRoundTermination:
    """
    **Feature: admin-mcp-defaults, Property 7: 多轮工具调用终止性**
    **Validates: Requirements 9.3, 9.4**
    
    Property: For any MCP-enhanced generation request, the number of tool call
    rounds should not exceed the max_tool_rounds parameter.
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        prompt=st.text(min_size=10, max_size=200),
        max_rounds=st.integers(min_value=1, max_value=5),
    )
    async def test_multi_round_termination_limit(self, user_id, prompt, max_rounds):
        """
        Property: The system should never exceed max_tool_rounds, even if
        the AI keeps requesting more tool calls.
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Track number of LLM calls
            call_count = [0]
            
            # Mock AI to always request tools (never finish naturally)
            async def mock_call_llm(messages, **kwargs):
                call_count[0] += 1
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": f"call_{call_count[0]}",
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
                        prompt=prompt,
                        user_id=user_id,
                        enable_mcp=True,
                        max_tool_rounds=max_rounds
                    )
                    
                    # Property: Should not exceed max_tool_rounds
                    assert result["tool_calls_made"] <= max_rounds, \
                        f"Tool calls made ({result['tool_calls_made']}) should not exceed max_rounds ({max_rounds})"
                    
                    # Should have made exactly max_rounds calls (since AI never stops)
                    assert result["tool_calls_made"] == max_rounds, \
                        f"Should have made exactly {max_rounds} tool calls"
                    
                    # Should have called LLM exactly max_rounds times
                    assert call_count[0] == max_rounds, \
                        f"Should have called LLM exactly {max_rounds} times"
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        prompt=st.text(min_size=10, max_size=200),
        max_rounds=st.integers(min_value=2, max_value=5),
        finish_round=st.integers(min_value=1, max_value=4),
    )
    async def test_multi_round_early_termination(self, user_id, prompt, max_rounds, finish_round):
        """
        Property: The system should terminate early if AI returns content
        without tool calls, even if max_tool_rounds is not reached.
        """
        # Ensure finish_round is less than max_rounds
        assume(finish_round < max_rounds)
        
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Track number of LLM calls
            call_count = [0]
            
            # Mock AI to request tools for finish_round times, then return content
            async def mock_call_llm(messages, **kwargs):
                call_count[0] += 1
                
                if call_count[0] <= finish_round:
                    # Request tool call
                    return {
                        "content": "",
                        "tool_calls": [{
                            "id": f"call_{call_count[0]}",
                            "type": "function",
                            "function": {
                                "name": "test-plugin.test_tool",
                                "arguments": "{}"
                            }
                        }],
                        "finish_reason": "tool_calls"
                    }
                else:
                    # Return final content
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
                        prompt=prompt,
                        user_id=user_id,
                        enable_mcp=True,
                        max_tool_rounds=max_rounds
                    )
                    
                    # Property: Should terminate early when AI returns content
                    assert result["tool_calls_made"] == finish_round, \
                        f"Should have made {finish_round} tool calls (terminated early)"
                    
                    assert result["tool_calls_made"] < max_rounds, \
                        f"Should have terminated before reaching max_rounds ({max_rounds})"
                    
                    assert result["content"] == "Final response", \
                        "Should have final content from AI"
                    
                    assert result["finish_reason"] == "stop", \
                        "Should have stop finish reason"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        prompt=st.text(min_size=10, max_size=200),
    )
    async def test_multi_round_zero_rounds_when_no_tools_requested(self, user_id, prompt):
        """
        Property: If AI doesn't request any tools, tool_calls_made should be 0.
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
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            llm_service = LLMService(test_db, mcp_tool_service=tool_service)
            
            # Mock AI to immediately return content without requesting tools
            async def mock_call_llm(messages, **kwargs):
                return {
                    "content": "Direct response without tools",
                    "finish_reason": "stop"
                }
            
            with patch.object(llm_service, '_call_llm_with_tools', new=AsyncMock(side_effect=mock_call_llm)):
                result = await llm_service.generate_with_mcp(
                    prompt=prompt,
                    user_id=user_id,
                    enable_mcp=True,
                    max_tool_rounds=3
                )
                
                # Property: Should have zero tool calls
                assert result["tool_calls_made"] == 0, \
                    "Should have zero tool calls when AI doesn't request any"
                
                assert result["tools_used"] == [], \
                    "Should have empty tools_used list"
                
                assert result["content"] == "Direct response without tools", \
                    "Should have content from AI"
                
                assert result["finish_reason"] == "stop", \
                    "Should have stop finish reason"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
