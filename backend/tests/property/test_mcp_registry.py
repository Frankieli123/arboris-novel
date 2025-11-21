"""
Property-based tests for MCP Plugin Registry.

Tests session reuse, LRU eviction, and TTL cleanup mechanisms.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch

from app.mcp.registry import MCPPluginRegistry, SessionInfo
from app.mcp.http_client import HTTPMCPClient
from app.mcp.config import MCPConfig


# Hypothesis strategies for generating test data
@st.composite
def user_plugin_pair(draw):
    """Generate random user ID and plugin name pairs.
    
    Returns a tuple of (user_id, plugin_name, server_url)
    """
    user_id = draw(st.integers(min_value=1, max_value=10000))
    plugin_name = draw(st.text(
        min_size=3, 
        max_size=20, 
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=':')
    ))
    server_url = draw(st.text(
        min_size=10, 
        max_size=50,
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P'))
    ))
    
    return user_id, plugin_name, server_url


@st.composite
def multiple_user_plugin_pairs(draw, min_pairs=2, max_pairs=10):
    """Generate multiple unique user-plugin pairs.
    
    Returns a list of (user_id, plugin_name, server_url) tuples.
    """
    num_pairs = draw(st.integers(min_value=min_pairs, max_value=max_pairs))
    pairs = []
    seen_keys = set()
    
    for i in range(num_pairs):
        # Generate unique pairs by using index
        user_id = i + 1
        plugin_name = f"plugin-{i}"
        server_url = draw(st.text(
            min_size=10, 
            max_size=50,
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P'))
        ))
        pairs.append((user_id, plugin_name, server_url))
    
    return pairs


@st.composite
def registry_capacity_scenario(draw):
    """Generate scenario for testing registry at capacity.
    
    Returns (max_clients, num_sessions_to_create) where num_sessions > max_clients
    """
    max_clients = draw(st.integers(min_value=2, max_value=10))
    num_sessions = draw(st.integers(min_value=max_clients + 1, max_value=max_clients + 5))
    
    return max_clients, num_sessions


class TestMCPPluginRegistrySessionReuse:
    """Test suite for session reuse property."""
    
    # Feature: mcp-plugin-system, Property 13: Session Reuse
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None)
    @given(pair=user_plugin_pair(), num_requests=st.integers(min_value=2, max_value=10))
    async def test_session_reuse(self, pair, num_requests):
        """
        **Feature: mcp-plugin-system, Property 13: Session Reuse**
        **Validates: Requirements 8.2**
        
        Property: For any user and plugin, repeated requests within the session TTL
        should reuse the same session object rather than creating new connections.
        
        This test verifies that:
        1. Multiple requests for the same user-plugin pair reuse the same session
        2. The session's last_used timestamp is updated on each access
        3. No new connections are created when a valid session exists
        """
        user_id, plugin_name, server_url = pair
        
        # Create registry with long TTL to ensure sessions don't expire during test
        registry = MCPPluginRegistry(max_clients=100, client_ttl=3600)
        
        # Mock the HTTP client
        mock_client = MagicMock(spec=HTTPMCPClient)
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.is_connected = MagicMock(return_value=True)
        mock_client.list_tools = AsyncMock(return_value=[])
        
        with patch('app.mcp.registry.HTTPMCPClient', return_value=mock_client):
            # First request - should create new session
            await registry.load_plugin(user_id, plugin_name, server_url)
            
            # Verify connection was established
            mock_client.connect.assert_called_once()
            initial_connect_count = mock_client.connect.call_count
            
            # Get the session info
            session_key = registry._get_session_key(user_id, plugin_name)
            assert session_key in registry._sessions, \
                "Session should exist after load_plugin"
            
            initial_session = registry._sessions[session_key]
            initial_last_used = initial_session.last_used
            
            # Make multiple subsequent requests
            for i in range(num_requests - 1):
                # Small delay to ensure timestamp changes
                await asyncio.sleep(0.01)
                
                # Get client - should reuse existing session
                client = await registry.get_client(user_id, plugin_name, server_url)
                
                # Verify it's the same client
                assert client is mock_client, \
                    f"Request {i+2} should return the same client instance"
                
                # Verify no new connection was created
                assert mock_client.connect.call_count == initial_connect_count, \
                    f"Request {i+2} should not create new connection (reuse existing)"
                
                # Verify session still exists and is the same object
                current_session = registry._sessions.get(session_key)
                assert current_session is not None, \
                    f"Session should still exist after request {i+2}"
                assert current_session is initial_session, \
                    f"Session object should be the same after request {i+2}"
                
                # Verify last_used was updated
                assert current_session.last_used > initial_last_used, \
                    f"last_used should be updated after request {i+2}"
                
                initial_last_used = current_session.last_used
            
            # Verify total sessions count
            assert len(registry._sessions) == 1, \
                "Should only have one session for the same user-plugin pair"
            
            # Cleanup
            await registry.shutdown()
    
    @pytest.mark.asyncio
    async def test_session_reuse_different_users_same_plugin(self):
        """
        Test that different users get different sessions for the same plugin.
        
        This complements the property test with a specific scenario.
        """
        registry = MCPPluginRegistry(max_clients=100, client_ttl=3600)
        plugin_name = "test-plugin"
        server_url = "http://test-server.com"
        
        mock_client1 = MagicMock(spec=HTTPMCPClient)
        mock_client1.connect = AsyncMock()
        mock_client1.disconnect = AsyncMock()
        mock_client1.is_connected = MagicMock(return_value=True)
        
        mock_client2 = MagicMock(spec=HTTPMCPClient)
        mock_client2.connect = AsyncMock()
        mock_client2.disconnect = AsyncMock()
        mock_client2.is_connected = MagicMock(return_value=True)
        
        # Use side_effect to return different clients
        with patch('app.mcp.registry.HTTPMCPClient', side_effect=[mock_client1, mock_client2]):
            # Load plugin for user 1
            await registry.load_plugin(1, plugin_name, server_url)
            
            # Load plugin for user 2
            await registry.load_plugin(2, plugin_name, server_url)
            
            # Verify two separate sessions exist
            assert len(registry._sessions) == 2
            
            # Verify each user gets their own client
            client1 = await registry.get_client(1, plugin_name, server_url)
            client2 = await registry.get_client(2, plugin_name, server_url)
            
            assert client1 is mock_client1
            assert client2 is mock_client2
            assert client1 is not client2
            
            await registry.shutdown()


class TestMCPPluginRegistryLRUEviction:
    """Test suite for LRU eviction property."""
    
    # Feature: mcp-plugin-system, Property 14: LRU Eviction
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(scenario=registry_capacity_scenario())
    async def test_lru_eviction(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 14: LRU Eviction**
        **Validates: Requirements 8.3**
        
        Property: For any registry at maximum capacity, when a new session is needed,
        the least recently used session should be evicted first.
        
        This test verifies that:
        1. Registry respects the max_clients limit
        2. When capacity is reached, the LRU session is evicted
        3. The evicted session is properly disconnected
        4. New session can be created after eviction
        """
        max_clients, num_sessions = scenario
        
        # Create registry with limited capacity
        registry = MCPPluginRegistry(max_clients=max_clients, client_ttl=3600)
        
        # Track created clients
        created_clients = []
        
        def create_mock_client(server_url, headers=None, timeout=None):
            mock_client = MagicMock(spec=HTTPMCPClient)
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client.is_connected = MagicMock(return_value=True)
            created_clients.append(mock_client)
            return mock_client
        
        with patch('app.mcp.registry.HTTPMCPClient', side_effect=create_mock_client):
            # Create sessions up to capacity
            sessions_info = []
            for i in range(max_clients):
                user_id = i + 1
                plugin_name = f"plugin-{i}"
                server_url = f"http://server-{i}.com"
                
                await registry.load_plugin(user_id, plugin_name, server_url)
                sessions_info.append((user_id, plugin_name, server_url))
                
                # Small delay to ensure different timestamps
                await asyncio.sleep(0.01)
            
            # Verify we're at capacity
            assert len(registry._sessions) == max_clients, \
                f"Should have {max_clients} sessions at capacity"
            
            # Keep track of which sessions should exist
            # We'll keep accessing the first session to keep it alive
            first_user_id, first_plugin_name, first_server_url = sessions_info[0]
            
            # Now create additional sessions beyond capacity
            evictions_expected = num_sessions - max_clients
            for i in range(max_clients, num_sessions):
                # Access the first session before each new load to keep it fresh
                await asyncio.sleep(0.01)
                await registry.get_client(first_user_id, first_plugin_name, first_server_url)
                
                user_id = i + 1
                plugin_name = f"plugin-{i}"
                server_url = f"http://server-{i}.com"
                
                # This should trigger LRU eviction
                await registry.load_plugin(user_id, plugin_name, server_url)
                
                # Verify we're still at capacity (not exceeding)
                assert len(registry._sessions) <= max_clients, \
                    f"Should not exceed max_clients ({max_clients})"
                
                # Verify the first session still exists (it was accessed most recently)
                first_session_key = registry._get_session_key(first_user_id, first_plugin_name)
                assert first_session_key in registry._sessions, \
                    "Most recently accessed session should not be evicted"
            
            # Verify disconnect was called on evicted clients
            # At least one client should have been disconnected
            disconnected_count = sum(
                1 for client in created_clients 
                if client.disconnect.called
            )
            expected_evictions = num_sessions - max_clients
            assert disconnected_count >= expected_evictions, \
                f"Should have disconnected at least {expected_evictions} clients"
            
            await registry.shutdown()
    
    @pytest.mark.asyncio
    async def test_lru_eviction_specific_order(self):
        """
        Test LRU eviction with specific access pattern.
        
        This is a concrete example that complements the property test.
        """
        registry = MCPPluginRegistry(max_clients=3, client_ttl=3600)
        
        clients = []
        def create_mock_client(server_url, headers=None, timeout=None):
            mock_client = MagicMock(spec=HTTPMCPClient)
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client.is_connected = MagicMock(return_value=True)
            clients.append(mock_client)
            return mock_client
        
        with patch('app.mcp.registry.HTTPMCPClient', side_effect=create_mock_client):
            # Create 3 sessions (at capacity)
            await registry.load_plugin(1, "plugin-1", "http://server-1.com")
            await asyncio.sleep(0.01)
            await registry.load_plugin(2, "plugin-2", "http://server-2.com")
            await asyncio.sleep(0.01)
            await registry.load_plugin(3, "plugin-3", "http://server-3.com")
            
            assert len(registry._sessions) == 3
            
            # Access plugin-1 to make it recently used
            await asyncio.sleep(0.01)
            await registry.get_client(1, "plugin-1", "http://server-1.com")
            
            # Now plugin-2 is LRU, then plugin-3, then plugin-1
            
            # Create new session - should evict plugin-2
            await registry.load_plugin(4, "plugin-4", "http://server-4.com")
            
            assert len(registry._sessions) == 3
            assert registry._get_session_key(1, "plugin-1") in registry._sessions
            assert registry._get_session_key(2, "plugin-2") not in registry._sessions  # Evicted
            assert registry._get_session_key(3, "plugin-3") in registry._sessions
            assert registry._get_session_key(4, "plugin-4") in registry._sessions
            
            # Verify plugin-2's client was disconnected
            assert clients[1].disconnect.called
            
            await registry.shutdown()


