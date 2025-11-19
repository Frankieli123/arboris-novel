"""Pytest configuration and fixtures for async task tests."""
import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set up test environment variables before importing app modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")

from app.db.base import Base
# Import all models to ensure they're registered with SQLAlchemy
from app.models import (
    User, AsyncTask, NovelProject, NovelConversation, NovelBlueprint,
    BlueprintCharacter, BlueprintRelationship, ChapterOutline, Chapter,
    ChapterVersion, ChapterEvaluation, LLMConfig, Prompt, UpdateLog,
    UsageMetric, UserDailyRequest, SystemConfig, AdminSetting
)


# Use SQLite in-memory database for testing with StaticPool to share connection
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine with shared in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,  # Use StaticPool to share the in-memory database
        connect_args={"check_same_thread": False},
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    # Make sure the user ID is loaded into the object
    _ = user.id
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test requests."""
    from app.core.security import create_access_token
    
    # Create a JWT token for the test user
    access_token = create_access_token(
        subject=str(test_user.id),
        extra_claims={"is_admin": test_user.is_admin}
    )
    
    return {
        "Authorization": f"Bearer {access_token}"
    }


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create a test admin user."""
    admin = User(
        username="testadmin",
        email="admin@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=True,
    )
    db_session.add(admin)
    await db_session.flush()
    await db_session.refresh(admin)
    _ = admin.id
    return admin


@pytest_asyncio.fixture
async def admin_token(test_admin: User) -> str:
    """Create an admin JWT token."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(
        subject=test_admin.username,
        extra_claims={"is_admin": test_admin.is_admin}
    )
    
    return access_token


@pytest_asyncio.fixture
async def user_token(test_user: User) -> str:
    """Create a regular user JWT token."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(
        subject=test_user.username,
        extra_claims={"is_admin": test_user.is_admin}
    )
    
    return access_token


@pytest_asyncio.fixture
async def test_session(db_session: AsyncSession) -> AsyncSession:
    """Alias for db_session to match test expectations."""
    return db_session


@pytest_asyncio.fixture
async def async_client(test_engine):
    """Create an async test client."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.db.session import get_session
    
    # Override the get_session dependency to use test database
    async def override_get_session():
        async_session = async_sessionmaker(
            bind=test_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with async_session() as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()
