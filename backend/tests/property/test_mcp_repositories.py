"""
Property-based tests for MCP Repository layer.

Tests correctness properties for repository methods that handle default and user plugins.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st, assume
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.models.mcp_plugin import MCPPlugin, UserPluginPreference
from app.models.user import User
from app.repositories.mcp_plugin_repository import MCPPluginRepository
from app.repositories.user_plugin_preference_repository import UserPluginPreferenceRepository
from app.db.base import Base


# Hypothesis strategies for generating test data
@st.composite
def plugin_name_strategy(draw):
    """Generate valid plugin names."""
    return draw(st.text(
        min_size=3,
        max_size=30,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' :')
    ))


@st.composite
def user_id_strategy(draw):
    """Generate valid user IDs."""
    return draw(st.integers(min_value=1, max_value=10000))


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
            
            # Create partial unique index for default plugins
            await conn.execute(text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_default_plugin_unique_name 
                ON mcp_plugins(plugin_name) WHERE user_id IS NULL
                """
            ))
        
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


async def create_test_user(session: AsyncSession, user_id: int) -> User:
    """Helper to create a test user."""
    user = User(
        id=user_id,
        username=f"user{user_id}",
        email=f"user{user_id}@example.com",
        hashed_password="hashed",
        is_active=True,
        is_admin=False
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


class TestUserAvailablePluginsMergeCorrectness:
    """Test suite for user available plugins merge correctness property."""
    
    # Feature: admin-mcp-defaults, Property 3: 用户可用插件合并正确性
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None, suppress_health_check=[])
    @given(
        target_user_id=user_id_strategy(),
        other_user_id=user_id_strategy(),
        num_default_plugins=st.integers(min_value=1, max_value=5),
        num_user_plugins=st.integers(min_value=1, max_value=5),
        num_other_user_plugins=st.integers(min_value=1, max_value=5)
    )
    async def test_user_available_plugins_merge_correctness(
        self,
        target_user_id,
        other_user_id,
        num_default_plugins,
        num_user_plugins,
        num_other_user_plugins
    ):
        """
        **Feature: admin-mcp-defaults, Property 3: 用户可用插件合并正确性**
        **Validates: Requirements 7.3**
        
        Property: For any user ID, querying user available plugins should return
        all default plugins and that user's custom plugins, but NOT other users' plugins.
        
        This test verifies that:
        1. get_all_available_plugins() returns all default plugins
        2. get_all_available_plugins() returns the user's own plugins
        3. get_all_available_plugins() does NOT return other users' plugins
        4. The merge is correct regardless of plugin names
        """
        # Ensure users are different
        assume(target_user_id != other_user_id)
        
        async with DatabaseContext() as test_db:
            # Create users
            await create_test_user(test_db, target_user_id)
            await create_test_user(test_db, other_user_id)
            
            repo = MCPPluginRepository(test_db)
            
            # Create default plugins
            default_plugins = []
            for i in range(num_default_plugins):
                plugin = MCPPlugin(
                    user_id=None,
                    plugin_name=f"default_plugin_{i}",
                    display_name=f"Default Plugin {i}",
                    plugin_type="http",
                    server_url=f"http://default{i}.com",
                    enabled=True
                )
                test_db.add(plugin)
                default_plugins.append(plugin)
            
            # Create target user's plugins
            target_user_plugins = []
            for i in range(num_user_plugins):
                plugin = MCPPlugin(
                    user_id=target_user_id,
                    plugin_name=f"user{target_user_id}_plugin_{i}",
                    display_name=f"User {target_user_id} Plugin {i}",
                    plugin_type="http",
                    server_url=f"http://user{target_user_id}_{i}.com",
                    enabled=True
                )
                test_db.add(plugin)
                target_user_plugins.append(plugin)
            
            # Create other user's plugins
            other_user_plugins = []
            for i in range(num_other_user_plugins):
                plugin = MCPPlugin(
                    user_id=other_user_id,
                    plugin_name=f"user{other_user_id}_plugin_{i}",
                    display_name=f"User {other_user_id} Plugin {i}",
                    plugin_type="http",
                    server_url=f"http://user{other_user_id}_{i}.com",
                    enabled=True
                )
                test_db.add(plugin)
                other_user_plugins.append(plugin)
            
            await test_db.commit()
            
            # Get available plugins for target user
            available = await repo.get_all_available_plugins(target_user_id)
            
            # Verify count: should be default + target user's plugins
            expected_count = num_default_plugins + num_user_plugins
            assert len(available) == expected_count, \
                f"Expected {expected_count} plugins, got {len(available)}"
            
            # Verify all default plugins are included
            available_ids = {p.id for p in available}
            for default_plugin in default_plugins:
                assert default_plugin.id in available_ids, \
                    f"Default plugin {default_plugin.plugin_name} not in available plugins"
            
            # Verify all target user's plugins are included
            for user_plugin in target_user_plugins:
                assert user_plugin.id in available_ids, \
                    f"User plugin {user_plugin.plugin_name} not in available plugins"
            
            # Verify NO other user's plugins are included
            for other_plugin in other_user_plugins:
                assert other_plugin.id not in available_ids, \
                    f"Other user's plugin {other_plugin.plugin_name} should not be in available plugins"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None, suppress_health_check=[])
    @given(
        user_id=user_id_strategy(),
        num_default_plugins=st.integers(min_value=0, max_value=5),
        num_user_plugins=st.integers(min_value=0, max_value=5)
    )
    async def test_available_plugins_includes_both_types(
        self,
        user_id,
        num_default_plugins,
        num_user_plugins
    ):
        """
        Test that get_all_available_plugins returns both default and user plugins.
        
        Edge case: handles zero plugins of either type.
        """
        async with DatabaseContext() as test_db:
            # Create user
            await create_test_user(test_db, user_id)
            
            repo = MCPPluginRepository(test_db)
            
            # Create default plugins
            for i in range(num_default_plugins):
                plugin = MCPPlugin(
                    user_id=None,
                    plugin_name=f"default_{i}",
                    display_name=f"Default {i}",
                    plugin_type="http",
                    server_url=f"http://default{i}.com",
                    enabled=True
                )
                test_db.add(plugin)
            
            # Create user plugins
            for i in range(num_user_plugins):
                plugin = MCPPlugin(
                    user_id=user_id,
                    plugin_name=f"user_{i}",
                    display_name=f"User {i}",
                    plugin_type="http",
                    server_url=f"http://user{i}.com",
                    enabled=True
                )
                test_db.add(plugin)
            
            await test_db.commit()
            
            # Get available plugins
            available = await repo.get_all_available_plugins(user_id)
            
            # Verify count
            expected_count = num_default_plugins + num_user_plugins
            assert len(available) == expected_count
            
            # Verify types
            default_count = sum(1 for p in available if p.user_id is None)
            user_count = sum(1 for p in available if p.user_id == user_id)
            
            assert default_count == num_default_plugins
            assert user_count == num_user_plugins


