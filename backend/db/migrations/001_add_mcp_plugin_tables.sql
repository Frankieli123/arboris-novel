-- Migration: Add MCP Plugin System Tables
-- Date: 2024-01-XX
-- Description: Adds mcp_plugins and user_plugin_preferences tables for MCP plugin system

-- Create mcp_plugins table
CREATE TABLE IF NOT EXISTS mcp_plugins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plugin_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    plugin_type VARCHAR(50) NOT NULL DEFAULT 'http',
    server_url VARCHAR(500) NOT NULL,
    headers TEXT NULL COMMENT 'JSON string for HTTP headers',
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    category VARCHAR(50) NULL,
    config TEXT NULL COMMENT 'JSON string for additional configuration',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_plugin_name (plugin_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create user_plugin_preferences table
CREATE TABLE IF NOT EXISTS user_plugin_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    plugin_id INT NOT NULL,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_plugin_prefs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_plugin_prefs_plugin FOREIGN KEY (plugin_id) REFERENCES mcp_plugins(id) ON DELETE CASCADE,
    UNIQUE KEY uq_user_plugin (user_id, plugin_id),
    INDEX idx_user_plugin_prefs_user (user_id),
    INDEX idx_user_plugin_prefs_plugin (plugin_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
