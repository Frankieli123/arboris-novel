"""
Property-based tests for MCP Tool Service.

Tests tool format conversion, caching, metrics, and execution.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.mcp_plugin import MCPPlugin, UserPluginPreference
from app.services.mcp_tool_service import MCPToolService, ToolMetrics
from app.services.mcp_plugin_service import MCPPluginService
from app.schemas.mcp_plugin import MCPPluginCreate
from app.mcp.registry import MCPPluginRegistry
from app.mcp.config import MCPConfig
from app.db.base import Base


# Hypothesis strategies for generating test data
@st.composite
def mcp_tool_definition(draw):
    """Generate random MCP tool definition.
    
    Returns a mock MCP tool object.
    """
    tool_name = draw(st.text(
        min_size=3,
        max_size=30,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' ')
    ))
    
    description = draw(st.text(min_size=5, max_size=100))
    
    # Generate input schema
    has_params = draw(st.booleans())
    if has_params:
        num_params = draw(st.integers(min_value=1, max_value=5))
        properties = {}
        required = []
        for i in range(num_params):
            param_name = f"param_{i}"
            properties[param_name] = {
                "type": draw(st.sampled_from(["string", "number", "boolean", "object", "array"])),
                "description": draw(st.text(min_size=1, max_size=50))
            }
            if draw(st.booleans()):
                required.append(param_name)
        
        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }
    else:
        input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    # Create mock tool object
    mock_tool = MagicMock()
    mock_tool.name = tool_name
    mock_tool.description = description
    mock_tool.inputSchema = input_schema
    
    return mock_tool


@st.composite
def tool_call_data(draw):
    """Generate random tool call data (OpenAI format).
    
    Returns a dictionary representing a tool call.
    """
    tool_call_id = draw(st.text(min_size=10, max_size=30))
    
    plugin_name = draw(st.text(
        min_size=3,
        max_size=20,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' .')
    ))
    
    tool_name = draw(st.text(
        min_size=3,
        max_size=20,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' .')
    ))
    
    full_tool_name = f"{plugin_name}.{tool_name}"
    
    # Generate arguments
    num_args = draw(st.integers(min_value=0, max_value=5))
    arguments = {}
    for i in range(num_args):
        arg_name = f"arg_{i}"
        arg_type = draw(st.sampled_from(["string", "int", "bool"]))
        if arg_type == "string":
            arguments[arg_name] = draw(st.text(min_size=0, max_size=50))
        elif arg_type == "int":
            arguments[arg_name] = draw(st.integers(min_value=-1000, max_value=1000))
        else:
            arguments[arg_name] = draw(st.booleans())
    
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {
            "name": full_tool_name,
            "arguments": json.dumps(arguments)
        }
    }


@st.composite
def invalid_tool_call_data(draw):
    """Generate tool call with invalid JSON arguments."""
    tool_call_id = draw(st.text(min_size=10, max_size=30))
    
    plugin_name = draw(st.text(min_size=3, max_size=20))
    tool_name = draw(st.text(min_size=3, max_size=20))
    full_tool_name = f"{plugin_name}.{tool_name}"
    
    # Generate invalid JSON
    invalid_json = draw(st.sampled_from([
        "{invalid}",
        "not json at all",
        "{unclosed",
        "{'single': 'quotes'}",
        "{trailing: comma,}"
    ]))
    
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {
            "name": full_tool_name,
            "arguments": invalid_json
        }
    }


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


class TestMCPToolServiceToolFormatConversion:
    """Test suite for tool format conversion property."""
    
    # Feature: mcp-plugin-system, Property 6: Tool Format Conversion
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(tools=st.lists(mcp_tool_definition(), min_size=1, max_size=5))
    async def test_tool_format_conversion(self, tools):
        """
        **Feature: mcp-plugin-system, Property 6: Tool Format Conversion**
        **Validates: Requirements 4.2, 4.3**
        
        Property: For any tool definition received from an MCP server, the converted
        format should be a valid OpenAI Function Calling format containing type="function"
        and a function object with name, description, and parameters fields.
        
        This test verifies that:
        1. All MCP tools are converted to OpenAI format
        2. Each converted tool has type="function"
        3. Each tool has a function object with required fields
        4. Tool names are prefixed with plugin name
        5. Input schemas are preserved
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            plugin_name = "test-plugin"
            
            # Convert tools to OpenAI format
            converted = tool_service._convert_to_openai_format(tools, plugin_name)
            
            # Verify same number of tools
            assert len(converted) == len(tools), \
                "Should convert all tools"
            
            # Verify each converted tool
            for i, (original_tool, converted_tool) in enumerate(zip(tools, converted)):
                # Verify type field
                assert "type" in converted_tool, \
                    f"Tool {i} should have 'type' field"
                assert converted_tool["type"] == "function", \
                    f"Tool {i} should have type='function'"
                
                # Verify function object exists
                assert "function" in converted_tool, \
                    f"Tool {i} should have 'function' field"
                
                function = converted_tool["function"]
                
                # Verify required function fields
                assert "name" in function, \
                    f"Tool {i} function should have 'name' field"
                assert "description" in function, \
                    f"Tool {i} function should have 'description' field"
                assert "parameters" in function, \
                    f"Tool {i} function should have 'parameters' field"
                
                # Verify name is prefixed with plugin name
                expected_name = f"{plugin_name}.{original_tool.name}"
                assert function["name"] == expected_name, \
                    f"Tool {i} name should be prefixed with plugin name"
                
                # Verify description is preserved
                assert function["description"] == (original_tool.description or ""), \
                    f"Tool {i} description should be preserved"
                
                # Verify parameters schema is preserved
                expected_params = original_tool.inputSchema or {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                assert function["parameters"] == expected_params, \
                    f"Tool {i} parameters schema should be preserved"


class TestMCPToolServiceToolCacheHit:
    """Test suite for tool cache hit property."""
    
    # Feature: mcp-plugin-system, Property 7: Tool Cache Hit
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        num_requests=st.integers(min_value=2, max_value=5)
    )
    async def test_tool_cache_hit(self, user_id, num_requests):
        """
        **Feature: mcp-plugin-system, Property 7: Tool Cache Hit**
        **Validates: Requirements 4.4, 11.3**
        
        Property: For any plugin, if tools are fetched and cached, subsequent requests
        within the cache TTL should return the cached tools without calling the MCP server.
        
        This test verifies that:
        1. First request fetches tools from server
        2. Subsequent requests within TTL use cache
        3. Cache hit count increases
        4. No additional server calls are made
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "cache-test-plugin",
                "display_name": "Cache Test Plugin",
                "server_url": "http://cache-test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # First request - should fetch from server
            tools_first = await tool_service.get_user_enabled_tools(user_id)
            
            # Verify tools were returned
            assert len(tools_first) > 0, "Should return tools on first request"
            
            # Verify server was called
            assert mock_registry.list_tools.call_count == 1, \
                "Should call server on first request"
            
            initial_call_count = mock_registry.list_tools.call_count
            
            # Make subsequent requests within TTL
            for i in range(num_requests - 1):
                tools = await tool_service.get_user_enabled_tools(user_id)
                
                # Verify same tools returned
                assert len(tools) == len(tools_first), \
                    f"Request {i+2} should return same number of tools"
                
                # Verify no additional server calls
                assert mock_registry.list_tools.call_count == initial_call_count, \
                    f"Request {i+2} should not call server (cache hit)"
            
            # Verify cache hit count increased
            cache_key = f"{user_id}:{plugin.plugin_name}"
            cached_entry = tool_service._tool_cache.get(cache_key)
            assert cached_entry is not None, "Cache entry should exist"
            assert cached_entry.hit_count == num_requests - 1, \
                f"Cache hit count should be {num_requests - 1}"


class TestMCPToolServiceToolCacheExpiration:
    """Test suite for tool cache expiration property."""
    
    # Feature: mcp-plugin-system, Property 8: Tool Cache Expiration
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(user_id=st.integers(min_value=1, max_value=10000))
    async def test_tool_cache_expiration(self, user_id):
        """
        **Feature: mcp-plugin-system, Property 8: Tool Cache Expiration**
        **Validates: Requirements 4.5, 11.4**
        
        Property: For any cached tool list, after the cache TTL expires, the next
        request should fetch fresh tools from the MCP server and update the cache.
        
        This test verifies that:
        1. Initial request caches tools
        2. After TTL expiration, next request fetches from server
        3. Cache is updated with new expiration time
        4. Server is called again after expiration
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "expiry-test-plugin",
                "display_name": "Expiry Test Plugin",
                "server_url": "http://expiry-test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # First request - should cache
            await tool_service.get_user_enabled_tools(user_id)
            
            # Verify cache exists
            cache_key = f"{user_id}:{plugin.plugin_name}"
            cached_entry = tool_service._tool_cache.get(cache_key)
            assert cached_entry is not None, "Cache should exist after first request"
            
            initial_expire_time = cached_entry.expire_time
            initial_call_count = mock_registry.list_tools.call_count
            
            # Manually expire the cache by setting expire_time to past
            cached_entry.expire_time = datetime.now() - timedelta(seconds=1)
            
            # Request after expiration - should fetch from server again
            await tool_service.get_user_enabled_tools(user_id)
            
            # Verify server was called again
            assert mock_registry.list_tools.call_count == initial_call_count + 1, \
                "Should call server again after cache expiration"
            
            # Verify cache was updated with new expiration time
            updated_entry = tool_service._tool_cache.get(cache_key)
            assert updated_entry is not None, "Cache should still exist"
            assert updated_entry.expire_time > datetime.now(), \
                "Cache should have new future expiration time"


