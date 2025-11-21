-- Rollback Migration: Remove Default Plugin Support (PostgreSQL)
-- Date: 2024-01-XX
-- Description: Removes user_id field from mcp_plugins table and restores original schema

-- WARNING: This rollback will delete all user-specific plugins (where user_id IS NOT NULL)
-- Only default plugins (user_id IS NULL) will be preserved

-- Step 1: Delete all user-specific plugins
DELETE FROM mcp_plugins WHERE user_id IS NOT NULL;

-- Step 2: Drop composite unique constraint
ALTER TABLE mcp_plugins
DROP CONSTRAINT IF EXISTS uq_user_plugin_name;

-- Step 3: Drop foreign key constraint
ALTER TABLE mcp_plugins
DROP CONSTRAINT IF EXISTS fk_mcp_plugins_user;

-- Step 4: Drop index on user_id
DROP INDEX IF EXISTS idx_mcp_plugins_user;

-- Step 5: Drop user_id column
ALTER TABLE mcp_plugins
DROP COLUMN IF EXISTS user_id;

-- Step 6: Restore original unique constraint on plugin_name
ALTER TABLE mcp_plugins
ADD CONSTRAINT mcp_plugins_plugin_name_key UNIQUE (plugin_name);

-- Note: After rollback, all remaining plugins will be treated as global plugins
-- User-specific plugins will be permanently deleted
