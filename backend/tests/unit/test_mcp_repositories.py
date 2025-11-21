"""
Unit tests for MCP Plugin Repository layer.

Tests CRUD operations, database constraints, and relationships.
"""

import pytest
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
    async def test_unique_plugin_name_constraint(self, test_db: AsyncSession):
        """Test that plugin names must be unique."""
        repo = MCPPluginRepository(test_db)
        
        plugin1 = MCPPlugin(
            plugin_name="duplicate",
            display_name="First",
            server_url="http://localhost:8000"
        )
        await repo.add(plugin1)
        await test_db.commit()
        
        plugin2 = MCPPlugin(
            plugin_name="duplicate",
            display_name="Second",
            server_url="http://localhost:8001"
        )
        
        with pytest.raises(IntegrityError):
            await repo.add(plugin2)
            await test_db.commit()
    
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
    async def test_get_enabled_plugins(self, test_db: AsyncSession, test_user: User):
        """Test getting all enabled plugins for a user."""
        # Create plugins
        plugin1 = MCPPlugin(
            plugin_name="plugin1",
            display_name="Plugin 1",
            server_url="http://localhost:8000",
            enabled=True
        )
        plugin2 = MCPPlugin(
            plugin_name="plugin2",
            display_name="Plugin 2",
            server_url="http://localhost:8001",
            enabled=True
        )
        plugin3 = MCPPlugin(
            plugin_name="plugin3",
            display_name="Plugin 3",
            server_url="http://localhost:8002",
            enabled=True
        )
        test_db.add_all([plugin1, plugin2, plugin3])
        await test_db.commit()
        await test_db.refresh(plugin1)
        await test_db.refresh(plugin2)
        await test_db.refresh(plugin3)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # Enable plugin1 and plugin2 for user
        await repo.set_user_preference(test_user.id, plugin1.id, True)
        await repo.set_user_preference(test_user.id, plugin2.id, True)
        await repo.set_user_preference(test_user.id, plugin3.id, False)
        await test_db.commit()
        
        enabled = await repo.get_enabled_plugins(test_user.id)
        assert len(enabled) == 2
        plugin_names = {p.plugin_name for p in enabled}
        assert "plugin1" in plugin_names
        assert "plugin2" in plugin_names
        assert "plugin3" not in plugin_names
    
    @pytest.mark.asyncio
    async def test_globally_disabled_plugin_not_in_enabled(self, test_db: AsyncSession, test_user: User):
        """Test that globally disabled plugins don't appear in enabled list."""
        plugin = MCPPlugin(
            plugin_name="disabled_global",
            display_name="Disabled",
            server_url="http://localhost:8000",
            enabled=False  # Globally disabled
        )
        test_db.add(plugin)
        await test_db.commit()
        await test_db.refresh(plugin)
        
        repo = UserPluginPreferenceRepository(test_db)
        
        # User enables it
        await repo.set_user_preference(test_user.id, plugin.id, True)
        await test_db.commit()
        
        # Should not appear in enabled list
        enabled = await repo.get_enabled_plugins(test_user.id)
        assert len(enabled) == 0
    
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