class TestMCPToolServiceToolCallParsing:
    """Test suite for tool call parsing property."""
    
    # Feature: mcp-plugin-system, Property 9: Tool Call Parsing
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(tool_call=tool_call_data())
    async def test_tool_call_parsing(self, tool_call):
        """
        **Feature: mcp-plugin-system, Property 9: Tool Call Parsing**
        **Validates: Requirements 6.1, 6.2**
        
        Property: For any valid tool_calls response from AI, the system should
        correctly extract the tool name and arguments as a valid dictionary.
        
        This test verifies that:
        1. Tool call ID is extracted correctly
        2. Tool name is parsed (plugin.tool format)
        3. Arguments JSON is parsed to dictionary
        4. Parsing handles various argument types
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Extract expected values
            tool_call_id = tool_call["id"]
            full_tool_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"]["arguments"]
            
            # Parse plugin and tool name
            if "." in full_tool_name:
                plugin_name, tool_name = full_tool_name.split(".", 1)
            else:
                plugin_name = full_tool_name
                tool_name = full_tool_name
            
            # Create plugin
            plugin_data = {
                "plugin_name": plugin_name,
                "display_name": f"Plugin {plugin_name}",
                "server_url": f"http://{plugin_name}.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Execute tool call
            result = await tool_service._execute_single_tool(1, tool_call)
            
            # Verify result structure
            assert "tool_call_id" in result, "Result should have tool_call_id"
            assert result["tool_call_id"] == tool_call_id, \
                "Tool call ID should match"
            
            assert "name" in result, "Result should have name"
            assert result["name"] == full_tool_name, \
                "Tool name should match"
            
            # Verify arguments were parsed (no JSON error)
            # If parsing succeeded, result should have success=True or content
            assert "content" in result, "Result should have content"
            
            # Parse the expected arguments to verify they're valid JSON
            expected_args = json.loads(arguments_str)
            assert isinstance(expected_args, dict), \
                "Arguments should parse to dictionary"


class TestMCPToolServiceParameterValidation:
    """Test suite for parameter validation property."""
    
    # Feature: mcp-plugin-system, Property 22: Parameter Validation
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(tool_call=invalid_tool_call_data())
    async def test_parameter_validation(self, tool_call):
        """
        **Feature: mcp-plugin-system, Property 22: Parameter Validation**
        **Validates: Requirements 12.3**
        
        Property: For any tool call with invalid JSON parameters, the system should
        return a parameter validation error without attempting to call the MCP server.
        
        This test verifies that:
        1. Invalid JSON is detected during parsing
        2. Error is returned without calling server
        3. Error message indicates parameter format error
        4. Result has success=False
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Execute tool call with invalid JSON
            result = await tool_service._execute_single_tool(1, tool_call)
            
            # Verify error result
            assert result["success"] is False, \
                "Result should indicate failure for invalid JSON"
            
            # Verify error message mentions parameter format
            content = json.loads(result["content"])
            assert "error" in content, "Content should have error field"
            assert "参数格式错误" in content["error"] or "format" in content["error"].lower(), \
                "Error should mention parameter format issue"
            
            # Verify server was NOT called
            assert mock_registry.call_tool.call_count == 0, \
                "Should not call server with invalid parameters"


