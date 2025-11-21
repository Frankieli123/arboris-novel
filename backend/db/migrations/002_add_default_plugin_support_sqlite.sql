-- Migration: Add Default Plugin Support (SQLite)
-- Date: 2024-01-XX
-- Description: Adds user_id field to mcp_plugins table to support default plugins
--              user_id = NULL indicates a default plugin (available to all users)
--              user_id = specific ID indicates a user-specific plugin

-- Step 1: Create new table with updated schema
CREATE TABLE IF NOT EXISTS mcp_plugins_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NULL,  -- NULL for default plugins, specific ID for user plugins
    plugin_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    plugin_type VARCHAR(50) NOT NULL DEFAULT 'http',
    server_url VARCHAR(500) NOT NULL,
    headers TEXT NULL,  -- JSON string for HTTP headers
    enabled INTEGER NOT NULL DEFAULT 1,  -- SQLite uses INTEGER for boolean
    category VARCHAR(50) NULL DEFAULT 'general',
    config TEXT NULL,  -- JSON string for additional configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, plugin_name)  -- Composite unique constraint
);

-- Step 2: Copy data from old table to new table
-- All existing plugins become default plugins (user_id = NULL)
INSERT INTO mcp_plugins_new (
    id, user_id, plugin_name, display_name, plugin_type, 
    server_url, headers, enabled, category, config, 
    created_at, updated_at
)
SELECT 
    id, NULL as user_id, plugin_name, display_name, plugin_type,
    server_url, headers, enabled, category, config,
    created_at, updated_at
FROM mcp_plugins;

-- Step 3: Drop old table
DROP TABLE mcp_plugins;

-- Step 4: Rename new table to original name
ALTER TABLE mcp_plugins_new RENAME TO mcp_plugins;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_mcp_plugins_user ON mcp_plugins(user_id);
CREATE INDEX IF NOT EXISTS idx_mcp_plugins_name ON mcp_plugins(plugin_name);
CREATE INDEX IF NOT EXISTS idx_mcp_plugins_enabled ON mcp_plugins(enabled);
CREATE INDEX IF NOT EXISTS idx_mcp_plugins_category ON mcp_plugins(category);

-- Step 5.1: Create partial unique index for default plugins
-- This ensures default plugins (user_id IS NULL) have unique plugin_names
CREATE UNIQUE INDEX IF NOT EXISTS idx_default_plugin_unique_name 
ON mcp_plugins(plugin_name) WHERE user_id IS NULL;

-- Step 6: Recreate triggers for updated_at
CREATE TRIGGER IF NOT EXISTS update_mcp_plugins_timestamp 
AFTER UPDATE ON mcp_plugins
BEGIN
    UPDATE mcp_plugins SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Note: This migration converts all existing plugins to default plugins (user_id = NULL)
-- If you need to assign existing plugins to specific users, run additional UPDATE statements
