"""
Property-based tests for HTTP MCP Client.

Tests error state recovery and reconnection mechanisms.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch

from app.mcp.http_client import HTTPMCPClient
from app.mcp.config import MCPConfig


# Hypothesis strategies for generating test data
@st.composite
def connection_scenario(draw):
    """Generate random connection scenarios for testing.
    
    Returns a tuple of (server_url, headers, should_fail_initially, should_recover)
    """
    server_url = draw(st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'P'))))
    
    # Generate headers
    num_headers = draw(st.integers(min_value=0, max_value=5))
    headers = {}
    for _ in range(num_headers):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L',))))
        value = draw(st.text(min_size=1, max_size=50))
        headers[key] = value
    
    # Determine failure and recovery behavior
    should_fail_initially = draw(st.booleans())
    should_recover = draw(st.booleans())
    
    return server_url, headers, should_fail_initially, should_recover


class TestHTTPMCPClientErrorRecovery:
    """Test suite for HTTP MCP Client error state recovery."""
    
    # Feature: mcp-plugin-system, Property 21: Error State Recovery
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None)
    @given(scenario=connection_scenario())
    async def test_error_state_recovery(self, scenario):
        """
        **Feature: mcp-plugin-system, Property 21: Error State Recovery**
        **Validates: Requirements 12.4**
        
        Property: For any session marked as error status due to connection failure,
        the next request should attempt to reconnect and restore the session to active status.
        
        This test verifies that:
        1. When a connection fails, the client properly handles the error
        2. When reconnection is attempted, the client can recover from error state
        3. The client correctly reports connection status throughout the lifecycle
        """
        server_url, headers, should_fail_initially, should_recover = scenario
        
        # Create client
        client = HTTPMCPClient(server_url, headers, timeout=MCPConfig.CONNECT_TIMEOUT_SECONDS)
        
        # Mock the streamablehttp_client context manager
        mock_stream_context = AsyncMock()
        mock_streams = (AsyncMock(), AsyncMock())
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_streams)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the ClientSession
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        
        with patch('app.mcp.http_client.streamablehttp_client', return_value=mock_stream_context):
            with patch('app.mcp.http_client.ClientSession', return_value=mock_session):
                
                # Initial connection attempt
                if should_fail_initially:
                    # Simulate connection failure
                    mock_stream_context.__aenter__.side_effect = Exception("Connection failed")
                    
                    # Verify connection fails
                    with pytest.raises(Exception, match="Connection failed"):
                        await client.connect()
                    
                    # Verify client is not connected after failure
                    assert not client.is_connected(), \
                        "Client should not be connected after connection failure"
                    
                    # Now test recovery
                    if should_recover:
                        # Reset the mock to allow successful connection
                        mock_stream_context.__aenter__.side_effect = None
                        mock_stream_context.__aenter__.return_value = mock_streams
                        
                        # Attempt reconnection
                        await client.connect()
                        
                        # Verify client is now connected
                        assert client.is_connected(), \
                            "Client should be connected after successful reconnection"
                        
                        # Verify session was initialized
                        mock_session.initialize.assert_called()
                        
                        # Clean up
                        await client.disconnect()
                        assert not client.is_connected(), \
                            "Client should not be connected after disconnect"
                    
                else:
                    # Successful initial connection
                    await client.connect()
                    
                    # Verify client is connected
                    assert client.is_connected(), \
                        "Client should be connected after successful connection"
                    
                    # Simulate connection loss by setting session to None
                    client._session = None
                    
                    # Verify client reports as disconnected
                    assert not client.is_connected(), \
                        "Client should report as disconnected when session is None"
                    
                    # Attempt reconnection
                    await client.connect()
                    
                    # Verify client is connected again
                    assert client.is_connected(), \
                        "Client should be connected after reconnection"
                    
                    # Clean up
                    await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_reconnection_after_network_interruption(self):
        """
        Test that client can recover from network interruption.
        
        This is a specific example test that complements the property test.
        """
        server_url = "http://test-server.com"
        headers = {"Authorization": "Bearer test-token"}
        
        client = HTTPMCPClient(server_url, headers)
        
        # Mock the streamablehttp_client
        mock_stream_context = AsyncMock()
        mock_streams = (AsyncMock(), AsyncMock())
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_streams)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        
        with patch('app.mcp.http_client.streamablehttp_client', return_value=mock_stream_context):
            with patch('app.mcp.http_client.ClientSession', return_value=mock_session):
                
                # Initial successful connection
                await client.connect()
                assert client.is_connected()
                
                # Simulate network interruption by clearing session
                client._session = None
                assert not client.is_connected()
                
                # Reconnect should succeed
                await client.connect()
                assert client.is_connected()
                
                # Verify initialize was called twice (initial + reconnect)
                assert mock_session.initialize.call_count == 2
                
                await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_reconnection_attempts(self):
        """
        Test that client can handle multiple reconnection attempts.
        """
        server_url = "http://test-server.com"
        client = HTTPMCPClient(server_url, {})
        
        mock_stream_context = AsyncMock()
        mock_streams = (AsyncMock(), AsyncMock())
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_streams)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        
        with patch('app.mcp.http_client.streamablehttp_client', return_value=mock_stream_context):
            with patch('app.mcp.http_client.ClientSession', return_value=mock_session):
                
                # Simulate multiple connection failures followed by success
                mock_stream_context.__aenter__.side_effect = [
                    Exception("Connection failed 1"),
                    Exception("Connection failed 2"),
                    mock_streams  # Success on third attempt
                ]
                
                # First attempt fails
                with pytest.raises(Exception, match="Connection failed 1"):
                    await client.connect()
                assert not client.is_connected()
                
                # Second attempt fails
                with pytest.raises(Exception, match="Connection failed 2"):
                    await client.connect()
                assert not client.is_connected()
                
                # Third attempt succeeds
                await client.connect()
                assert client.is_connected()
                
                await client.disconnect()