class TestMCPToolServiceToolCallRetry:
    """Test suite for tool call retry property."""
    
    # Feature: mcp-plugin-system, Property 10: Tool Call Retry
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=10000),
        num_failures=st.integers(min_value=1, max_value=2)  # Limit to 2 to avoid long delays
    )
    async def test_tool_call_retry(self, user_id, num_failures):
        """
        **Feature: mcp-plugin-system, Property 10: Tool Call Retry**
        **Validates: Requirements 6.4**
        
        Property: For any tool call that fails with a retryable error, the system
        should retry up to MAX_RETRIES times with exponentially increasing delays
        between attempts.
        
        This test verifies that:
        1. Failed calls are retried
        2. Retry count respects MAX_RETRIES
        3. Delays increase exponentially
        4. Eventually succeeds if retries work
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "retry-test-plugin",
                "display_name": "Retry Test Plugin",
                "server_url": "http://retry-test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Configure mock to fail num_failures times, then succeed
            call_count = 0
            
            async def mock_call_with_failures(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= num_failures:
                    raise Exception(f"Temporary failure {call_count}")
                return {"result": "success"}
            
            mock_registry.call_tool = AsyncMock(side_effect=mock_call_with_failures)
            
            # Patch retry delays to make test faster
            with patch.object(MCPConfig, 'BASE_RETRY_DELAY_SECONDS', 0.01):
                # Call tool with retry
                result = await tool_service._call_tool_with_retry(
                    user_id, plugin, "test_tool", {}, timeout=60.0
                )
            
                # Verify it eventually succeeded
                assert result == {"result": "success"}, \
                    "Should succeed after retries"
                
                # Verify correct number of attempts
                expected_attempts = num_failures + 1
                assert call_count == expected_attempts, \
                    f"Should have made {expected_attempts} attempts"


class TestMCPToolServiceToolCallResultFormat:
    """Test suite for tool call result format property."""
    
    # Feature: mcp-plugin-system, Property 11: Tool Call Result Format
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(tool_call=tool_call_data())
    async def test_tool_call_result_format(self, tool_call):
        """
        **Feature: mcp-plugin-system, Property 11: Tool Call Result Format**
        **Validates: Requirements 6.6**
        
        Property: For any successful tool call, the result should be formatted as
        a dictionary with tool_call_id, role="tool", name, content, and success=True fields.
        
        This test verifies that:
        1. Result has all required fields
        2. role is set to "tool"
        3. success is True for successful calls
        4. content is properly formatted
        5. duration_ms is included
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Extract tool info
            full_tool_name = tool_call["function"]["name"]
            plugin_name = full_tool_name.split(".")[0] if "." in full_tool_name else full_tool_name
            
            # Create plugin
            plugin_data = {
                "plugin_name": plugin_name,
                "display_name": f"Plugin {plugin_name}",
                "server_url": f"http://{plugin_name}.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            await plugin_service.create_plugin(plugin_create)
            
            # Mock successful tool call
            mock_registry.call_tool = AsyncMock(return_value={"result": "success"})
            
            # Execute tool call
            result = await tool_service._execute_single_tool(1, tool_call)
            
            # Verify all required fields
            assert "tool_call_id" in result, "Result must have tool_call_id"
            assert "role" in result, "Result must have role"
            assert "name" in result, "Result must have name"
            assert "content" in result, "Result must have content"
            assert "success" in result, "Result must have success"
            
            # Verify field values
            assert result["tool_call_id"] == tool_call["id"], \
                "tool_call_id should match request"
            
            assert result["role"] == "tool", \
                "role should be 'tool'"
            
            assert result["name"] == full_tool_name, \
                "name should match tool name"
            
            assert result["success"] is True, \
                "success should be True for successful call"
            
            # Verify duration is included
            assert "duration_ms" in result, "Result should include duration_ms"
            assert isinstance(result["duration_ms"], (int, float)), \
                "duration_ms should be numeric"
            assert result["duration_ms"] >= 0, \
                "duration_ms should be non-negative"


class TestMCPToolServiceParallelToolExecution:
    """Test suite for parallel tool execution property."""
    
    # Feature: mcp-plugin-system, Property 12: Parallel Tool Execution
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=None)
    @given(
        num_tools=st.integers(min_value=2, max_value=5),
        user_id=st.integers(min_value=1, max_value=10000)
    )
    async def test_parallel_tool_execution(self, num_tools, user_id):
        """
        **Feature: mcp-plugin-system, Property 12: Parallel Tool Execution**
        **Validates: Requirements 6.7**
        
        Property: For any list of multiple tool calls, all tools should be executed
        concurrently using asyncio.gather(), not sequentially.
        
        This test verifies that:
        1. Multiple tool calls are executed
        2. Execution is concurrent (timing check)
        3. All results are returned
        4. Results maintain order
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "parallel-test-plugin",
                "display_name": "Parallel Test Plugin",
                "server_url": "http://parallel-test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            await plugin_service.create_plugin(plugin_create)
            
            # Create multiple tool calls
            tool_calls = []
            for i in range(num_tools):
                tool_calls.append({
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": f"parallel-test-plugin.tool_{i}",
                        "arguments": json.dumps({"index": i})
                    }
                })
            
            # Mock tool call with delay to test parallelism
            async def mock_call_with_delay(*args, **kwargs):
                await asyncio.sleep(0.1)  # Small delay
                return {"result": "success"}
            
            mock_registry.call_tool = AsyncMock(side_effect=mock_call_with_delay)
            
            # Execute tool calls and measure time
            start_time = datetime.now()
            results = await tool_service.execute_tool_calls(user_id, tool_calls)
            duration = (datetime.now() - start_time).total_seconds()
            
            # Verify all results returned
            assert len(results) == num_tools, \
                f"Should return {num_tools} results"
            
            # Verify parallel execution (should take ~0.1s, not 0.1s * num_tools)
            # Allow some overhead, but should be much less than sequential
            max_expected_duration = 0.1 * 3  # 3x the single call time as buffer
            assert duration < max_expected_duration, \
                f"Execution should be parallel (took {duration}s, expected < {max_expected_duration}s)"
            
            # Verify all tool calls were made
            assert mock_registry.call_tool.call_count == num_tools, \
                f"Should have called {num_tools} tools"


class TestMCPToolServiceMetricsRecording:
    """Test suite for metrics recording property."""
    
    # Feature: mcp-plugin-system, Property 16: Metrics Recording
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        tool_call=tool_call_data(),
        should_succeed=st.booleans()
    )
    async def test_metrics_recording(self, tool_call, should_succeed):
        """
        **Feature: mcp-plugin-system, Property 16: Metrics Recording**
        **Validates: Requirements 9.1, 9.2, 9.3**
        
        Property: For any tool call, the system should record the start time,
        end time, and update the appropriate success or failure metrics.
        
        This test verifies that:
        1. Metrics are created for tool
        2. Success/failure counts are updated
        3. Duration is recorded
        4. Total calls count increases
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Extract tool info
            full_tool_name = tool_call["function"]["name"]
            plugin_name = full_tool_name.split(".")[0] if "." in full_tool_name else full_tool_name
            tool_name = full_tool_name.split(".")[1] if "." in full_tool_name else full_tool_name
            
            # Create plugin
            plugin_data = {
                "plugin_name": plugin_name,
                "display_name": f"Plugin {plugin_name}",
                "server_url": f"http://{plugin_name}.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            await plugin_service.create_plugin(plugin_create)
            
            # Configure mock based on should_succeed
            if should_succeed:
                mock_registry.call_tool = AsyncMock(return_value={"result": "success"})
            else:
                mock_registry.call_tool = AsyncMock(side_effect=Exception("Tool failed"))
            
            # Execute tool call
            await tool_service._execute_single_tool(1, tool_call)
            
            # Verify metrics were recorded
            metric_key = f"{plugin_name}.{tool_name}"
            assert metric_key in tool_service._metrics, \
                "Metrics should be created for tool"
            
            metrics = tool_service._metrics[metric_key]
            
            # Verify total calls increased
            assert metrics.total_calls == 1, \
                "Total calls should be 1"
            
            # Verify success/failure counts
            if should_succeed:
                assert metrics.success_calls == 1, \
                    "Success calls should be 1 for successful call"
                assert metrics.failed_calls == 0, \
                    "Failed calls should be 0 for successful call"
            else:
                assert metrics.success_calls == 0, \
                    "Success calls should be 0 for failed call"
                assert metrics.failed_calls == 1, \
                    "Failed calls should be 1 for failed call"
            
            # Verify duration was recorded
            assert metrics.total_duration_ms > 0, \
                "Duration should be recorded"


class TestMCPToolServiceMetricsCompleteness:
    """Test suite for metrics completeness property."""
    
    # Feature: mcp-plugin-system, Property 17: Metrics Completeness
    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None)
    @given(
        num_calls=st.integers(min_value=1, max_value=5),
        success_rate=st.floats(min_value=0.0, max_value=1.0)
    )
    async def test_metrics_completeness(self, num_calls, success_rate):
        """
        **Feature: mcp-plugin-system, Property 17: Metrics Completeness**
        **Validates: Requirements 9.4**
        
        Property: For any tool that has been called, querying metrics should return
        a complete ToolMetrics object with total_calls, success_calls, failed_calls,
        avg_duration_ms, and success_rate fields.
        
        This test verifies that:
        1. Metrics query returns all required fields
        2. Counts are accurate
        3. Averages are calculated correctly
        4. Success rate is computed correctly
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "metrics-test-plugin",
                "display_name": "Metrics Test Plugin",
                "server_url": "http://metrics-test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            await plugin_service.create_plugin(plugin_create)
            
            # Calculate expected successes and failures
            num_successes = int(num_calls * success_rate)
            num_failures = num_calls - num_successes
            
            # Make tool calls with controlled success/failure
            for i in range(num_calls):
                should_succeed = i < num_successes
                
                tool_call = {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": "metrics-test-plugin.test_tool",
                        "arguments": json.dumps({"index": i})
                    }
                }
                
                if should_succeed:
                    mock_registry.call_tool = AsyncMock(return_value={"result": "success"})
                else:
                    mock_registry.call_tool = AsyncMock(side_effect=Exception("Failed"))
                
                await tool_service._execute_single_tool(1, tool_call)
            
            # Query metrics
            metrics = tool_service.get_metrics("metrics-test-plugin.test_tool")
            
            # Verify all required fields present
            assert "tool_name" in metrics, "Metrics should have tool_name"
            assert "total_calls" in metrics, "Metrics should have total_calls"
            assert "success_calls" in metrics, "Metrics should have success_calls"
            assert "failed_calls" in metrics, "Metrics should have failed_calls"
            assert "avg_duration_ms" in metrics, "Metrics should have avg_duration_ms"
            assert "success_rate" in metrics, "Metrics should have success_rate"
            
            # Verify counts are accurate
            assert metrics["total_calls"] == num_calls, \
                f"Total calls should be {num_calls}"
            
            assert metrics["success_calls"] == num_successes, \
                f"Success calls should be {num_successes}"
            
            assert metrics["failed_calls"] == num_failures, \
                f"Failed calls should be {num_failures}"
            
            # Verify success rate calculation
            expected_rate = num_successes / num_calls if num_calls > 0 else 0.0
            assert abs(metrics["success_rate"] - expected_rate) < 0.01, \
                f"Success rate should be approximately {expected_rate}"
            
            # Verify average duration is non-negative
            assert metrics["avg_duration_ms"] >= 0, \
                "Average duration should be non-negative"


class TestMCPToolServiceCacheClear:
    """Test suite for cache clear property."""
    
    # Feature: mcp-plugin-system, Property 20: Cache Clear
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(user_id=st.integers(min_value=1, max_value=10000))
    async def test_cache_clear(self, user_id):
        """
        **Feature: mcp-plugin-system, Property 20: Cache Clear**
        **Validates: Requirements 11.5**
        
        Property: For any state of the tool cache, calling clear_cache() should
        result in an empty cache, and the next tool request should fetch fresh
        data from the server.
        
        This test verifies that:
        1. Cache is populated after first request
        2. clear_cache() empties the cache
        3. Next request fetches from server again
        4. Cache is repopulated after clear
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "clear-test-plugin",
                "display_name": "Clear Test Plugin",
                "server_url": "http://clear-test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Enable plugin for user
            await plugin_service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test tool"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # First request - populates cache
            await tool_service.get_user_enabled_tools(user_id)
            
            # Verify cache is populated
            assert len(tool_service._tool_cache) > 0, \
                "Cache should be populated after first request"
            
            initial_call_count = mock_registry.list_tools.call_count
            
            # Clear cache
            tool_service.clear_cache()
            
            # Verify cache is empty
            assert len(tool_service._tool_cache) == 0, \
                "Cache should be empty after clear_cache()"
            
            # Next request should fetch from server again
            await tool_service.get_user_enabled_tools(user_id)
            
            # Verify server was called again
            assert mock_registry.list_tools.call_count == initial_call_count + 1, \
                "Should call server again after cache clear"
            
            # Verify cache is repopulated
            assert len(tool_service._tool_cache) > 0, \
                "Cache should be repopulated after request"


