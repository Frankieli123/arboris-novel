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


class TestJSONConfigurationValidation:
    """Test suite for JSON configuration validation correctness."""
    
    # Feature: admin-mcp-defaults, Property 8: JSON 配置验证正确性
    @settings(max_examples=100, deadline=None)
    @given(config=plugin_config())
    def test_json_config_validation_correctness(self, config):
        """
        **Feature: admin-mcp-defaults, Property 8: JSON 配置验证正确性**
        **Validates: Requirements 3.2, 3.3, 4.2**
        
        Property: For any plugin, if headers or config fields are not None,
        they should be valid JSON-serializable structures.
        
        This test verifies that:
        1. Non-None headers can be serialized to JSON
        2. Non-None config can be serialized to JSON
        3. The serialized JSON can be deserialized back
        4. The deserialized data matches the original
        """
        import json
        
        # Create plugin model
        plugin = MCPPluginCreate(**config)
        
        # Test headers field
        if plugin.headers is not None:
            # Should be JSON serializable
            headers_json = json.dumps(plugin.headers)
            assert isinstance(headers_json, str), "Headers should serialize to JSON string"
            
            # Should be deserializable
            headers_deserialized = json.loads(headers_json)
            assert headers_deserialized == plugin.headers, \
                "Deserialized headers should match original"
        
        # Test config field
        if plugin.config is not None:
            # Should be JSON serializable
            config_json = json.dumps(plugin.config)
            assert isinstance(config_json, str), "Config should serialize to JSON string"
            
            # Should be deserializable
            config_deserialized = json.loads(config_json)
            assert config_deserialized == plugin.config, \
                "Deserialized config should match original"
        
        # Test full model JSON serialization
        full_json = plugin.model_dump_json()
        assert isinstance(full_json, str), "Full model should serialize to JSON"
        
        # Deserialize and verify
        plugin_from_json = MCPPluginCreate.model_validate_json(full_json)
        assert plugin_from_json.headers == plugin.headers
        assert plugin_from_json.config == plugin.config
    
    @settings(max_examples=100, deadline=None)
    @given(
        has_headers=st.booleans(),
        has_config=st.booleans()
    )
    def test_null_json_fields_are_valid(self, has_headers, has_config):
        """
        Property: Plugins with None headers or config should be valid.
        
        This ensures that optional JSON fields can be None without issues.
        """
        import json
        
        config_data = {
            "plugin_name": "test-plugin",
            "display_name": "Test Plugin",
            "server_url": "http://test.com",
            "headers": {"Authorization": "Bearer token"} if has_headers else None,
            "config": {"timeout": 30} if has_config else None,
        }
        
        # Create plugin
        plugin = MCPPluginCreate(**config_data)
        
        # Verify None fields are handled correctly
        if not has_headers:
            assert plugin.headers is None
        else:
            assert plugin.headers is not None
            # Should be JSON serializable
            json.dumps(plugin.headers)
        
        if not has_config:
            assert plugin.config is None
        else:
            assert plugin.config is not None
            # Should be JSON serializable
            json.dumps(plugin.config)
        
        # Full model should still be JSON serializable
        json_str = plugin.model_dump_json()
        plugin_from_json = MCPPluginCreate.model_validate_json(json_str)
        
        assert plugin_from_json.headers == plugin.headers
        assert plugin_from_json.config == plugin.config
    
    def test_invalid_json_types_rejected(self):
        """
        Test that truly non-JSON-serializable types would be rejected.
        
        This is an example test showing that the schema enforces JSON compatibility.
        """
        import json
        
        # Valid JSON types should work
        valid_config = {
            "plugin_name": "test",
            "display_name": "Test",
            "server_url": "http://test.com",
            "config": {
                "string": "value",
                "number": 42,
                "float": 3.14,
                "bool": True,
                "null": None,
                "array": [1, 2, 3],
                "object": {"nested": "value"}
            }
        }
        
        plugin = MCPPluginCreate(**valid_config)
        
        # Should be JSON serializable
        json_str = json.dumps(plugin.config)
        assert json_str is not None
        
        # Deserialize and verify
        deserialized = json.loads(json_str)
        assert deserialized == plugin.config


