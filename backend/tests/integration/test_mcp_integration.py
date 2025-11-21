"""
End-to-end integration tests for MCP Plugin System.

These tests verify complete workflows including:
- Admin configuring default plugins
- Users enabling/disabling plugins
- MCP-enhanced generation flow
- Error handling and graceful degradation

Requirements tested: 1.1, 5.4, 9.1, 10.2
"""

import os
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock, patch

# Set required environment variables before importing app modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-integration-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.db.base import Base
from app.models.user import User
from app.models.mcp_plugin import MCPPlugin
from app.services.mcp_plugin_service import MCPPluginService
from app.services.mcp_tool_service import MCPToolService
from app.services.llm_service import LLMService
from app.mcp.registry import MCPPluginRegistry
from app.schemas.mcp_plugin import MCPPluginCreate, MCPPluginUpdate


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def test_registry():
    """Create a test MCP registry."""
    registry = MCPPluginRegistry(
        max_clients=10,
        client_ttl=300
    )
    yield registry
    await registry.shutdown()


@pytest.fixture
async def test_user(test_db: AsyncSession):
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def test_admin(test_db: AsyncSession):
    """Create a test admin user."""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True
    )
    test_db.add(admin)
    await test_db.commit()
    await test_db.refresh(admin)
    return admin