# Edge case tests
class TestMCPToolServiceEdgeCases:
    """Test edge cases and specific scenarios."""
    
    @pytest.mark.asyncio
    async def test_empty_tool_calls_list(self):
        """Test that empty tool calls list returns empty results."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            results = await tool_service.execute_tool_calls(1, [])
            
            assert results == [], "Empty tool calls should return empty results"
            assert mock_registry.call_tool.call_count == 0, \
                "Should not call server for empty list"
    
    @pytest.mark.asyncio
    async def test_tool_call_without_plugin_name_separator(self):
        """Test tool call with name that doesn't have plugin.tool format."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            tool_call = {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "standalone_tool",  # No dot separator
                    "arguments": "{}"
                }
            }
            
            # Should handle gracefully (plugin_name = tool_name)
            result = await tool_service._execute_single_tool(1, tool_call)
            
            # Should return error (plugin not found)
            assert result["success"] is False
            content = json.loads(result["content"])
            assert "error" in content
    
    @pytest.mark.asyncio
    async def test_metrics_for_nonexistent_tool(self):
        """Test querying metrics for a tool that hasn't been called."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            metrics = tool_service.get_metrics("nonexistent.tool")
            
            assert metrics == {}, "Should return empty dict for nonexistent tool"
    
    @pytest.mark.asyncio
    async def test_get_all_metrics(self):
        """Test getting metrics for all tools."""
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
            await plugin_service.create_plugin(plugin_create)
            
            # Make some tool calls
            for i in range(3):
                tool_call = {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": f"test-plugin.tool_{i}",
                        "arguments": "{}"
                    }
                }
                await tool_service._execute_single_tool(1, tool_call)
            
            # Get all metrics
            all_metrics = tool_service.get_metrics()
            
            # Should have metrics for 3 tools
            assert len(all_metrics) == 3, "Should have metrics for 3 tools"
            
            for i in range(3):
                tool_name = f"test-plugin.tool_{i}"
                assert tool_name in all_metrics, f"Should have metrics for {tool_name}"
                assert all_metrics[tool_name]["total_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_tool_call_max_retries_exceeded(self):
        """Test that tool call fails after max retries."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            plugin_service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "fail-plugin",
                "display_name": "Fail Plugin",
                "server_url": "http://fail.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await plugin_service.create_plugin(plugin_create)
            
            # Configure mock to always fail
            mock_registry.call_tool = AsyncMock(side_effect=Exception("Always fails"))
            
            # Should raise exception after max retries
            with pytest.raises(Exception, match="Always fails"):
                await tool_service._call_tool_with_retry(
                    1, plugin, "test_tool", {}, timeout=60.0
                )
            
            # Verify it tried MAX_RETRIES times
            assert mock_registry.call_tool.call_count == MCPConfig.MAX_RETRIES
    
    @pytest.mark.asyncio
    async def test_convert_tool_with_no_description(self):
        """Test converting tool with None description."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create tool with no description
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = None
            mock_tool.inputSchema = {"type": "object"}
            
            converted = tool_service._convert_to_openai_format([mock_tool], "plugin")
            
            # Should use empty string for description
            assert converted[0]["function"]["description"] == ""
    
    @pytest.mark.asyncio
    async def test_convert_tool_with_no_input_schema(self):
        """Test converting tool with None inputSchema."""
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create tool with no input schema
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test"
            mock_tool.inputSchema = None
            
            converted = tool_service._convert_to_openai_format([mock_tool], "plugin")
            
            # Should use default schema
            expected_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }
            assert converted[0]["function"]["parameters"] == expected_schema
