"""
Unit tests for MCP Plugin Repository layer.

Tests CRUD operations, database constraints, and relationships.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models.mcp_plugin import MCPPlugin, UserPluginPreference
from app.models.user import User
from app.repositories.mcp_plugin_repository import MCPPluginRepository
from app.repositories.user_plugin_preference_repository import UserPluginPreferenceRepository


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add partial unique index for default plugins (SQLite specific)
        await conn.execute(
            text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_default_plugin_unique_name 
            ON mcp_plugins(plugin_name) WHERE user_id IS NULL
            """)
        )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


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


class TestMCPPluginRepository:
    """Test MCPPluginRepository CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_plugin(self, test_db: AsyncSession):
        """Test creating a new plugin."""
        repo = MCPPluginRepository(test_db)
        
        plugin = MCPPlugin(
            plugin_name="test_plugin",
            display_name="Test Plugin",
            plugin_type="http",
            server_url="http://localhost:8000",
            enabled=True
        )
        
        created = await repo.add(plugin)
        await test_db.commit()
        await test_db.refresh(created)
        
        assert created.id is not None
        assert created.plugin_name == "test_plugin"
        assert created.display_name == "Test Plugin"
        assert created.enabled is True
    
    @pytest.mark.asyncio
    async def test_get_plugin_by_id(self, test_db: AsyncSession):
        """Test retrieving a plugin by ID."""
        repo = MCPPluginRepository(test_db)
        
        plugin = MCPPlugin(
            plugin_name="test_plugin",
            display_name="Test Plugin",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        retrieved = await repo.get(id=plugin.id)
        assert retrieved is not None
        assert retrieved.id == plugin.id
        assert retrieved.plugin_name == "test_plugin"
    
    @pytest.mark.asyncio
    async def test_get_plugin_by_name(self, test_db: AsyncSession):
        """Test retrieving a plugin by name."""
        repo = MCPPluginRepository(test_db)
        
        plugin = MCPPlugin(
            plugin_name="unique_plugin",
            display_name="Unique Plugin",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin)
        await test_db.commit()
        
        retrieved = await repo.get_by_name("unique_plugin")
        assert retrieved is not None
        assert retrieved.plugin_name == "unique_plugin"
    
    @pytest.mark.asyncio
    async def test_unique_default_plugin_name_constraint(self, test_db: AsyncSession):
        """Test that default plugin names must be unique."""
        repo = MCPPluginRepository(test_db)
        
        # Create first default plugin
        plugin1 = MCPPlugin(
            user_id=None,  # Default plugin
            plugin_name="duplicate",
            display_name="First",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin1)
        await test_db.commit()
        
        # Try to create another default plugin with same name
        plugin2 = MCPPlugin(
            user_id=None,  # Default plugin
            plugin_name="duplicate",
            display_name="Second",
            server_url="http://localhost:8001"
        )
        
        with pytest.raises(IntegrityError):
            await repo.add(plugin2)
            await test_db.commit()
    
    @pytest.mark.asyncio
    async def test_unique_user_plugin_name_constraint(self, test_db: AsyncSession, test_user: User):
        """Test that user plugin names must be unique per user."""
        repo = MCPPluginRepository(test_db)
        
        # Create first user plugin
        plugin1 = MCPPlugin(
            user_id=test_user.id,
            plugin_name="duplicate",
            display_name="First",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin1)
        await test_db.commit()
        
        # Try to create another plugin with same name for same user
        plugin2 = MCPPlugin(
            user_id=test_user.id,
            plugin_name="duplicate",
            display_name="Second",
            server_url="http://localhost:8001"
        )
        
        with pytest.raises(IntegrityError):
            await repo.add(plugin2)
            await test_db.commit()
    
    @pytest.mark.asyncio
    async def test_default_and_user_plugin_can_share_name(self, test_db: AsyncSession, test_user: User):
        """Test that default and user plugins can have the same name."""
        repo = MCPPluginRepository(test_db)
        
        # Create default plugin
        default_plugin = MCPPlugin(
            user_id=None,
            plugin_name="shared_name",
            display_name="Default",
            server_url="http://localhost:8000"
        )
        await repo.add(default_plugin)
        await test_db.commit()
        
        # Create user plugin with same name - should succeed
        user_plugin = MCPPlugin(
            user_id=test_user.id,
            plugin_name="shared_name",
            display_name="User",
            server_url="http://localhost:8001"
        )
        await repo.add(user_plugin)
        await test_db.commit()
        
        # Both should exist
        all_plugins = await repo.get_all_available_plugins(test_user.id)
        assert len(all_plugins) == 2
    
    @pytest.mark.asyncio
    async def test_list_enabled_plugins(self, test_db: AsyncSession):
        """Test listing only enabled plugins."""
        repo = MCPPluginRepository(test_db)
        
        # Create enabled plugin
        enabled = MCPPlugin(
            plugin_name="enabled",
            display_name="Enabled",
            server_url="http://localhost:8000",
            enabled=True
        )
        await repo.add(enabled)
        
        # Create disabled plugin
        disabled = MCPPlugin(
            plugin_name="disabled",
            display_name="Disabled",
            server_url="http://localhost:8001",
            enabled=False
        )
        await repo.add(disabled)
        await test_db.commit()
        
        enabled_list = await repo.list_enabled()
        assert len(enabled_list) == 1
        assert enabled_list[0].plugin_name == "enabled"
    
    @pytest.mark.asyncio
    async def test_list_by_category(self, test_db: AsyncSession):
        """Test listing plugins by category."""
        repo = MCPPluginRepository(test_db)
        
        search_plugin = MCPPlugin(
            plugin_name="search1",
            display_name="Search 1",
            server_url="http://localhost:8000",
            category="search"
        )
        await repo.add(search_plugin)
        
        file_plugin = MCPPlugin(
            plugin_name="file1",
            display_name="File 1",
            server_url="http://localhost:8001",
            category="file"
        )
        await repo.add(file_plugin)
        await test_db.commit()
        
        search_list = await repo.list_by_category("search")
        assert len(search_list) == 1
        assert search_list[0].category == "search"
    
    @pytest.mark.asyncio
    async def test_update_plugin(self, test_db: AsyncSession):
        """Test updating a plugin."""
        repo = MCPPluginRepository(test_db)
        
        plugin = MCPPlugin(
            plugin_name="update_test",
            display_name="Original",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        await repo.update_fields(plugin, display_name="Updated", enabled=False)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        assert plugin.display_name == "Updated"
        assert plugin.enabled is False
    
    @pytest.mark.asyncio
    async def test_delete_plugin(self, test_db: AsyncSession):
        """Test deleting a plugin."""
        repo = MCPPluginRepository(test_db)
        
        plugin = MCPPlugin(
            plugin_name="delete_test",
            display_name="To Delete",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        plugin_id = plugin.id
        await repo.delete(plugin)
        await test_db.commit()
        
        deleted = await repo.get(id=plugin_id)
        assert deleted is None
    
    @pytest.mark.asyncio
    async def test_get_default_plugins(self, test_db: AsyncSession, test_user: User):
        """Test retrieving all default plugins (user_id = NULL)."""
        repo = MCPPluginRepository(test_db)
        
        # Create default plugins (user_id = None)
        default1 = MCPPlugin(
            user_id=None,
            plugin_name="default1",
            display_name="Default 1",
            server_url="http://localhost:8000"
        )
        default2 = MCPPlugin(
            user_id=None,
            plugin_name="default2",
            display_name="Default 2",
            server_url="http://localhost:8001"
        )
        
        # Create user plugin
        user_plugin = MCPPlugin(
            user_id=test_user.id,
            plugin_name="user_plugin",
            display_name="User Plugin",
            server_url="http://localhost:8002"
        )
        
        test_db.add_all([default1, default2, user_plugin])
        await test_db.commit()
        
        # Get default plugins
        defaults = await repo.get_default_plugins()
        
        assert len(defaults) == 2
        plugin_names = {p.plugin_name for p in defaults}
        assert "default1" in plugin_names
        assert "default2" in plugin_names
        assert "user_plugin" not in plugin_names
    
    @pytest.mark.asyncio
    async def test_get_user_plugins(self, test_db: AsyncSession, test_user: User):
        """Test retrieving user-specific plugins."""
        repo = MCPPluginRepository(test_db)
        
        # Create another user
        user2 = User(
            username="user2",
            email="user2@example.com",
            hashed_password="hashed",
            is_active=True
        )
        test_db.add(user2)
        await test_db.commit()
        await test_db.refresh(user2)
        
        # Create plugins for test_user
        user1_plugin1 = MCPPlugin(
            user_id=test_user.id,
            plugin_name="user1_plugin1",
            display_name="User 1 Plugin 1",
            server_url="http://localhost:8000"
        )
        user1_plugin2 = MCPPlugin(
            user_id=test_user.id,
            plugin_name="user1_plugin2",
            display_name="User 1 Plugin 2",
            server_url="http://localhost:8001"
        )
        
        # Create plugin for user2
        user2_plugin = MCPPlugin(
            user_id=user2.id,
            plugin_name="user2_plugin",
            display_name="User 2 Plugin",
            server_url="http://localhost:8002"
        )
        
        # Create default plugin
        default_plugin = MCPPlugin(
            user_id=None,
            plugin_name="default",
            display_name="Default",
            server_url="http://localhost:8003"
        )
        
        test_db.add_all([user1_plugin1, user1_plugin2, user2_plugin, default_plugin])
        await test_db.commit()
        
        # Get user1's plugins
        user1_plugins = await repo.get_user_plugins(test_user.id)
        
        assert len(user1_plugins) == 2
        plugin_names = {p.plugin_name for p in user1_plugins}
        assert "user1_plugin1" in plugin_names
        assert "user1_plugin2" in plugin_names
        assert "user2_plugin" not in plugin_names
        assert "default" not in plugin_names
    
    @pytest.mark.asyncio
    async def test_get_all_available_plugins(self, test_db: AsyncSession, test_user: User):
        """Test retrieving all available plugins (default + user plugins)."""
        repo = MCPPluginRepository(test_db)
        
        # Create another user
        user2 = User(
            username="user2",
            email="user2@example.com",
            hashed_password="hashed",
            is_active=True
        )
        test_db.add(user2)
        await test_db.commit()
        await test_db.refresh(user2)
        
        # Create default plugins
        default1 = MCPPlugin(
            user_id=None,
            plugin_name="default1",
            display_name="Default 1",
            server_url="http://localhost:8000"
        )
        default2 = MCPPlugin(
            user_id=None,
            plugin_name="default2",
            display_name="Default 2",
            server_url="http://localhost:8001"
        )
        
        # Create user1 plugins
        user1_plugin = MCPPlugin(
            user_id=test_user.id,
            plugin_name="user1_plugin",
            display_name="User 1 Plugin",
            server_url="http://localhost:8002"
        )
        
        # Create user2 plugin
        user2_plugin = MCPPlugin(
            user_id=user2.id,
            plugin_name="user2_plugin",
            display_name="User 2 Plugin",
            server_url="http://localhost:8003"
        )
        
        test_db.add_all([default1, default2, user1_plugin, user2_plugin])
        await test_db.commit()
        
        # Get all available plugins for user1
        available = await repo.get_all_available_plugins(test_user.id)
        
        assert len(available) == 3  # 2 defaults + 1 user plugin
        plugin_names = {p.plugin_name for p in available}
        assert "default1" in plugin_names
        assert "default2" in plugin_names
        assert "user1_plugin" in plugin_names
        assert "user2_plugin" not in plugin_names
    
    @pytest.mark.asyncio
    async def test_create_default_plugin(self, test_db: AsyncSession):
        """Test creating a default plugin."""
        repo = MCPPluginRepository(test_db)
        
        plugin_data = {
            "plugin_name": "new_default",
            "display_name": "New Default",
            "server_url": "http://localhost:8000",
            "plugin_type": "http",
            "enabled": True
        }
        
        plugin = await repo.create_default_plugin(plugin_data)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        assert plugin.id is not None
        assert plugin.user_id is None  # Should be NULL for default
        assert plugin.plugin_name == "new_default"
    
    @pytest.mark.asyncio
    async def test_create_user_plugin(self, test_db: AsyncSession, test_user: User):
        """Test creating a user-specific plugin."""
        repo = MCPPluginRepository(test_db)
        
        plugin_data = {
            "plugin_name": "new_user_plugin",
            "display_name": "New User Plugin",
            "server_url": "http://localhost:8000",
            "plugin_type": "http",
            "enabled": True
        }
        
        plugin = await repo.create_user_plugin(test_user.id, plugin_data)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        assert plugin.id is not None
        assert plugin.user_id == test_user.id
        assert plugin.plugin_name == "new_user_plugin"


class TestUserPluginPreferenceRepository:
    """Test UserPluginPreferenceRepository operations."""
    
    @pytest.mark.asyncio
    async def test_create_preference(self, test_db: AsyncSession, test_user: User):
        """Test creating a user plugin preference."""
        # Create plugin
        plugin = MCPPlugin(
            plugin_name="test_plugin",
            display_name="Test",
            server_url="http://localhost:8000"
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        pref = await repo.set_user_preference(test_user.id, plugin.id, True)
        await test_db.commit()
        
        assert pref.user_id == test_user.id
        assert pref.plugin_id == plugin.id
        assert pref.enabled is True
    
    @pytest.mark.asyncio
    async def test_get_user_preference(self, test_db: AsyncSession, test_user: User):
        """Test retrieving a user's preference."""
        plugin = MCPPlugin(
            plugin_name="test_plugin",
            display_name="Test",
            server_url="http://localhost:8000"
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        await repo.set_user_preference(test_user.id, plugin.id, True)
        await test_db.commit()
        
        pref = await repo.get_user_preference(test_user.id, plugin.id)
        assert pref is not None
        assert pref.enabled is True
    
    @pytest.mark.asyncio
    async def test_get_user_preferences(self, test_db: AsyncSession, test_user: User):
        """Test retrieving all preferences for a user."""
        # Create plugins
        plugin1 = MCPPlugin(
            plugin_name="plugin1",
            display_name="Plugin 1",
            server_url="http://localhost:8000"
        )
        plugin2 = MCPPlugin(
            plugin_name="plugin2",
            display_name="Plugin 2",
            server_url="http://localhost:8001"
        )
        plugin3 = MCPPlugin(
            plugin_name="plugin3",
            display_name="Plugin 3",
            server_url="http://localhost:8002"
        )
        test_db.add_all([plugin1, plugin2, plugin3])
        await test_db.commit()
        await test_db.refresh(plugin1)
        await test_db.refresh(plugin2)
        await test_db.refresh(plugin3)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # Set preferences for plugin1 and plugin2
        await repo.set_user_preference(test_user.id, plugin1.id, True)
        await repo.set_user_preference(test_user.id, plugin2.id, False)
        # No preference for plugin3
        await test_db.commit()
        
        prefs = await repo.get_user_preferences(test_user.id)
        
        assert len(prefs) == 2
        pref_map = {p.plugin_id: p.enabled for p in prefs}
        assert plugin1.id in pref_map
        assert plugin2.id in pref_map
        assert plugin3.id not in pref_map
        assert pref_map[plugin1.id] is True
        assert pref_map[plugin2.id] is False
    
    @pytest.mark.asyncio
    async def test_update_preference(self, test_db: AsyncSession, test_user: User):
        """Test updating an existing preference."""
        plugin = MCPPlugin(
            plugin_name="test_plugin",
            display_name="Test",
            server_url="http://localhost:8000"
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # Create preference
        await repo.set_user_preference(test_user.id, plugin.id, True)
        await test_db.commit()
        
        # Update preference
        updated = await repo.set_user_preference(test_user.id, plugin.id, False)
        await test_db.commit()
        
        assert updated.enabled is False
    
    @pytest.mark.asyncio
    async def test_get_enabled_plugins_with_preferences(self, test_db: AsyncSession, test_user: User):
        """Test getting enabled plugins when user has explicit preferences."""
        # Create default plugins
        default1 = MCPPlugin(
            user_id=None,
            plugin_name="default1",
            display_name="Default 1",
            server_url="http://localhost:8000",
            enabled=True
        )
        default2 = MCPPlugin(
            user_id=None,
            plugin_name="default2",
            display_name="Default 2",
            server_url="http://localhost:8001",
            enabled=True
        )
        
        # Create user plugin
        user_plugin = MCPPlugin(
            user_id=test_user.id,
            plugin_name="user_plugin",
            display_name="User Plugin",
            server_url="http://localhost:8002",
            enabled=True
        )
        
        test_db.add_all([default1, default2, user_plugin])
        await test_db.commit()
        await test_db.refresh(default1)
        await test_db.refresh(default2)
        await test_db.refresh(user_plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # User explicitly enables default1 and disables default2
        await repo.set_user_preference(test_user.id, default1.id, True)
        await repo.set_user_preference(test_user.id, default2.id, False)
        # No preference for user_plugin, should use default enabled=True
        await test_db.commit()
        
        enabled = await repo.get_enabled_plugins(test_user.id)
        
        # Should get default1 (explicit enable) and user_plugin (default enable)
        # Should NOT get default2 (explicit disable)
        assert len(enabled) == 2
        plugin_names = {p.plugin_name for p in enabled}
        assert "default1" in plugin_names
        assert "user_plugin" in plugin_names
        assert "default2" not in plugin_names
    
    @pytest.mark.asyncio
    async def test_get_enabled_plugins_without_preferences(self, test_db: AsyncSession, test_user: User):
        """Test getting enabled plugins when user has no preferences (uses defaults)."""
        # Create default plugins with different enabled states
        enabled_default = MCPPlugin(
            user_id=None,
            plugin_name="enabled_default",
            display_name="Enabled Default",
            server_url="http://localhost:8000",
            enabled=True
        )
        disabled_default = MCPPlugin(
            user_id=None,
            plugin_name="disabled_default",
            display_name="Disabled Default",
            server_url="http://localhost:8001",
            enabled=False
        )
        
        # Create user plugins
        enabled_user = MCPPlugin(
            user_id=test_user.id,
            plugin_name="enabled_user",
            display_name="Enabled User",
            server_url="http://localhost:8002",
            enabled=True
        )
        disabled_user = MCPPlugin(
            user_id=test_user.id,
            plugin_name="disabled_user",
            display_name="Disabled User",
            server_url="http://localhost:8003",
            enabled=False
        )
        
        test_db.add_all([enabled_default, disabled_default, enabled_user, disabled_user])
        await test_db.commit()
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # No preferences set, should use plugin's default enabled state
        enabled = await repo.get_enabled_plugins(test_user.id)
        
        assert len(enabled) == 2
        plugin_names = {p.plugin_name for p in enabled}
        assert "enabled_default" in plugin_names
        assert "enabled_user" in plugin_names
        assert "disabled_default" not in plugin_names
        assert "disabled_user" not in plugin_names
    
    @pytest.mark.asyncio
    async def test_get_enabled_plugins_mixed_preferences(self, test_db: AsyncSession, test_user: User):
        """Test getting enabled plugins with mixed preference scenarios."""
        # Create plugins
        plugin1 = MCPPlugin(
            user_id=None,
            plugin_name="plugin1",
            display_name="Plugin 1",
            server_url="http://localhost:8000",
            enabled=True  # Default enabled
        )
        plugin2 = MCPPlugin(
            user_id=None,
            plugin_name="plugin2",
            display_name="Plugin 2",
            server_url="http://localhost:8001",
            enabled=False  # Default disabled
        )
        plugin3 = MCPPlugin(
            user_id=test_user.id,
            plugin_name="plugin3",
            display_name="Plugin 3",
            server_url="http://localhost:8002",
            enabled=True  # Default enabled
        )
        
        test_db.add_all([plugin1, plugin2, plugin3])
        await test_db.commit()
        await test_db.refresh(plugin1)
        await test_db.refresh(plugin2)
        await test_db.refresh(plugin3)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # User disables plugin1 (override default)
        await repo.set_user_preference(test_user.id, plugin1.id, False)
        # User enables plugin2 (override default)
        await repo.set_user_preference(test_user.id, plugin2.id, True)
        # No preference for plugin3 (use default)
        await test_db.commit()
        
        enabled = await repo.get_enabled_plugins(test_user.id)
        
        assert len(enabled) == 2
        plugin_names = {p.plugin_name for p in enabled}
        assert "plugin2" in plugin_names  # User enabled
        assert "plugin3" in plugin_names  # Default enabled
        assert "plugin1" not in plugin_names  # User disabled
    
    @pytest.mark.asyncio
    async def test_user_preference_overrides_default_enabled(self, test_db: AsyncSession, test_user: User):
        """Test that user preferences override the plugin's default enabled state."""
        # Create a plugin that is disabled by default
        plugin = MCPPlugin(
            user_id=None,
            plugin_name="disabled_default",
            display_name="Disabled Default",
            server_url="http://localhost:8000",
            enabled=False  # Disabled by default
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # User explicitly enables it via preference
        await repo.set_user_preference(test_user.id, plugin.id, True)
        await test_db.commit()
        
        # Should appear in enabled list because user preference overrides default
        enabled = await repo.get_enabled_plugins(test_user.id)
        assert len(enabled) == 1
        assert enabled[0].plugin_name == "disabled_default"
    
    @pytest.mark.asyncio
    async def test_cascade_delete_on_plugin_deletion(self, test_db: AsyncSession, test_user: User):
        """Test that preferences are deleted when plugin is deleted."""
        plugin = MCPPlugin(
            plugin_name="cascade_test",
            display_name="Cascade",
            server_url="http://localhost:8000"
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        await repo.set_user_preference(test_user.id, plugin.id, True)
        await test_db.commit()
        
        # Delete plugin
        await test_db.delete(plugin)
        await test_db.commit()
        
        # Preference should be gone
        pref = await repo.get_user_preference(test_user.id, plugin.id)
        assert pref is None
    
    @pytest.mark.asyncio
    async def test_unique_user_plugin_constraint(self, test_db: AsyncSession, test_user: User):
        """Test that user-plugin combination must be unique."""
        plugin = MCPPlugin(
            plugin_name="unique_test",
            display_name="Unique",
            server_url="http://localhost:8000"
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        # Create first preference
        pref1 = UserPluginPreference(
            user_id=test_user.id,
            plugin_id=plugin.id,
            enabled=True
        )
        test_db.add(pref1)
        await test_db.commit()
        
        # Try to create duplicate
        pref2 = UserPluginPreference(
            user_id=test_user.id,
            plugin_id=plugin.id,
            enabled=False
        )
        
        with pytest.raises(IntegrityError):
            test_db.add(pref2)
            await test_db.commit()
