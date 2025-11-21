# MCP Plugin Data Models - Implementation Notes

## Overview

This document describes the implementation of the MCP Plugin data models for the Arboris Novel AI platform.

## Models Created

### 1. MCPPlugin Model
**File**: `backend/app/models/mcp_plugin.py`

Stores MCP plugin configuration including:
- `plugin_name`: Unique identifier for the plugin
- `display_name`: Human-readable name
- `plugin_type`: Type of plugin (default: "http")
- `server_url`: URL of the MCP server
- `headers`: JSON string for authentication headers
- `enabled`: Global enable/disable flag
- `category`: Optional categorization
- `config`: Additional JSON configuration
- Timestamps: `created_at`, `updated_at`

**Relationships**:
- One-to-many with `UserPluginPreference`

### 2. UserPluginPreference Model
**File**: `backend/app/models/mcp_plugin.py`

Stores user-level plugin preferences:
- `user_id`: Foreign key to users table
- `plugin_id`: Foreign key to mcp_plugins table
- `enabled`: User-specific enable/disable flag
- Timestamps: `created_at`, `updated_at`

**Constraints**:
- Unique constraint on (user_id, plugin_id) pair
- Cascade delete when user or plugin is deleted

**Relationships**:
- Many-to-one with `User`
- Many-to-one with `MCPPlugin`

## Database Schema

### Tables Created

1. **mcp_plugins**
   - Primary key: `id` (INT AUTO_INCREMENT)
   - Unique index on `plugin_name`
   - Stores plugin configuration

2. **user_plugin_preferences**
   - Primary key: `id` (INT AUTO_INCREMENT)
   - Foreign keys: `user_id`, `plugin_id`
   - Unique constraint: (user_id, plugin_id)
   - Indexes on both foreign keys for performance

## Migration Files

### Forward Migration
**File**: `backend/db/migrations/001_add_mcp_plugin_tables.sql`

Creates both tables with proper constraints and indexes.

### Rollback Migration
**File**: `backend/db/migrations/001_add_mcp_plugin_tables_rollback.sql`

Drops both tables in correct order (user_plugin_preferences first due to FK).

## Integration

### Updated Files

1. **backend/app/models/__init__.py**
   - Added imports for `MCPPlugin` and `UserPluginPreference`
   - Exported in `__all__` list

2. **backend/app/models/user.py**
   - Added `plugin_preferences` relationship to User model

3. **backend/db/schema.sql**
   - Added table definitions for new installations

## Usage Example

```python
from backend.app.models import MCPPlugin, UserPluginPreference, User

# Create a plugin
plugin = MCPPlugin(
    plugin_name="exa_search",
    display_name="Exa Search",
    server_url="https://mcp.exa.ai",
    headers='{"Authorization": "Bearer token"}',
    enabled=True,
    category="search"
)

# Enable plugin for a user
preference = UserPluginPreference(
    user_id=user.id,
    plugin_id=plugin.id,
    enabled=True
)
```

## Testing

Models have been verified to:
- Import correctly without errors
- Follow SQLAlchemy 2.0 Mapped type annotations
- Match the project's existing model patterns
- Include proper relationships and constraints

## Next Steps

After applying the migration:
1. Implement Repository layer (Task 3)
2. Implement Service layer (Task 6)
3. Implement API endpoints (Task 8)
