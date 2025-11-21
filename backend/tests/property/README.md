# Property-Based Tests for MCP Plugin System

This directory contains property-based tests for the MCP (Model Context Protocol) plugin system using the Hypothesis library.

## Overview

Property-based testing verifies that universal properties hold across many randomly generated inputs, providing stronger correctness guarantees than example-based tests alone.

## Test Configuration

- **Library**: Hypothesis (https://hypothesis.readthedocs.io/)
- **Minimum iterations per property**: 100
- **Test runner**: pytest with pytest-asyncio

## Running Tests

```bash
# Run all property tests
python -m pytest tests/property/ -v

# Run specific test file
python -m pytest tests/property/test_mcp_http_client.py -v

# Run with coverage
python -m pytest tests/property/ --cov=app.mcp --cov-report=html
```

## Test Files

### test_llm_service_mcp.py

Tests for LLM Service MCP integration and graceful degradation behavior.

**Property 19: Graceful Degradation**
- **Validates**: Requirements 5.5
- **Description**: For any user request with MCP tools enabled, if all tool calls fail or any part of the MCP integration fails, the system should gracefully degrade to normal generation mode and still produce a response without raising an exception.

**Test Coverage**:
1. `test_graceful_degradation_all_tools_fail` - Property-based test with 30 random scenarios
   - Tests behavior when all tool calls fail
   - Verifies fallback to normal generation
   - Ensures no exceptions are raised
   
2. `test_graceful_degradation_no_mcp_service` - Property-based test with 30 random scenarios
   - Tests behavior when MCP service is not initialized
   - Verifies immediate fallback to normal generation
   
3. `test_graceful_degradation_tool_fetch_fails` - Property-based test with 30 random scenarios
   - Tests behavior when fetching tools fails
   - Verifies graceful error handling
   
4. `test_graceful_degradation_no_tools_enabled` - Property-based test with 30 random scenarios
   - Tests behavior when no tools are enabled for user
   - Verifies normal generation is used
   
5. `test_graceful_degradation_first_llm_call_fails` - Property-based test with 30 random scenarios
   - Tests behavior when first LLM call (with tools) fails
   - Verifies fallback to normal generation
   
6. `test_graceful_degradation_tool_execution_fails` - Property-based test with 30 random scenarios
   - Tests behavior when tool execution throws exception
   - Verifies graceful error handling and fallback
   
7. `test_successful_tool_call_no_degradation` - Example test
   - Tests that successful tool calls don't trigger degradation
   - Verifies normal flow with tool results
   
8. `test_partial_tool_success_no_degradation` - Example test
   - Tests that partial tool success doesn't trigger degradation
   - Verifies system continues with available results

### test_mcp_schemas.py

Tests for MCP Plugin Pydantic schemas serialization and deserialization.

**Property 1: Plugin Configuration Round-Trip**
- **Validates**: Requirements 1.2
- **Description**: For any valid plugin configuration, storing it to the database and then retrieving it should return an equivalent configuration with all fields preserved.

**Test Coverage**:
1. `test_plugin_create_round_trip` - Property-based test with 100 random configurations
   - Tests MCPPluginCreate schema round-trip
   - Verifies all fields are preserved
   - Validates optional fields handling
   
2. `test_plugin_base_round_trip` - Property-based test with 100 random configurations
   - Tests MCPPluginBase schema round-trip
   - Ensures base schema preserves all fields
   
3. `test_plugin_update_round_trip` - Property-based test with 100 random partial updates
   - Tests MCPPluginUpdate schema with optional fields
   - Validates partial update scenarios
   
4. `test_plugin_json_round_trip` - Property-based test with 100 random configurations
   - Tests JSON serialization/deserialization
   - Verifies JSON string conversion preserves data
   
5. `test_plugin_create_with_defaults` - Example test
   - Tests default value application
   
6. `test_plugin_update_empty` - Example test
   - Tests empty update scenario
   
7. `test_plugin_config_with_complex_nested_data` - Example test
   - Tests complex nested configuration data

### test_mcp_http_client.py

Tests for HTTP MCP Client error state recovery and reconnection mechanisms.

**Property 21: Error State Recovery**
- **Validates**: Requirements 12.4
- **Description**: For any session marked as error status due to connection failure, the next request should attempt to reconnect and restore the session to active status.

**Test Coverage**:
1. `test_error_state_recovery` - Property-based test with 100 random scenarios
   - Tests connection failures and recovery
   - Verifies proper error handling
   - Validates reconnection logic
   
2. `test_reconnection_after_network_interruption` - Example test
   - Simulates network interruption
   - Verifies successful reconnection
   
3. `test_multiple_reconnection_attempts` - Example test
   - Tests multiple failed attempts followed by success
   - Validates retry behavior

## Test Strategies

The tests use Hypothesis strategies to generate random test data:

- **connection_scenario**: Generates random server URLs, headers, and failure/recovery scenarios
- Covers various combinations of initial failures and recovery attempts
- Tests both successful and failed connection scenarios

## Implementation Notes

- All tests use mocking to avoid requiring actual MCP servers
- Tests verify both the happy path and error conditions
- Each property test is tagged with its design document reference
- Tests follow the format: `# Feature: mcp-plugin-system, Property X: <description>`

## Adding New Property Tests

When adding new property tests:

1. Reference the property number from the design document
2. Add the validation comment: `**Feature: mcp-plugin-system, Property X: <name>**`
3. Include the requirements validation: `**Validates: Requirements X.Y**`
4. Configure Hypothesis with `@settings(max_examples=100, deadline=None)`
5. Use appropriate Hypothesis strategies for input generation
6. Verify the property holds across all generated inputs
