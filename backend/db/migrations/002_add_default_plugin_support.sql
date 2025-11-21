-- Migration: Add Default Plugin Support (PostgreSQL)
-- Date: 2024-01-XX
-- Description: Adds user_id field to mcp_plugins table to support default plugins
--              user_id = NULL indicates a default plugin (available to all users)
--              user_id = specific ID indicates a user-specific plugin

-- Step 1: Add user_id column (nullable)
ALTER TABLE mcp_plugins 
ADD COLUMN IF NOT EXISTS user_id INTEGER NULL;

-- Step 2: Add foreign key constraint
ALTER TABLE mcp_plugins
ADD CONSTRAINT fk_mcp_plugins_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Step 3: Create index on user_id
CREATE INDEX IF NOT EXISTS idx_mcp_plugins_user ON mcp_plugins(user_id);

-- Step 4: Drop old unique constraint on plugin_name
ALTER TABLE mcp_plugins
DROP CONSTRAINT IF EXISTS mcp_plugins_plugin_name_key;

-- Step 5: Add new composite unique constraint
-- This ensures:
-- - Default plugins (user_id = NULL) have unique plugin_name globally
-- - User plugins have unique (user_id, plugin_name) combination
ALTER TABLE mcp_plugins
ADD CONSTRAINT uq_user_plugin_name UNIQUE (user_id, plugin_name);

-- Step 6: Update category default value if not already set
UPDATE mcp_plugins 
SET category = 'general' 
WHERE category IS NULL;

-- Step 7: Set default for category column
ALTER TABLE mcp_plugins
ALTER COLUMN category SET DEFAULT 'general';

-- Step 8: Create partial unique index for default plugins
-- This ensures default plugins (user_id IS NULL) have unique plugin_names
-- PostgreSQL supports partial indexes with WHERE clause
CREATE UNIQUE INDEX IF NOT EXISTS idx_default_plugin_unique_name 
ON mcp_plugins(plugin_name) WHERE user_id IS NULL;

-- Note: This migration converts all existing plugins to default plugins (user_id = NULL)
-- All existing plugins will be available to all users
-- If you need to assign existing plugins to specific users, run additional UPDATE statements
