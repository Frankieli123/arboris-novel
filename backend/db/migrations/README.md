# Database Migrations

This directory contains SQL migration scripts for the Arboris Novel AI platform.

## Migration Files

Each migration consists of two files:
- `XXX_migration_name.sql` - The forward migration (upgrade)
- `XXX_migration_name_rollback.sql` - The rollback migration (downgrade)

## How to Apply Migrations

### Using MySQL CLI

```bash
# Apply migration
mysql -u username -p database_name < backend/db/migrations/001_add_mcp_plugin_tables.sql

# Rollback migration
mysql -u username -p database_name < backend/db/migrations/001_add_mcp_plugin_tables_rollback.sql
```

### Using Docker

```bash
# Apply migration
docker exec -i mysql_container mysql -u username -p database_name < backend/db/migrations/001_add_mcp_plugin_tables.sql

# Rollback migration
docker exec -i mysql_container mysql -u username -p database_name < backend/db/migrations/001_add_mcp_plugin_tables_rollback.sql
```

## Migration List

| ID  | Name | Description | Date |
|-----|------|-------------|------|
| 001 | add_mcp_plugin_tables | Adds MCP plugin system tables (mcp_plugins, user_plugin_preferences) | 2024-01-XX |

## Testing Migrations

Before applying to production:

1. **Test on a copy of production data**
2. **Verify the migration applies cleanly**
3. **Test the rollback**
4. **Verify application functionality**

## Notes

- Always backup your database before applying migrations
- Test migrations in a development environment first
- Keep migration files in version control
- Document any manual steps required
