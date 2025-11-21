-- Rollback Migration: Remove MCP Plugin System Tables
-- Date: 2024-01-XX
-- Description: Removes mcp_plugins and user_plugin_preferences tables

-- Drop user_plugin_preferences table first (due to foreign key constraint)
DROP TABLE IF EXISTS user_plugin_preferences;

-- Drop mcp_plugins table
DROP TABLE IF EXISTS mcp_plugins;