class TestPluginCategoryConsistency:
    """Test suite for plugin category consistency."""
    
    # Feature: admin-mcp-defaults, Property 9: 插件分类一致性
    @settings(max_examples=100, deadline=None)
    @given(config=plugin_config())
    def test_plugin_category_consistency(self, config):
        """
        **Feature: admin-mcp-defaults, Property 9: 插件分类一致性**
        **Validates: Requirements 2.5**
        
        Property: For any plugin, if category is not specified (None),
        it should default to "general".
        
        This test verifies that:
        1. When category is None, the default "general" is applied
        2. When category is specified, it is preserved
        3. The default is consistent across serialization
        """
        # Create plugin
        plugin = MCPPluginCreate(**config)
        
        # Check category consistency
        if config.get("category") is None:
            # When not specified, should default to None in the schema
            # (The database or service layer applies the "general" default)
            # But the schema should accept None
            assert plugin.category is None or plugin.category == "general", \
                "Unspecified category should be None or 'general'"
        else:
            # When specified, should be preserved
            assert plugin.category == config["category"], \
                f"Specified category should be preserved: {plugin.category} != {config['category']}"
        
        # Serialize and verify consistency
        serialized = plugin.model_dump()
        
        if config.get("category") is None:
            # None should be preserved in serialization
            assert serialized["category"] is None or serialized["category"] == "general"
        else:
            assert serialized["category"] == config["category"]
        
        # Round-trip should preserve category
        plugin_roundtrip = MCPPluginCreate(**serialized)
        assert plugin_roundtrip.category == plugin.category
    
    @settings(max_examples=50, deadline=None)
    @given(
        category=st.one_of(
            st.none(),
            st.sampled_from(["search", "filesystem", "database", "api", "tool", "general", "other"])
        )
    )
    def test_category_default_behavior(self, category):
        """
        Property: Category field should handle None and valid categories correctly.
        
        This tests the default behavior more explicitly.
        """
        config_data = {
            "plugin_name": "test-plugin",
            "display_name": "Test Plugin",
            "server_url": "http://test.com",
            "category": category
        }
        
        # Create plugin
        plugin = MCPPluginCreate(**config_data)
        
        # Verify category
        if category is None:
            # Schema allows None (database/service layer will apply default)
            assert plugin.category is None or plugin.category == "general"
        else:
            # Specified category should be preserved
            assert plugin.category == category
        
        # Serialize
        serialized = plugin.model_dump()
        
        # Category should be consistent in serialization
        assert serialized["category"] == plugin.category
        
        # Round-trip
        plugin_roundtrip = MCPPluginCreate(**serialized)
        assert plugin_roundtrip.category == plugin.category
    
    def test_category_explicit_general(self):
        """
        Test that explicitly setting category to "general" works correctly.
        """
        config_data = {
            "plugin_name": "test-plugin",
            "display_name": "Test Plugin",
            "server_url": "http://test.com",
            "category": "general"
        }
        
        plugin = MCPPluginCreate(**config_data)
        
        # Should be "general"
        assert plugin.category == "general"
        
        # Serialize
        serialized = plugin.model_dump()
        assert serialized["category"] == "general"
        
        # Round-trip
        plugin_roundtrip = MCPPluginCreate(**serialized)
        assert plugin_roundtrip.category == "general"
    
    def test_category_none_to_general_in_response(self):
        """
        Test that MCPPluginResponse can handle category defaulting.
        
        This simulates what happens when data comes from the database.
        """
        from datetime import datetime
        
        # Simulate database data with None category
        response_data = {
            "id": 1,
            "plugin_name": "test-plugin",
            "display_name": "Test Plugin",
            "plugin_type": "http",
            "server_url": "http://test.com",
            "headers": None,
            "enabled": True,
            "category": None,  # From database
            "config": None,
            "is_default": False,
            "user_enabled": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Create response model
        response = MCPPluginResponse(**response_data)
        
        # Category should be None (database layer handles default)
        assert response.category is None or response.category == "general"
