"""
Property-based tests for MCP Plugin Schemas.

Tests configuration serialization and deserialization round-trip.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from hypothesis import given, settings, strategies as st

from app.schemas.mcp_plugin import (
    MCPPluginBase,
    MCPPluginCreate,
    MCPPluginUpdate,
    MCPPluginResponse,
    ToolDefinition,
    ToolCallResult,
    ToolMetrics,
    PluginTestReport,
)


# Hypothesis strategies for generating test data
@st.composite
def plugin_config(draw):
    """Generate random valid plugin configuration.
    
    Returns a dictionary with all fields for MCPPluginCreate.
    """
    plugin_name = draw(st.text(
        min_size=3,
        max_size=50,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' ')
    ))
    
    display_name = draw(st.text(min_size=3, max_size=100))
    
    plugin_type = draw(st.sampled_from(["http", "stdio", "sse"]))
    
    # Generate valid-looking URL
    protocol = draw(st.sampled_from(["http", "https"]))
    domain = draw(st.text(
        min_size=5,
        max_size=30,
        alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' ')
    ))
    server_url = f"{protocol}://{domain}.com"
    
    # Generate headers (optional)
    has_headers = draw(st.booleans())
    headers = None
    if has_headers:
        num_headers = draw(st.integers(min_value=1, max_value=5))
        headers = {}
        for _ in range(num_headers):
            key = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=('L',))
            ))
            value = draw(st.text(min_size=1, max_size=50))
            headers[key] = value
    
    enabled = draw(st.booleans())
    
    # Generate category (optional)
    has_category = draw(st.booleans())
    category = None
    if has_category:
        category = draw(st.sampled_from([
            "search", "filesystem", "database", "api", "tool", "other"
        ]))
    
    # Generate config (optional)
    has_config = draw(st.booleans())
    config = None
    if has_config:
        config = {}
        num_config_items = draw(st.integers(min_value=1, max_value=5))
        for _ in range(num_config_items):
            key = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=('L',))
            ))
            # Generate various types of values
            value_type = draw(st.sampled_from(["string", "int", "bool", "float"]))
            if value_type == "string":
                value = draw(st.text(min_size=0, max_size=50))
            elif value_type == "int":
                value = draw(st.integers(min_value=-1000, max_value=1000))
            elif value_type == "bool":
                value = draw(st.booleans())
            else:  # float
                value = draw(st.floats(
                    min_value=-1000.0,
                    max_value=1000.0,
                    allow_nan=False,
                    allow_infinity=False
                ))
            config[key] = value
    
    return {
        "plugin_name": plugin_name,
        "display_name": display_name,
        "plugin_type": plugin_type,
        "server_url": server_url,
        "headers": headers,
        "enabled": enabled,
        "category": category,
        "config": config,
    }


@st.composite
def plugin_update_config(draw):
    """Generate random plugin update configuration.
    
    Returns a dictionary with optional fields for MCPPluginUpdate.
    """
    config = {}
    
    # Each field is optional in update
    if draw(st.booleans()):
        config["display_name"] = draw(st.text(min_size=3, max_size=100))
    
    if draw(st.booleans()):
        protocol = draw(st.sampled_from(["http", "https"]))
        domain = draw(st.text(
            min_size=5,
            max_size=30,
            alphabet=st.characters(whitelist_categories=('L', 'N'), blacklist_characters=' ')
        ))
        config["server_url"] = f"{protocol}://{domain}.com"
    
    if draw(st.booleans()):
        num_headers = draw(st.integers(min_value=1, max_value=5))
        headers = {}
        for _ in range(num_headers):
            key = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=('L',))
            ))
            value = draw(st.text(min_size=1, max_size=50))
            headers[key] = value
        config["headers"] = headers
    
    if draw(st.booleans()):
        config["enabled"] = draw(st.booleans())
    
    if draw(st.booleans()):
        config["category"] = draw(st.sampled_from([
            "search", "filesystem", "database", "api", "tool", "other"
        ]))
    
    if draw(st.booleans()):
        extra_config = {}
        num_items = draw(st.integers(min_value=1, max_value=3))
        for _ in range(num_items):
            key = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=('L',))
            ))
            value = draw(st.text(min_size=0, max_size=50))
            extra_config[key] = value
        config["config"] = extra_config
    
    return config


class TestMCPPluginSchemaRoundTrip:
    """Test suite for plugin schema round-trip serialization."""
    
    # Feature: mcp-plugin-system, Property 1: Plugin Configuration Round-Trip
    @settings(max_examples=100, deadline=None)
    @given(config=plugin_config())
    def test_plugin_create_round_trip(self, config):
        """
        **Feature: mcp-plugin-system, Property 1: Plugin Configuration Round-Trip**
        **Validates: Requirements 1.2**
        
        Property: For any valid plugin configuration, serializing to Pydantic model
        and then converting back to dict should preserve all fields.
        
        This test verifies that:
        1. MCPPluginCreate can be instantiated from any valid config dict
        2. The model can be serialized back to dict
        3. All fields are preserved in the round-trip
        4. Optional fields (None values) are handled correctly
        """
        # Create Pydantic model from config
        plugin = MCPPluginCreate(**config)
        
        # Verify model was created successfully
        assert plugin is not None, "Plugin model should be created"
        
        # Serialize back to dict
        serialized = plugin.model_dump()
        
        # Verify all original fields are present in serialized form
        for key, original_value in config.items():
            assert key in serialized, f"Field '{key}' should be present in serialized data"
            
            serialized_value = serialized[key]
            
            # Compare values, handling None specially
            if original_value is None:
                assert serialized_value is None, \
                    f"Field '{key}' should be None in serialized data"
            else:
                assert serialized_value == original_value, \
                    f"Field '{key}' value mismatch: {serialized_value} != {original_value}"
        
        # Verify we can create a new model from serialized data (full round-trip)
        plugin_roundtrip = MCPPluginCreate(**serialized)
        
        # Verify the round-trip model is equivalent
        assert plugin_roundtrip.plugin_name == plugin.plugin_name
        assert plugin_roundtrip.display_name == plugin.display_name
        assert plugin_roundtrip.plugin_type == plugin.plugin_type
        assert plugin_roundtrip.server_url == plugin.server_url
        assert plugin_roundtrip.headers == plugin.headers
        assert plugin_roundtrip.enabled == plugin.enabled
        assert plugin_roundtrip.category == plugin.category
        assert plugin_roundtrip.config == plugin.config
    
    @settings(max_examples=100, deadline=None)
    @given(config=plugin_config())
    def test_plugin_base_round_trip(self, config):
        """
        Test round-trip for MCPPluginBase schema.
        
        This ensures the base schema also preserves all fields correctly.
        """
        # Create base model
        plugin = MCPPluginBase(**config)
        
        # Serialize
        serialized = plugin.model_dump()
        
        # Verify all fields preserved
        for key, original_value in config.items():
            assert key in serialized
            if original_value is None:
                assert serialized[key] is None
            else:
                assert serialized[key] == original_value
        
        # Round-trip
        plugin_roundtrip = MCPPluginBase(**serialized)
        assert plugin_roundtrip.model_dump() == serialized
    
    @settings(max_examples=100, deadline=None)
    @given(update_config=plugin_update_config())
    def test_plugin_update_round_trip(self, update_config):
        """
        Test round-trip for MCPPluginUpdate schema.
        
        Update schemas have all optional fields, so this tests partial updates.
        """
        # Skip if no fields provided (empty update)
        if not update_config:
            return
        
        # Create update model
        plugin_update = MCPPluginUpdate(**update_config)
        
        # Serialize
        serialized = plugin_update.model_dump(exclude_unset=True)
        
        # Verify only provided fields are in serialized form
        for key in update_config.keys():
            assert key in serialized, \
                f"Provided field '{key}' should be in serialized data"
        
        # Verify values match
        for key, original_value in update_config.items():
            if original_value is None:
                assert serialized[key] is None
            else:
                assert serialized[key] == original_value
        
        # Round-trip
        plugin_update_roundtrip = MCPPluginUpdate(**serialized)
        
        # Verify round-trip preserves values
        roundtrip_serialized = plugin_update_roundtrip.model_dump(exclude_unset=True)
        assert roundtrip_serialized == serialized
    
    @settings(max_examples=100, deadline=None)
    @given(config=plugin_config())
    def test_plugin_json_round_trip(self, config):
        """
        Test JSON serialization round-trip.
        
        This verifies that the schema can be serialized to JSON and back.
        """
        # Create model
        plugin = MCPPluginCreate(**config)
        
        # Serialize to JSON string
        json_str = plugin.model_dump_json()
        
        # Verify it's a valid JSON string
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        
        # Deserialize from JSON
        plugin_from_json = MCPPluginCreate.model_validate_json(json_str)
        
        # Verify all fields match
        assert plugin_from_json.plugin_name == plugin.plugin_name
        assert plugin_from_json.display_name == plugin.display_name
        assert plugin_from_json.plugin_type == plugin.plugin_type
        assert plugin_from_json.server_url == plugin.server_url
        assert plugin_from_json.headers == plugin.headers
        assert plugin_from_json.enabled == plugin.enabled
        assert plugin_from_json.category == plugin.category
        assert plugin_from_json.config == plugin.config
    
    def test_plugin_create_with_defaults(self):
        """
        Test that default values are applied correctly.
        
        This is a specific example test that complements the property tests.
        """
        # Create with minimal required fields
        plugin = MCPPluginCreate(
            plugin_name="test-plugin",
            display_name="Test Plugin",
            server_url="http://test.com"
        )
        
        # Verify defaults are applied
        assert plugin.plugin_type == "http"
        assert plugin.enabled is True
        assert plugin.headers is None
        assert plugin.category is None
        assert plugin.config is None
    
    def test_plugin_update_empty(self):
        """
        Test that MCPPluginUpdate can be created with no fields.
        
        This is valid for updates where nothing changes.
        """
        # Create empty update
        update = MCPPluginUpdate()
        
        # Serialize with exclude_unset
        serialized = update.model_dump(exclude_unset=True)
        
        # Should be empty dict
        assert serialized == {}
    
    def test_plugin_config_with_complex_nested_data(self):
        """
        Test that complex nested config data is preserved.
        """
        config_data = {
            "plugin_name": "complex-plugin",
            "display_name": "Complex Plugin",
            "server_url": "http://complex.com",
            "config": {
                "nested": {
                    "level1": {
                        "level2": {
                            "value": "deep"
                        }
                    }
                },
                "array": [1, 2, 3, 4, 5],
                "mixed": {
                    "string": "text",
                    "number": 42,
                    "bool": True,
                    "null": None
                }
            }
        }
        
        # Create model
        plugin = MCPPluginCreate(**config_data)
        
        # Serialize
        serialized = plugin.model_dump()
        
        # Verify complex config is preserved
        assert serialized["config"] == config_data["config"]
        
        # Round-trip
        plugin_roundtrip = MCPPluginCreate(**serialized)
        assert plugin_roundtrip.config == config_data["config"]
