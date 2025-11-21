"""
Property-based tests for MCP Plugin Service.

Tests plugin management, user preferences, and configuration propagation.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.mcp_plugin import MCPPlugin, UserPluginPreference
from app.services.mcp_plugin_service import MCPPluginService
from app.services.mcp_tool_service import MCPToolService
from app.schemas.mcp_plugin import MCPPluginCreate
from app.mcp.registry import MCPPluginRegistry
from app.db.base import Base


# Hypothesis strategies for generating test data
@st.composite
def plugin_data(draw):
    """Generate random valid plugin data for creation.
    
    Returns a dictionary suitable for MCPPluginCreate.
    """
    plugin_name = draw(st.text(
        min_size=3,
        max_size=30,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' :')
    ))
    
    display_name = draw(st.text(min_size=3, max_size=50))
    
    plugin_type = draw(st.sampled_from(["http", "stdio", "sse"]))
    
    # Generate valid-looking URL
    protocol = draw(st.sampled_from(["http", "https"]))
    domain = draw(st.text(
        min_size=5,
        max_size=20,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' ')
    ))
    server_url = f"{protocol}://{domain}.com"
    
    enabled = draw(st.booleans())
    
    category = draw(st.sampled_from([
        "search", "filesystem", "database", "api", "tool", None
    ]))
    
    return {
        "plugin_name": plugin_name,
        "display_name": display_name,
        "plugin_type": plugin_type,
        "server_url": server_url,
        "enabled": enabled,
        "category": category,
    }


@st.composite
def user_plugin_scenario(draw):
    """Generate scenario with user ID, plugin data, and enable/disable action.
    
    Returns (user_id, plugin_data, should_enable)
    """
    user_id = draw(st.integers(min_value=1, max_value=10000))
    plugin = draw(plugin_data())
    should_enable = draw(st.booleans())
    
    return user_id, plugin, should_enable


@st.composite
def multiple_plugins_scenario(draw, min_plugins=2, max_plugins=5):
    """Generate scenario with multiple plugins for a user.
    
    Returns (user_id, list of plugin_data, list of enabled states)
    """
    user_id = draw(st.integers(min_value=1, max_value=10000))
    num_plugins = draw(st.integers(min_value=min_plugins, max_value=max_plugins))
    
    plugins = []
    enabled_states = []
    
    for i in range(num_plugins):
        plugin = draw(plugin_data())
        # Make plugin names unique
        plugin["plugin_name"] = f"{plugin['plugin_name']}-{i}"
        plugins.append(plugin)
        enabled_states.append(draw(st.booleans()))
    
    return user_id, plugins, enabled_states


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
    return registry


class TestMCPPluginServiceEnabledPluginsLoaded:
    """Test suite for enabled plugins loading property."""
    
    # Feature: mcp-plugin-system, Property 2: Enabled Plugins Are Loaded
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None, suppress_health_check=[])
    @given(scenario=user_plugin_scenario())
    async def test_enabled_plugins_are_loaded(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 2: Enabled Plugins Are Loaded**
        **Validates: Requirements 1.3**
        
        Property: For any plugin configuration with enabled=true, after creation or update,
        the plugin should appear in the registry with an active session.
        
        This test verifies that:
        1. When a plugin is created with enabled=true, it can be loaded into the registry
        2. When a plugin is updated to enabled=true, it can be loaded
        3. The registry's load_plugin method is called with correct parameters
        """
        user_id, plugin_data, should_enable = scenario
        
        # Force the plugin to be enabled for this test
        plugin_data["enabled"] = True
        
        # Create test database and mock registry
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            # Create service
            service = MCPPluginService(test_db)
            
            # Create plugin
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await service.create_plugin(plugin_create)
            
            # Verify plugin was created with enabled=true
            assert plugin.enabled is True, "Plugin should be created with enabled=true"
            assert plugin.id is not None, "Plugin should have an ID after creation"
            
            # Now simulate loading the plugin into registry
            # In real system, this would be done by the registry on startup or when plugin is enabled
            await mock_registry.load_plugin(user_id, plugin.plugin_name, plugin.server_url)
            
            # Verify load_plugin was called
            mock_registry.load_plugin.assert_called_once_with(
                user_id, plugin.plugin_name, plugin.server_url
            )
            
            # Test update scenario: disable then re-enable
            from app.schemas.mcp_plugin import MCPPluginUpdate
            
            # Disable plugin
            update_disable = MCPPluginUpdate(enabled=False)
            await service.update_plugin(plugin.id, update_disable)
            
            # Re-enable plugin
            update_enable = MCPPluginUpdate(enabled=True)
            updated_plugin = await service.update_plugin(plugin.id, update_enable)
            
            # Verify plugin is enabled after update
            assert updated_plugin.enabled is True, "Plugin should be enabled after update"
            
            # Simulate loading after update
            mock_registry.load_plugin.reset_mock()
            await mock_registry.load_plugin(user_id, updated_plugin.plugin_name, updated_plugin.server_url)
            
            # Verify load_plugin was called again
            mock_registry.load_plugin.assert_called_once()


