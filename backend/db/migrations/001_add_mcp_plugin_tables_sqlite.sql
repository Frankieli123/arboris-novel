-- Migration: Add MCP Plugin System Tables (SQLite)
-- Date: 2024-01-XX
-- Description: Adds mcp_plugins and user_plugin_preferences tables for MCP plugin system

-- Create mcp_plugins table
CREATE TABLE IF NOT EXISTS mcp_plugins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    plugin_type VARCHAR(50) NOT NULL DEFAULT 'http',
    server_url VARCHAR(500) NOT NULL,
    headers TEXT NULL,  -- JSON string for HTTP headers
    enabled INTEGER NOT NULL DEFAULT 1,  -- SQLite uses INTEGER for boolean
    category VARCHAR(50) NULL,
    config TEXT NULL,  -- JSON string for additional configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on plugin_name
CREATE INDEX IF NOT EXISTS idx_plugin_name ON mcp_plugins(plugin_name);

-- Create user_plugin_preferences table
CREATE TABLE IF NOT EXISTS user_plugin_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plugin_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,  -- SQLite uses INTEGER for boolean
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plugin_id) REFERENCES mcp_plugins(id) ON DELETE CASCADE,
    UNIQUE(user_id, plugin_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_plugin_prefs_user ON user_plugin_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_plugin_prefs_plugin ON user_plugin_preferences(plugin_id);

-- Note: SQLite doesn't support triggers for ON UPDATE CURRENT_TIMESTAMP
-- You may need to handle updated_at in application code or use triggers:

-- Trigger for mcp_plugins updated_at
CREATE TRIGGER IF NOT EXISTS update_mcp_plugins_timestamp 
AFTER UPDATE ON mcp_plugins
BEGIN
    UPDATE mcp_plugins SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger for user_plugin_preferences updated_at
CREATE TRIGGER IF NOT EXISTS update_user_plugin_prefs_timestamp 
AFTER UPDATE ON user_plugin_preferences
BEGIN
    UPDATE user_plugin_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