class TestMCPPluginRegistryTTLCleanup:
    """Test suite for TTL cleanup property."""
    
    # Feature: mcp-plugin-system, Property 15: Session TTL Cleanup
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None)
    @given(
        pairs=multiple_user_plugin_pairs(min_pairs=2, max_pairs=5),
        ttl_seconds=st.integers(min_value=1, max_value=5)
    )
    async def test_session_ttl_cleanup(self, pairs, ttl_seconds):
        """
        **Feature: mcp-plugin-system, Property 15: Session TTL Cleanup**
        **Validates: Requirements 8.4**
        
        Property: For any session that has been idle for longer than CLIENT_TTL_SECONDS,
        the cleanup task should close and remove that session.
        
        This test verifies that:
        1. Sessions that exceed TTL are identified as expired
        2. Expired sessions are properly disconnected
        3. Expired sessions are removed from the registry
        4. Active sessions (within TTL) are not affected
        """
        # Create registry with short TTL for testing
        registry = MCPPluginRegistry(max_clients=100, client_ttl=ttl_seconds)
        
        # Track created clients
        created_clients = {}
        
        def create_mock_client(server_url, headers=None, timeout=None):
            mock_client = MagicMock(spec=HTTPMCPClient)
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client.is_connected = MagicMock(return_value=True)
            return mock_client
        
        with patch('app.mcp.registry.HTTPMCPClient', side_effect=create_mock_client):
            # Create sessions for all pairs
            for user_id, plugin_name, server_url in pairs:
                await registry.load_plugin(user_id, plugin_name, server_url)
                session_key = registry._get_session_key(user_id, plugin_name)
                created_clients[session_key] = registry._sessions[session_key].client
                
                # Small delay between creations
                await asyncio.sleep(0.01)
            
            initial_session_count = len(registry._sessions)
            assert initial_session_count == len(pairs), \
                "Should have created one session per pair"
            
            # Keep the first session active by accessing it
            if pairs:
                first_user_id, first_plugin_name, first_server_url = pairs[0]
                
                # Wait for TTL to expire
                await asyncio.sleep(ttl_seconds + 0.5)
                
                # Access first session to keep it alive
                await registry.get_client(first_user_id, first_plugin_name, first_server_url)
                
                # Run cleanup
                await registry.cleanup_expired_sessions()
                
                # Verify first session still exists (it was accessed recently)
                first_session_key = registry._get_session_key(first_user_id, first_plugin_name)
                assert first_session_key in registry._sessions, \
                    "Recently accessed session should not be cleaned up"
                
                # Verify other sessions were cleaned up (they exceeded TTL)
                for user_id, plugin_name, _ in pairs[1:]:
                    session_key = registry._get_session_key(user_id, plugin_name)
                    assert session_key not in registry._sessions, \
                        f"Expired session {session_key} should be cleaned up"
                    
                    # Verify disconnect was called
                    if session_key in created_clients:
                        assert created_clients[session_key].disconnect.called, \
                            f"Disconnect should be called for expired session {session_key}"
                
                # Verify session count decreased
                assert len(registry._sessions) < initial_session_count, \
                    "Session count should decrease after cleanup"
            
            await registry.shutdown()
    
    @pytest.mark.asyncio
    async def test_ttl_cleanup_disconnected_sessions(self):
        """
        Test that cleanup also removes sessions with disconnected clients.
        
        This complements the property test with a specific edge case.
        """
        registry = MCPPluginRegistry(max_clients=100, client_ttl=3600)
        
        mock_client1 = MagicMock(spec=HTTPMCPClient)
        mock_client1.connect = AsyncMock()
        mock_client1.disconnect = AsyncMock()
        mock_client1.is_connected = MagicMock(return_value=True)
        
        mock_client2 = MagicMock(spec=HTTPMCPClient)
        mock_client2.connect = AsyncMock()
        mock_client2.disconnect = AsyncMock()
        # This client will report as disconnected
        mock_client2.is_connected = MagicMock(return_value=False)
        
        with patch('app.mcp.registry.HTTPMCPClient', side_effect=[mock_client1, mock_client2]):
            # Create two sessions
            await registry.load_plugin(1, "plugin-1", "http://server-1.com")
            await registry.load_plugin(2, "plugin-2", "http://server-2.com")
            
            assert len(registry._sessions) == 2
            
            # Run cleanup - should remove the disconnected session
            await registry.cleanup_expired_sessions()
            
            # Verify disconnected session was removed
            assert len(registry._sessions) == 1
            assert registry._get_session_key(1, "plugin-1") in registry._sessions
            assert registry._get_session_key(2, "plugin-2") not in registry._sessions
            
            # Verify disconnect was called on the removed session
            assert mock_client2.disconnect.called
            
            await registry.shutdown()
    
    @pytest.mark.asyncio
    async def test_cleanup_task_runs_periodically(self):
        """
        Test that the cleanup task runs periodically when started.
        """
        # Use very short cleanup interval for testing
        with patch.object(MCPConfig, 'CLEANUP_INTERVAL_SECONDS', 0.1):
            registry = MCPPluginRegistry(max_clients=100, client_ttl=1)
            
            mock_client = MagicMock(spec=HTTPMCPClient)
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client.is_connected = MagicMock(return_value=True)
            
            with patch('app.mcp.registry.HTTPMCPClient', return_value=mock_client):
                # Create a session
                await registry.load_plugin(1, "plugin-1", "http://server-1.com")
                
                # Start cleanup task
                await registry.start_cleanup_task()
                
                # Wait for TTL to expire
                await asyncio.sleep(1.5)
                
                # Wait for cleanup task to run (at least once)
                await asyncio.sleep(0.3)
                
                # Session should be cleaned up
                assert len(registry._sessions) == 0, \
                    "Cleanup task should have removed expired session"
                
                await registry.shutdown()