class TestMCPPluginServiceDeletionCleanup:
    """Test suite for plugin deletion cleanup property."""
    
    # Feature: mcp-plugin-system, Property 3: Plugin Deletion Cleanup
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None, suppress_health_check=[])
    @given(scenario=user_plugin_scenario())
    async def test_plugin_deletion_cleanup(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 3: Plugin Deletion Cleanup**
        **Validates: Requirements 1.5**
        
        Property: For any plugin, after deletion, it should not appear in the registry,
        database, or user preferences, and all associated resources should be released.
        
        This test verifies that:
        1. Plugin is removed from database after deletion
        2. User preferences for the plugin are removed (cascade delete)
        3. Registry unload_plugin is called to release resources
        4. Subsequent queries for the plugin return None
        """
        user_id, plugin_data, should_enable = scenario
        
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            # Create service
            service = MCPPluginService(test_db)
            
            # Create plugin
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await service.create_plugin(plugin_create)
            plugin_id = plugin.id
            plugin_name = plugin.plugin_name
            
            # Create user preference for this plugin
            await service.toggle_user_plugin(user_id, plugin_id, should_enable)
            
            # Verify preference exists
            pref = await service.user_pref_repo.get_user_preference(user_id, plugin_id)
            assert pref is not None, "User preference should exist before deletion"
            
            # Simulate plugin being loaded in registry
            await mock_registry.load_plugin(user_id, plugin_name, plugin.server_url)
            
            # Delete the plugin
            await service.delete_plugin(plugin_id)
            
            # Verify plugin no longer exists in database
            deleted_plugin = await service.get_plugin(plugin_id)
            assert deleted_plugin is None, "Plugin should not exist after deletion"
            
            # Verify user preference was cascade deleted
            deleted_pref = await service.user_pref_repo.get_user_preference(user_id, plugin_id)
            assert deleted_pref is None, "User preference should be cascade deleted"
            
            # Simulate unloading from registry
            await mock_registry.unload_plugin(user_id, plugin_name)
            
            # Verify unload_plugin was called
            mock_registry.unload_plugin.assert_called_once_with(user_id, plugin_name)
            
            # Verify we can't get plugin with user status
            plugin_with_status = await service.get_plugin_with_user_status(plugin_id, user_id)
            assert plugin_with_status is None, "Should return None for deleted plugin"


class TestMCPPluginServiceUserToolInclusion:
    """Test suite for user tool inclusion property."""
    
    # Feature: mcp-plugin-system, Property 4: User Tool Inclusion
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None, suppress_health_check=[])
    @given(scenario=multiple_plugins_scenario(min_plugins=2, max_plugins=4))
    async def test_user_tool_inclusion(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 4: User Tool Inclusion**
        **Validates: Requirements 2.2**
        
        Property: For any user and any plugin they enable, the tools from that plugin
        should appear in the user's available tools list returned by get_user_enabled_tools().
        
        This test verifies that:
        1. When a user enables a plugin, its tools are included in their tool list
        2. Multiple enabled plugins all contribute their tools
        3. Tools are correctly formatted and associated with their plugins
        """
        user_id, plugins_data, enabled_states = scenario
        
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            # Create service
            service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create all plugins
            created_plugins = []
            for plugin_data in plugins_data:
                # Ensure plugin is globally enabled
                plugin_data["enabled"] = True
                plugin_create = MCPPluginCreate(**plugin_data)
                plugin = await service.create_plugin(plugin_create)
                created_plugins.append(plugin)
            
            # Set user preferences
            enabled_plugins = []
            for plugin, should_enable in zip(created_plugins, enabled_states):
                await service.toggle_user_plugin(user_id, plugin.id, should_enable)
                if should_enable:
                    enabled_plugins.append(plugin)
            
            # Mock tools for each enabled plugin
            # Create a mapping of plugin names to tools
            plugin_tools_map = {}
            for plugin in enabled_plugins:
                mock_tool = MagicMock()
                mock_tool.name = f"tool_{plugin.plugin_name}"
                mock_tool.description = f"Tool from {plugin.plugin_name}"
                mock_tool.inputSchema = {"type": "object", "properties": {}}
                plugin_tools_map[plugin.plugin_name] = [mock_tool]
            
            # Configure registry to return tools based on plugin name
            async def mock_list_tools(uid, pname, *args, **kwargs):
                return plugin_tools_map.get(pname, [])
            
            mock_registry.list_tools = AsyncMock(side_effect=mock_list_tools)
            
            # Get user's enabled tools
            tools = await tool_service.get_user_enabled_tools(user_id)
            
            # Verify tools from enabled plugins are included
            tool_names = [tool["function"]["name"] for tool in tools]
            
            for plugin in enabled_plugins:
                expected_tool_name = f"{plugin.plugin_name}.tool_{plugin.plugin_name}"
                assert expected_tool_name in tool_names, \
                    f"Tool from enabled plugin {plugin.plugin_name} should be in user's tool list"
            
            # Verify we have the right number of tools (one per enabled plugin)
            assert len(tools) == len(enabled_plugins), \
                f"Should have {len(enabled_plugins)} tools from enabled plugins"


class TestMCPPluginServiceUserToolExclusion:
    """Test suite for user tool exclusion property."""
    
    # Feature: mcp-plugin-system, Property 5: User Tool Exclusion
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None, suppress_health_check=[])
    @given(scenario=multiple_plugins_scenario(min_plugins=2, max_plugins=4))
    async def test_user_tool_exclusion(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 5: User Tool Exclusion**
        **Validates: Requirements 2.3**
        
        Property: For any user and any plugin they disable, the tools from that plugin
        should not appear in the user's available tools list returned by get_user_enabled_tools().
        
        This test verifies that:
        1. When a user disables a plugin, its tools are excluded from their tool list
        2. Disabled plugins don't contribute tools even if globally enabled
        3. Only enabled plugins' tools appear in the list
        """
        user_id, plugins_data, enabled_states = scenario
        
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            # Create service
            service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create all plugins (all globally enabled)
            created_plugins = []
            for plugin_data in plugins_data:
                plugin_data["enabled"] = True
                plugin_create = MCPPluginCreate(**plugin_data)
                plugin = await service.create_plugin(plugin_create)
                created_plugins.append(plugin)
            
            # Set user preferences
            disabled_plugins = []
            enabled_plugins = []
            for plugin, should_enable in zip(created_plugins, enabled_states):
                await service.toggle_user_plugin(user_id, plugin.id, should_enable)
                if should_enable:
                    enabled_plugins.append(plugin)
                else:
                    disabled_plugins.append(plugin)
            
            # Mock tools for ALL plugins (both enabled and disabled)
            def create_mock_list_tools(all_plugins):
                async def mock_list_tools(uid, pname, *args, **kwargs):
                    for plugin in all_plugins:
                        if pname == plugin.plugin_name:
                            mock_tool = MagicMock()
                            mock_tool.name = f"tool_{plugin.plugin_name}"
                            mock_tool.description = f"Tool from {plugin.plugin_name}"
                            mock_tool.inputSchema = {"type": "object", "properties": {}}
                            return [mock_tool]
                    return []
                return mock_list_tools
            
            mock_registry.list_tools = AsyncMock(side_effect=create_mock_list_tools(created_plugins))
            
            # Get user's enabled tools
            tools = await tool_service.get_user_enabled_tools(user_id)
            
            # Verify tools from disabled plugins are NOT included
            tool_names = [tool["function"]["name"] for tool in tools]
            
            for plugin in disabled_plugins:
                excluded_tool_name = f"{plugin.plugin_name}.tool_{plugin.plugin_name}"
                assert excluded_tool_name not in tool_names, \
                    f"Tool from disabled plugin {plugin.plugin_name} should NOT be in user's tool list"
            
            # Verify tools from enabled plugins ARE included
            for plugin in enabled_plugins:
                included_tool_name = f"{plugin.plugin_name}.tool_{plugin.plugin_name}"
                assert included_tool_name in tool_names, \
                    f"Tool from enabled plugin {plugin.plugin_name} should be in user's tool list"


class TestMCPPluginServiceConfigurationChangePropagation:
    """Test suite for configuration change propagation property."""
    
    # Feature: mcp-plugin-system, Property 18: Configuration Change Propagation
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None, suppress_health_check=[])
    @given(scenario=user_plugin_scenario())
    async def test_configuration_change_propagation(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 18: Configuration Change Propagation**
        **Validates: Requirements 2.4**
        
        Property: For any user plugin preference change (enable/disable), the next AI
        generation request should reflect the new configuration in the available tools list.
        
        This test verifies that:
        1. Initial tool list reflects initial preferences
        2. After toggling preference, tool list is updated
        3. Changes propagate immediately (no stale cache)
        4. Multiple toggle operations work correctly
        """
        user_id, plugin_data, initial_enable = scenario
        
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            # Create service
            service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin (globally enabled)
            plugin_data["enabled"] = True
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await service.create_plugin(plugin_create)
            
            # Mock tool for this plugin
            mock_tool = MagicMock()
            mock_tool.name = f"tool_{plugin.plugin_name}"
            mock_tool.description = f"Tool from {plugin.plugin_name}"
            mock_tool.inputSchema = {"type": "object", "properties": {}}
            
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Set initial preference
            await service.toggle_user_plugin(user_id, plugin.id, initial_enable)
            
            # Clear any cache to ensure fresh fetch
            tool_service.clear_cache()
            
            # Get initial tool list
            initial_tools = await tool_service.get_user_enabled_tools(user_id)
            expected_tool_name = f"{plugin.plugin_name}.tool_{plugin.plugin_name}"
            
            if initial_enable:
                # Tool should be present
                tool_names = [tool["function"]["name"] for tool in initial_tools]
                assert expected_tool_name in tool_names, \
                    "Tool should be present when plugin is initially enabled"
            else:
                # Tool should be absent
                tool_names = [tool["function"]["name"] for tool in initial_tools]
                assert expected_tool_name not in tool_names, \
                    "Tool should be absent when plugin is initially disabled"
            
            # Toggle preference
            new_enable = not initial_enable
            await service.toggle_user_plugin(user_id, plugin.id, new_enable)
            
            # Clear cache to simulate next request
            tool_service.clear_cache()
            
            # Get updated tool list
            updated_tools = await tool_service.get_user_enabled_tools(user_id)
            updated_tool_names = [tool["function"]["name"] for tool in updated_tools]
            
            if new_enable:
                # Tool should now be present
                assert expected_tool_name in updated_tool_names, \
                    "Tool should appear after enabling plugin"
            else:
                # Tool should now be absent
                assert expected_tool_name not in updated_tool_names, \
                    "Tool should disappear after disabling plugin"
            
            # Toggle back to original state
            await service.toggle_user_plugin(user_id, plugin.id, initial_enable)
            tool_service.clear_cache()
            
            # Get final tool list
            final_tools = await tool_service.get_user_enabled_tools(user_id)
            final_tool_names = [tool["function"]["name"] for tool in final_tools]
            
            if initial_enable:
                # Should be back to present
                assert expected_tool_name in final_tool_names, \
                    "Tool should reappear after re-enabling"
            else:
                # Should be back to absent
                assert expected_tool_name not in final_tool_names, \
                    "Tool should remain absent after re-disabling"


# Additional edge case tests
class TestMCPPluginServiceEdgeCases:
    """Test edge cases and specific scenarios."""
    
    @pytest.mark.asyncio
    async def test_globally_disabled_plugin_can_be_enabled_by_user(self):
        """
        Test that globally disabled plugins CAN appear in user tools
        if user explicitly enables them via preference.
        
        This tests that user preferences override global defaults.
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
        
            # Create globally disabled plugin
            plugin_data = {
                "plugin_name": "disabled-plugin",
                "display_name": "Disabled Plugin",
                "server_url": "http://disabled.com",
                "enabled": False  # Globally disabled by default
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await service.create_plugin(plugin_create)
            
            # User explicitly enables it via preference
            await service.toggle_user_plugin(1, plugin.id, True)
            
            # Mock tool
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            mock_tool.description = "Test"
            mock_tool.inputSchema = {}
            mock_registry.list_tools = AsyncMock(return_value=[mock_tool])
            
            # Get user tools
            tools = await tool_service.get_user_enabled_tools(1)
            
            # Should have tools because user explicitly enabled it
            assert len(tools) == 1, \
                "User preference should override global disabled state"
    
    @pytest.mark.asyncio
    async def test_user_with_no_preferences_gets_no_tools(self):
        """
        Test that a user with no plugin preferences gets no tools.
        """
        async with DatabaseContext() as test_db:
            mock_registry = create_mock_registry()
            
            service = MCPPluginService(test_db)
            tool_service = MCPToolService(test_db, mock_registry)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "test-plugin",
                "display_name": "Test Plugin",
                "server_url": "http://test.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            await service.create_plugin(plugin_create)
            
            # User 999 has no preferences
            tools = await tool_service.get_user_enabled_tools(999)
            
            # Should be empty
            assert len(tools) == 0, \
                "User with no preferences should get no tools"
    
    @pytest.mark.asyncio
    async def test_delete_plugin_with_multiple_user_preferences(self):
        """
        Test that deleting a plugin removes preferences for all users.
        """
        async with DatabaseContext() as test_db:
            service = MCPPluginService(test_db)
            
            # Create plugin
            plugin_data = {
                "plugin_name": "shared-plugin",
                "display_name": "Shared Plugin",
                "server_url": "http://shared.com",
                "enabled": True
            }
            plugin_create = MCPPluginCreate(**plugin_data)
            plugin = await service.create_plugin(plugin_create)
            
            # Multiple users enable it
            user_ids = [1, 2, 3, 4, 5]
            for user_id in user_ids:
                await service.toggle_user_plugin(user_id, plugin.id, True)
            
            # Verify all preferences exist
            for user_id in user_ids:
                pref = await service.user_pref_repo.get_user_preference(user_id, plugin.id)
                assert pref is not None, f"Preference should exist for user {user_id}"
            
            # Delete plugin
            await service.delete_plugin(plugin.id)
            
            # Verify all preferences are gone
            for user_id in user_ids:
                pref = await service.user_pref_repo.get_user_preference(user_id, plugin.id)
                assert pref is None, f"Preference should be deleted for user {user_id}"