@pytest.fixture
async def test_user2(test_db: AsyncSession):
    """Create a second test user."""
    user = User(
        username="testuser2",
        email="test2@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminDefaultPluginWorkflow:
    """Test complete admin default plugin configuration workflow.
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
    """
    
    async def test_admin_creates_default_plugin(
        self, test_db: AsyncSession, test_admin: User, test_user: User
    ):
        """
        Test workflow:
        1. Admin creates default plugin
        2. Verify plugin is marked as default (user_id = NULL)
        3. Verify plugin appears in user's available plugins
        4. Verify plugin is enabled by default for user
        
        Validates: Requirements 1.1, 1.2, 1.3
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Admin creates default plugin
        plugin_data = MCPPluginCreate(
            plugin_name="default_search",
            display_name="Default Search Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="search",
            description="A default search plugin for all users"
        )
        
        plugin = await plugin_service.create_default_plugin(plugin_data)
        
        # Step 2: Verify plugin is marked as default
        assert plugin.id is not None
        assert plugin.user_id is None  # Key: default plugins have NULL user_id
        assert plugin.plugin_name == "default_search"
        assert plugin.enabled is True
        
        # Step 3: Verify plugin appears in user's available plugins
        user_plugins = await plugin_service.list_plugins_with_user_status(test_user.id)
        default_plugin = next((p for p in user_plugins if p.plugin_name == "default_search"), None)
        
        assert default_plugin is not None
        assert default_plugin.is_default is True
        
        # Step 4: Verify plugin is enabled by default for user
        assert default_plugin.user_enabled is True  # Uses plugin's default enabled status
    
    async def test_admin_updates_default_plugin(
        self, test_db: AsyncSession, test_admin: User, test_user: User
    ):
        """
        Test workflow:
        1. Admin creates default plugin
        2. Admin updates plugin configuration
        3. Verify changes are reflected for all users
        
        Validates: Requirements 1.4
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create default plugin
        plugin_data = MCPPluginCreate(
            plugin_name="updatable_plugin",
            display_name="Original Name",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        
        # Step 2: Update plugin
        update_data = MCPPluginUpdate(
            display_name="Updated Name",
            server_url="http://localhost:9001",
            category="updated_category"
        )
        updated_plugin = await plugin_service.update_plugin(plugin.id, update_data)
        
        # Step 3: Verify changes
        assert updated_plugin.display_name == "Updated Name"
        assert updated_plugin.server_url == "http://localhost:9001"
        assert updated_plugin.category == "updated_category"
        assert updated_plugin.user_id is None  # Still a default plugin
        
        # Verify user sees updated plugin
        user_plugins = await plugin_service.list_plugins_with_user_status(test_user.id)
        user_plugin = next((p for p in user_plugins if p.id == plugin.id), None)
        assert user_plugin is not None
        assert user_plugin.display_name == "Updated Name"
    
    async def test_admin_deletes_default_plugin(
        self, test_db: AsyncSession, test_admin: User, test_user: User
    ):
        """
        Test workflow:
        1. Admin creates default plugin
        2. User enables plugin
        3. Admin deletes plugin
        4. Verify plugin is removed for all users
        
        Validates: Requirements 1.5
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create default plugin
        plugin_data = MCPPluginCreate(
            plugin_name="deletable_plugin",
            display_name="Deletable Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        plugin_id = plugin.id
        
        # Step 2: User enables plugin (creates preference)
        await plugin_service.toggle_user_plugin(test_user.id, plugin_id, True)
        
        # Step 3: Admin deletes plugin
        await plugin_service.delete_plugin(plugin_id)
        
        # Step 4: Verify plugin is gone
        deleted_plugin = await plugin_service.get_plugin(plugin_id)
        assert deleted_plugin is None
        
        # Verify plugin no longer appears in user's list
        user_plugins = await plugin_service.list_plugins_with_user_status(test_user.id)
        assert not any(p.id == plugin_id for p in user_plugins)


@pytest.mark.integration
@pytest.mark.asyncio
class TestUserPluginPreferenceWorkflow:
    """Test user plugin preference management workflow.
    
    Validates: Requirements 5.1, 5.2, 5.3, 5.4
    """
    
    async def test_user_sees_default_and_custom_plugins(
        self, test_db: AsyncSession, test_user: User, test_user2: User
    ):
        """
        Test workflow:
        1. Admin creates default plugin
        2. User1 creates custom plugin
        3. User2 creates custom plugin
        4. Verify User1 sees default + their custom plugin
        5. Verify User2 sees default + their custom plugin
        6. Verify users don't see each other's custom plugins
        
        Validates: Requirements 5.1, 5.2, 5.3
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create default plugin
        default_plugin_data = MCPPluginCreate(
            plugin_name="default_plugin",
            display_name="Default Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        default_plugin = await plugin_service.create_default_plugin(default_plugin_data)
        
        # Step 2: User1 creates custom plugin
        user1_plugin_data = MCPPluginCreate(
            plugin_name="user1_custom",
            display_name="User1 Custom Plugin",
            server_url="http://localhost:9001",
            enabled=True,
            category="custom"
        )
        user1_plugin = await plugin_service.create_plugin(user1_plugin_data, user_id=test_user.id)
        
        # Step 3: User2 creates custom plugin
        user2_plugin_data = MCPPluginCreate(
            plugin_name="user2_custom",
            display_name="User2 Custom Plugin",
            server_url="http://localhost:9002",
            enabled=True,
            category="custom"
        )
        user2_plugin = await plugin_service.create_plugin(user2_plugin_data, user_id=test_user2.id)
        
        # Step 4: Verify User1 sees default + their custom plugin
        user1_plugins = await plugin_service.list_plugins_with_user_status(test_user.id)
        user1_plugin_names = {p.plugin_name for p in user1_plugins}
        
        assert "default_plugin" in user1_plugin_names
        assert "user1_custom" in user1_plugin_names
        assert "user2_custom" not in user1_plugin_names  # Should not see User2's plugin
        
        # Step 5: Verify User2 sees default + their custom plugin
        user2_plugins = await plugin_service.list_plugins_with_user_status(test_user2.id)
        user2_plugin_names = {p.plugin_name for p in user2_plugins}
        
        assert "default_plugin" in user2_plugin_names
        assert "user2_custom" in user2_plugin_names
        assert "user1_custom" not in user2_plugin_names  # Should not see User1's plugin
        
        # Step 6: Verify is_default flag is correct
        user1_default = next(p for p in user1_plugins if p.plugin_name == "default_plugin")
        user1_custom = next(p for p in user1_plugins if p.plugin_name == "user1_custom")
        
        assert user1_default.is_default is True
        assert user1_custom.is_default is False
    
    async def test_user_toggles_default_plugin(
        self, test_db: AsyncSession, test_user: User, test_user2: User
    ):
        """
        Test workflow:
        1. Admin creates default plugin (enabled by default)
        2. User1 disables the default plugin
        3. User2 keeps the default plugin enabled
        4. Verify User1's preference is respected
        5. Verify User2's preference is respected
        6. Verify default plugin itself is unchanged
        
        Validates: Requirements 5.4, 7.4
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create default plugin
        plugin_data = MCPPluginCreate(
            plugin_name="toggleable_default",
            display_name="Toggleable Default Plugin",
            server_url="http://localhost:9000",
            enabled=True,  # Enabled by default
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        
        # Step 2: User1 disables the plugin
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, False)
        
        # Step 3: User2 doesn't change anything (uses default)
        # No action needed
        
        # Step 4: Verify User1's preference
        user1_plugins = await plugin_service.list_plugins_with_user_status(test_user.id)
        user1_plugin = next(p for p in user1_plugins if p.id == plugin.id)
        assert user1_plugin.user_enabled is False  # User disabled it
        
        # Step 5: Verify User2's preference
        user2_plugins = await plugin_service.list_plugins_with_user_status(test_user2.id)
        user2_plugin = next(p for p in user2_plugins if p.id == plugin.id)
        assert user2_plugin.user_enabled is True  # Uses default enabled status
        
        # Step 6: Verify default plugin itself is unchanged
        original_plugin = await plugin_service.get_plugin(plugin.id)
        assert original_plugin.enabled is True  # Still enabled by default
        assert original_plugin.user_id is None  # Still a default plugin


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCPEnhancedGenerationWorkflow:
    """Test complete MCP-enhanced generation workflow.
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2
    """
    
    async def test_generation_with_mcp_enabled(
        self, test_db: AsyncSession, test_user: User, test_registry: MCPPluginRegistry
    ):
        """
        Test workflow:
        1. Create and enable plugin for user
        2. Mock MCP tool service to return tools
        3. Mock LLM to request tool calls
        4. Mock tool execution
        5. Verify generation uses MCP tools
        6. Verify result indicates MCP enhancement
        
        Validates: Requirements 9.1, 9.2, 10.1, 10.2
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create and enable plugin
        plugin_data = MCPPluginCreate(
            plugin_name="test_search",
            display_name="Test Search",
            server_url="http://localhost:9000",
            enabled=True,
            category="search"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, True)
        
        # Step 2-5: Mock MCP tool service and LLM
        mock_tool_service = AsyncMock(spec=MCPToolService)
        mock_tool_service.get_user_enabled_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        mock_tool_service.execute_tool_calls.return_value = [
            {
                "tool_call_id": "call_123",
                "name": "search",
                "content": "Search results: Test information",
                "success": True
            }
        ]
        
        llm_service = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        # Mock the LLM calls
        with patch.object(llm_service, '_call_llm_with_tools') as mock_llm_call:
            # First call: AI requests tool
            mock_llm_call.side_effect = [
                {
                    "content": "",
                    "finish_reason": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": '{"query": "test"}'
                            }
                        }
                    ]
                },
                # Second call: AI returns final content
                {
                    "content": "Generated content based on search results",
                    "finish_reason": "stop"
                }
            ]
            
            # Step 6: Generate with MCP
            result = await llm_service.generate_with_mcp(
                prompt="Generate a story about AI",
                user_id=test_user.id,
                enable_mcp=True
            )
            
            # Verify MCP was used
            assert result["mcp_enhanced"] is True
            assert result["tool_calls_made"] == 1
            assert "search" in result["tools_used"]
            assert result["content"] == "Generated content based on search results"
            
            # Verify tool service was called
            mock_tool_service.get_user_enabled_tools.assert_called_once_with(test_user.id)
            mock_tool_service.execute_tool_calls.assert_called_once()
    
    async def test_generation_with_mcp_disabled(
        self, test_db: AsyncSession, test_user: User
    ):
        """
        Test workflow:
        1. Create plugin but don't enable it
        2. Generate with enable_mcp=False
        3. Verify generation works without MCP
        4. Verify result indicates no MCP enhancement
        
        Validates: Requirements 10.1
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create plugin but don't enable it
        plugin_data = MCPPluginCreate(
            plugin_name="unused_plugin",
            display_name="Unused Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        await plugin_service.create_default_plugin(plugin_data)
        
        # Step 2-3: Generate without MCP
        mock_tool_service = AsyncMock(spec=MCPToolService)
        llm_service = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        with patch.object(llm_service, '_stream_and_collect') as mock_stream:
            mock_stream.return_value = "Generated content without MCP"
            
            result = await llm_service.generate_with_mcp(
                prompt="Generate a story",
                user_id=test_user.id,
                enable_mcp=False  # Explicitly disabled
            )
            
            # Step 4: Verify no MCP enhancement
            assert result["mcp_enhanced"] is False
            assert result["tool_calls_made"] == 0
            assert len(result["tools_used"]) == 0
            assert result["content"] == "Generated content without MCP"
            
            # Verify tool service was not called
            mock_tool_service.get_user_enabled_tools.assert_not_called()
    
    async def test_generation_degrades_when_tools_fail(
        self, test_db: AsyncSession, test_user: User, test_registry: MCPPluginRegistry
    ):
        """
        Test workflow:
        1. Create and enable plugin
        2. Mock tool service to fail
        3. Generate with MCP enabled
        4. Verify generation completes without MCP
        5. Verify graceful degradation
        
        Validates: Requirements 9.5, 10.4
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create and enable plugin
        plugin_data = MCPPluginCreate(
            plugin_name="failing_plugin",
            display_name="Failing Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, True)
        
        # Step 2: Mock tool service to fail
        mock_tool_service = AsyncMock(spec=MCPToolService)
        mock_tool_service.get_user_enabled_tools.side_effect = Exception("Tool service failed")
        
        llm_service = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        # Step 3-5: Generate and verify degradation
        with patch.object(llm_service, '_stream_and_collect') as mock_stream:
            mock_stream.return_value = "Generated content without tools"
            
            result = await llm_service.generate_with_mcp(
                prompt="Generate a story",
                user_id=test_user.id,
                enable_mcp=True
            )
            
            # Verify graceful degradation
            assert result["mcp_enhanced"] is False  # Degraded to non-MCP
            assert result["tool_calls_made"] == 0
            assert len(result["tools_used"]) == 0
            assert result["content"] == "Generated content without tools"
            
            # Verify fallback was used
            mock_stream.assert_called_once()
    
    async def test_generation_degrades_when_all_tool_calls_fail(
        self, test_db: AsyncSession, test_user: User, test_registry: MCPPluginRegistry
    ):
        """
        Test workflow:
        1. Create and enable plugin
        2. Mock AI to request tools
        3. Mock all tool calls to fail
        4. Verify generation degrades to non-MCP mode
        
        Validates: Requirements 9.5, 10.4
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create and enable plugin
        plugin_data = MCPPluginCreate(
            plugin_name="unreliable_plugin",
            display_name="Unreliable Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, True)
        
        # Step 2-3: Mock tool service
        mock_tool_service = AsyncMock(spec=MCPToolService)
        mock_tool_service.get_user_enabled_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "unreliable_tool",
                    "description": "An unreliable tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        # All tool calls fail
        mock_tool_service.execute_tool_calls.return_value = [
            {
                "tool_call_id": "call_123",
                "name": "unreliable_tool",
                "content": "Error: Tool failed",
                "success": False
            }
        ]
        
        llm_service = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        with patch.object(llm_service, '_call_llm_with_tools') as mock_llm_call, \
             patch.object(llm_service, '_stream_and_collect') as mock_stream:
            
            # AI requests tool
            mock_llm_call.return_value = {
                "content": "",
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "unreliable_tool",
                            "arguments": '{}'
                        }
                    }
                ]
            }
            
            # Fallback generation
            mock_stream.return_value = "Fallback content"
            
            # Step 4: Generate and verify degradation
            result = await llm_service.generate_with_mcp(
                prompt="Generate content",
                user_id=test_user.id,
                enable_mcp=True
            )
            
            # Verify degradation occurred
            assert result["mcp_enhanced"] is True  # Tools were available (just failed)
            assert result["content"] == "Fallback content"
            
            # Verify fallback was called
            mock_stream.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiRoundToolCalling:
    """Test multi-round tool calling workflow.
    
    Validates: Requirements 9.3, 9.4
    """
    
    async def test_multi_round_tool_calling(
        self, test_db: AsyncSession, test_user: User, test_registry: MCPPluginRegistry
    ):
        """
        Test workflow:
        1. Create and enable plugin
        2. Mock AI to request tools multiple times
        3. Verify multiple rounds of tool calls
        4. Verify max_tool_rounds is respected
        
        Validates: Requirements 9.3, 9.4
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create and enable plugin
        plugin_data = MCPPluginCreate(
            plugin_name="multi_tool",
            display_name="Multi Tool",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, True)
        
        # Step 2: Mock tool service
        mock_tool_service = AsyncMock(spec=MCPToolService)
        mock_tool_service.get_user_enabled_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "tool1",
                    "description": "First tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool2",
                    "description": "Second tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        mock_tool_service.execute_tool_calls.return_value = [
            {
                "tool_call_id": "call_1",
                "name": "tool1",
                "content": "Result from tool1",
                "success": True
            }
        ]
        
        llm_service = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        # Step 3: Mock multiple rounds of tool calls
        with patch.object(llm_service, '_call_llm_with_tools') as mock_llm_call:
            mock_llm_call.side_effect = [
                # Round 1: Request tool1
                {
                    "content": "",
                    "finish_reason": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "tool1", "arguments": "{}"}
                        }
                    ]
                },
                # Round 2: Request tool2
                {
                    "content": "",
                    "finish_reason": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "tool2", "arguments": "{}"}
                        }
                    ]
                },
                # Round 3: Final content
                {
                    "content": "Final content after multiple tool calls",
                    "finish_reason": "stop"
                }
            ]
            
            result = await llm_service.generate_with_mcp(
                prompt="Generate with multiple tools",
                user_id=test_user.id,
                enable_mcp=True,
                max_tool_rounds=3
            )
            
            # Verify multiple rounds occurred
            assert result["mcp_enhanced"] is True
            assert result["tool_calls_made"] == 2  # Two tool calls made
            assert "tool1" in result["tools_used"]
            assert "tool2" in result["tools_used"]
            assert result["content"] == "Final content after multiple tool calls"
            
            # Verify LLM was called 3 times (2 tool rounds + 1 final)
            assert mock_llm_call.call_count == 3
    
    async def test_max_tool_rounds_limit(
        self, test_db: AsyncSession, test_user: User, test_registry: MCPPluginRegistry
    ):
        """
        Test workflow:
        1. Create and enable plugin
        2. Mock AI to always request tools
        3. Verify generation stops at max_tool_rounds
        
        Validates: Requirements 9.4
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Create and enable plugin
        plugin_data = MCPPluginCreate(
            plugin_name="infinite_tool",
            display_name="Infinite Tool",
            server_url="http://localhost:9000",
            enabled=True,
            category="general"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, True)
        
        # Step 2: Mock tool service
        mock_tool_service = AsyncMock(spec=MCPToolService)
        mock_tool_service.get_user_enabled_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "endless_tool",
                    "description": "A tool that never ends",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        mock_tool_service.execute_tool_calls.return_value = [
            {
                "tool_call_id": "call_x",
                "name": "endless_tool",
                "content": "Tool result",
                "success": True
            }
        ]
        
        llm_service = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        # Step 3: Mock AI to always request tools (never finish)
        with patch.object(llm_service, '_call_llm_with_tools') as mock_llm_call:
            # Always return tool calls, never final content
            mock_llm_call.return_value = {
                "content": "",
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "endless_tool", "arguments": "{}"}
                    }
                ]
            }
            
            result = await llm_service.generate_with_mcp(
                prompt="Generate endlessly",
                user_id=test_user.id,
                enable_mcp=True,
                max_tool_rounds=2  # Limit to 2 rounds
            )
            
            # Verify it stopped at max_tool_rounds
            assert mock_llm_call.call_count == 2  # Should stop at 2 rounds
            assert result["tool_calls_made"] == 2
            
            # Content should be empty since AI never returned final content
            assert result["content"] == ""


@pytest.mark.integration
@pytest.mark.asyncio
class TestCompleteEndToEndWorkflow:
    """Test complete end-to-end workflow combining all features.
    
    Validates: Requirements 1.1, 5.4, 9.1, 10.2
    """
    
    async def test_complete_workflow(
        self, test_db: AsyncSession, test_admin: User, test_user: User, test_user2: User, test_registry: MCPPluginRegistry
    ):
        """
        Complete end-to-end test:
        1. Admin creates default plugin
        2. User1 enables the plugin
        3. User2 disables the plugin
        4. User1 generates content with MCP
        5. User2 generates content without MCP
        6. Admin updates plugin
        7. Verify changes propagate correctly
        8. Admin deletes plugin
        9. Verify cleanup
        
        Validates: Requirements 1.1, 5.4, 9.1, 10.2
        """
        plugin_service = MCPPluginService(test_db)
        
        # Step 1: Admin creates default plugin
        plugin_data = MCPPluginCreate(
            plugin_name="complete_test_plugin",
            display_name="Complete Test Plugin",
            server_url="http://localhost:9000",
            enabled=True,
            category="search",
            description="A plugin for complete workflow testing"
        )
        plugin = await plugin_service.create_default_plugin(plugin_data)
        assert plugin.user_id is None
        
        # Step 2: User1 enables the plugin (explicitly)
        await plugin_service.toggle_user_plugin(test_user.id, plugin.id, True)
        
        # Step 3: User2 disables the plugin
        await plugin_service.toggle_user_plugin(test_user2.id, plugin.id, False)
        
        # Verify preferences
        user1_plugins = await plugin_service.list_plugins_with_user_status(test_user.id)
        user1_plugin = next(p for p in user1_plugins if p.id == plugin.id)
        assert user1_plugin.user_enabled is True
        
        user2_plugins = await plugin_service.list_plugins_with_user_status(test_user2.id)
        user2_plugin = next(p for p in user2_plugins if p.id == plugin.id)
        assert user2_plugin.user_enabled is False
        
        # Step 4: User1 generates content with MCP
        mock_tool_service = AsyncMock(spec=MCPToolService)
        mock_tool_service.get_user_enabled_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        mock_tool_service.execute_tool_calls.return_value = [
            {
                "tool_call_id": "call_1",
                "name": "search",
                "content": "Search results",
                "success": True
            }
        ]
        
        llm_service1 = LLMService(test_db, mcp_tool_service=mock_tool_service)
        
        with patch.object(llm_service1, '_call_llm_with_tools') as mock_llm_call:
            mock_llm_call.side_effect = [
                {
                    "content": "",
                    "finish_reason": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": "{}"}
                        }
                    ]
                },
                {
                    "content": "User1 content with MCP",
                    "finish_reason": "stop"
                }
            ]
            
            result1 = await llm_service1.generate_with_mcp(
                prompt="Generate for User1",
                user_id=test_user.id,
                enable_mcp=True
            )
            
            assert result1["mcp_enhanced"] is True
            assert result1["tool_calls_made"] == 1
            assert result1["content"] == "User1 content with MCP"
        
        # Step 5: User2 generates content without MCP (plugin disabled)
        mock_tool_service2 = AsyncMock(spec=MCPToolService)
        mock_tool_service2.get_user_enabled_tools.return_value = []  # No enabled tools
        
        llm_service2 = LLMService(test_db, mcp_tool_service=mock_tool_service2)
        
        with patch.object(llm_service2, '_stream_and_collect') as mock_stream:
            mock_stream.return_value = "User2 content without MCP"
            
            result2 = await llm_service2.generate_with_mcp(
                prompt="Generate for User2",
                user_id=test_user2.id,
                enable_mcp=True
            )
            
            assert result2["mcp_enhanced"] is False
            assert result2["tool_calls_made"] == 0
            assert result2["content"] == "User2 content without MCP"
        
        # Step 6: Admin updates plugin
        update_data = MCPPluginUpdate(
            display_name="Updated Complete Test Plugin",
            description="Updated description"
        )
        updated_plugin = await plugin_service.update_plugin(plugin.id, update_data)
        assert updated_plugin.display_name == "Updated Complete Test Plugin"
        
        # Step 7: Verify changes propagate
        user1_plugins_updated = await plugin_service.list_plugins_with_user_status(test_user.id)
        user1_plugin_updated = next(p for p in user1_plugins_updated if p.id == plugin.id)
        assert user1_plugin_updated.display_name == "Updated Complete Test Plugin"
        assert user1_plugin_updated.user_enabled is True  # Preference preserved
        
        user2_plugins_updated = await plugin_service.list_plugins_with_user_status(test_user2.id)
        user2_plugin_updated = next(p for p in user2_plugins_updated if p.id == plugin.id)
        assert user2_plugin_updated.display_name == "Updated Complete Test Plugin"
        assert user2_plugin_updated.user_enabled is False  # Preference preserved
        
        # Step 8: Admin deletes plugin
        await plugin_service.delete_plugin(plugin.id)
        
        # Step 9: Verify cleanup
        deleted_plugin = await plugin_service.get_plugin(plugin.id)
        assert deleted_plugin is None
        
        # Verify plugin removed from both users' lists
        user1_final = await plugin_service.list_plugins_with_user_status(test_user.id)
        assert not any(p.id == plugin.id for p in user1_final)
        
        user2_final = await plugin_service.list_plugins_with_user_status(test_user2.id)
        assert not any(p.id == plugin.id for p in user2_final)


# Summary of integration tests:
#
# 1. TestAdminDefaultPluginWorkflow - Tests admin creating, updating, and deleting default plugins
# 2. TestUserPluginPreferenceWorkflow - Tests users managing their plugin preferences
# 3. TestMCPEnhancedGenerationWorkflow - Tests MCP-enhanced generation with tools
# 4. TestMultiRoundToolCalling - Tests multi-round tool calling and limits
# 5. TestCompleteEndToEndWorkflow - Tests complete workflow from admin setup to user generation
#
# These tests validate:
# - Requirements 1.1, 1.2, 1.3, 1.4, 1.5 (Admin default plugin management)
# - Requirements 5.1, 5.2, 5.3, 5.4 (User plugin preferences)
# - Requirements 9.1, 9.2, 9.3, 9.4, 9.5 (MCP tool calling)
# - Requirements 10.1, 10.2, 10.4 (MCP-enhanced generation)