class TestUserPreferenceQueryCorrectness:
    """Test suite for user preference query correctness property."""
    
    # Feature: admin-mcp-defaults, Property 10: 用户偏好查询正确性
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None, suppress_health_check=[])
    @given(
        user_id=user_id_strategy(),
        num_plugins_with_pref=st.integers(min_value=1, max_value=5),
        num_plugins_without_pref=st.integers(min_value=1, max_value=5)
    )
    async def test_user_preference_query_correctness(
        self,
        user_id,
        num_plugins_with_pref,
        num_plugins_without_pref
    ):
        """
        **Feature: admin-mcp-defaults, Property 10: 用户偏好查询正确性**
        **Validates: Requirements 5.4**
        
        Property: For any user and plugin, if the user has set a preference,
        the query result should use the preference setting; otherwise, it should
        use the plugin's default enabled state.
        
        This test verifies that:
        1. Plugins with user preferences use the preference value
        2. Plugins without preferences use the plugin's default enabled state
        3. The logic correctly handles mixed scenarios
        """
        async with DatabaseContext() as test_db:
            # Create user
            await create_test_user(test_db, user_id)
            
            pref_repo = UserPluginPreferenceRepository(test_db)
            
            # Create plugins with preferences
            plugins_with_pref = []
            pref_values = []
            for i in range(num_plugins_with_pref):
                # Alternate between enabled and disabled defaults
                default_enabled = (i % 2 == 0)
                # Set preference to opposite of default
                pref_enabled = not default_enabled
                
                plugin = MCPPlugin(
                    user_id=None,  # Default plugin
                    plugin_name=f"with_pref_{i}",
                    display_name=f"With Pref {i}",
                    plugin_type="http",
                    server_url=f"http://withpref{i}.com",
                    enabled=default_enabled
                )
                test_db.add(plugin)
                await test_db.flush()
                await test_db.refresh(plugin)
                
                # Set user preference
                await pref_repo.set_user_preference(user_id, plugin.id, pref_enabled)
                
                plugins_with_pref.append(plugin)
                pref_values.append(pref_enabled)
            
            # Create plugins without preferences
            plugins_without_pref = []
            default_enabled_values = []
            for i in range(num_plugins_without_pref):
                # Alternate between enabled and disabled
                default_enabled = (i % 2 == 0)
                
                plugin = MCPPlugin(
                    user_id=None,  # Default plugin
                    plugin_name=f"without_pref_{i}",
                    display_name=f"Without Pref {i}",
                    plugin_type="http",
                    server_url=f"http://withoutpref{i}.com",
                    enabled=default_enabled
                )
                test_db.add(plugin)
                await test_db.flush()
                await test_db.refresh(plugin)
                
                plugins_without_pref.append(plugin)
                default_enabled_values.append(default_enabled)
            
            await test_db.commit()
            
            # Get enabled plugins
            enabled = await pref_repo.get_enabled_plugins(user_id)
            enabled_ids = {p.id for p in enabled}
            
            # Verify plugins with preferences use preference value
            for plugin, pref_value in zip(plugins_with_pref, pref_values):
                if pref_value:
                    assert plugin.id in enabled_ids, \
                        f"Plugin {plugin.plugin_name} with preference=True should be enabled"
                else:
                    assert plugin.id not in enabled_ids, \
                        f"Plugin {plugin.plugin_name} with preference=False should not be enabled"
            
            # Verify plugins without preferences use default enabled state
            for plugin, default_enabled in zip(plugins_without_pref, default_enabled_values):
                if default_enabled:
                    assert plugin.id in enabled_ids, \
                        f"Plugin {plugin.plugin_name} with default enabled=True should be enabled"
                else:
                    assert plugin.id not in enabled_ids, \
                        f"Plugin {plugin.plugin_name} with default enabled=False should not be enabled"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None, suppress_health_check=[])
    @given(
        user_id=user_id_strategy(),
        num_plugins=st.integers(min_value=1, max_value=10)
    )
    async def test_preference_overrides_default(self, user_id, num_plugins):
        """
        Test that user preferences always override the plugin's default enabled state.
        
        This is a specific case of Property 10.
        """
        async with DatabaseContext() as test_db:
            # Create user
            await create_test_user(test_db, user_id)
            
            pref_repo = UserPluginPreferenceRepository(test_db)
            
            plugins = []
            for i in range(num_plugins):
                # Create plugin with enabled=False
                plugin = MCPPlugin(
                    user_id=None,
                    plugin_name=f"plugin_{i}",
                    display_name=f"Plugin {i}",
                    plugin_type="http",
                    server_url=f"http://plugin{i}.com",
                    enabled=False  # Disabled by default
                )
                test_db.add(plugin)
                await test_db.flush()
                await test_db.refresh(plugin)
                
                # User enables it via preference
                await pref_repo.set_user_preference(user_id, plugin.id, True)
                
                plugins.append(plugin)
            
            await test_db.commit()
            
            # Get enabled plugins
            enabled = await pref_repo.get_enabled_plugins(user_id)
            
            # All plugins should be enabled despite default enabled=False
            assert len(enabled) == num_plugins, \
                f"Expected {num_plugins} enabled plugins, got {len(enabled)}"
            
            enabled_ids = {p.id for p in enabled}
            for plugin in plugins:
                assert plugin.id in enabled_ids, \
                    f"Plugin {plugin.plugin_name} should be enabled via preference"
    
    @pytest.mark.asyncio
    @settings(max_examples=30, deadline=None, suppress_health_check=[])
    @given(
        user_id=user_id_strategy(),
        num_enabled_default=st.integers(min_value=0, max_value=5),
        num_disabled_default=st.integers(min_value=0, max_value=5)
    )
    async def test_no_preferences_uses_defaults(
        self,
        user_id,
        num_enabled_default,
        num_disabled_default
    ):
        """
        Test that when no preferences are set, the plugin's default enabled state is used.
        """
        async with DatabaseContext() as test_db:
            # Create user
            await create_test_user(test_db, user_id)
            
            pref_repo = UserPluginPreferenceRepository(test_db)
            
            # Create enabled plugins
            enabled_plugins = []
            for i in range(num_enabled_default):
                plugin = MCPPlugin(
                    user_id=None,
                    plugin_name=f"enabled_{i}",
                    display_name=f"Enabled {i}",
                    plugin_type="http",
                    server_url=f"http://enabled{i}.com",
                    enabled=True
                )
                test_db.add(plugin)
                await test_db.flush()
                await test_db.refresh(plugin)
                enabled_plugins.append(plugin)
            
            # Create disabled plugins
            disabled_plugins = []
            for i in range(num_disabled_default):
                plugin = MCPPlugin(
                    user_id=None,
                    plugin_name=f"disabled_{i}",
                    display_name=f"Disabled {i}",
                    plugin_type="http",
                    server_url=f"http://disabled{i}.com",
                    enabled=False
                )
                test_db.add(plugin)
                await test_db.flush()
                await test_db.refresh(plugin)
                disabled_plugins.append(plugin)
            
            await test_db.commit()
            
            # Get enabled plugins (no preferences set)
            enabled = await pref_repo.get_enabled_plugins(user_id)
            
            # Should only get the enabled plugins
            assert len(enabled) == num_enabled_default
            
            enabled_ids = {p.id for p in enabled}
            for plugin in enabled_plugins:
                assert plugin.id in enabled_ids
            for plugin in disabled_plugins:
                assert plugin.id not in enabled_ids
