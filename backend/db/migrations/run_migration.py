#!/usr/bin/env python3
"""
数据库迁移脚本 - 添加 user_id 字段支持默认插件
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine


async def run_migration():
    """运行数据库迁移"""
    
    print("=" * 60)
    print("开始数据库迁移：添加 user_id 字段支持")
    print("=" * 60)
    print(f"数据库类型: {settings.db_provider}")
    print(f"数据库连接: {settings.sqlalchemy_database_uri.split('@')[-1] if '@' in settings.sqlalchemy_database_uri else settings.sqlalchemy_database_uri}")
    print()
    
    try:
        async with engine.begin() as conn:
            # 检查 user_id 字段是否已存在
            if settings.db_provider == "mysql":
                result = await conn.execute(text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'mcp_plugins' 
                    AND COLUMN_NAME = 'user_id'
                """))
                exists = result.scalar() > 0
            elif settings.db_provider == "sqlite":
                result = await conn.execute(text("PRAGMA table_info(mcp_plugins)"))
                columns = [row[1] for row in result.fetchall()]
                exists = 'user_id' in columns
            else:  # PostgreSQL
                result = await conn.execute(text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.columns 
                    WHERE table_name = 'mcp_plugins' 
                    AND column_name = 'user_id'
                """))
                exists = result.scalar() > 0
            
            if exists:
                print("✓ user_id 字段已存在，无需迁移")
                return
            
            print("✗ user_id 字段不存在，开始迁移...")
            print()
            
            # 根据数据库类型执行不同的迁移脚本
            if settings.db_provider == "mysql":
                print("执行 MySQL 迁移...")
                await run_mysql_migration(conn)
            elif settings.db_provider == "sqlite":
                print("执行 SQLite 迁移...")
                await run_sqlite_migration(conn)
            else:  # PostgreSQL
                print("执行 PostgreSQL 迁移...")
                await run_postgresql_migration(conn)
            
            print()
            print("=" * 60)
            print("✓ 迁移完成！")
            print("=" * 60)
            
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ 迁移失败！")
        print("=" * 60)
        print(f"错误信息: {e}")
        raise


async def run_mysql_migration(conn):
    """MySQL 迁移"""
    
    # Step 1: Add user_id column
    print("1. 添加 user_id 字段...")
    await conn.execute(text("""
        ALTER TABLE mcp_plugins 
        ADD COLUMN user_id INT NULL AFTER id
    """))
    
    # Step 2: Add foreign key
    print("2. 添加外键约束...")
    await conn.execute(text("""
        ALTER TABLE mcp_plugins
        ADD CONSTRAINT fk_mcp_plugins_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    """))
    
    # Step 3: Create index
    print("3. 创建索引...")
    await conn.execute(text("""
        CREATE INDEX idx_mcp_plugins_user ON mcp_plugins(user_id)
    """))
    
    # Step 4: Drop old unique constraint if exists
    print("4. 删除旧的唯一约束...")
    try:
        await conn.execute(text("""
            ALTER TABLE mcp_plugins DROP INDEX plugin_name
        """))
    except:
        pass  # 约束可能不存在
    
    # Step 5: Add composite unique constraint
    print("5. 添加复合唯一约束...")
    await conn.execute(text("""
        ALTER TABLE mcp_plugins
        ADD CONSTRAINT uq_user_plugin_name UNIQUE (user_id, plugin_name)
    """))
    
    # Step 6: Update category
    print("6. 更新分类默认值...")
    await conn.execute(text("""
        UPDATE mcp_plugins 
        SET category = 'general' 
        WHERE category IS NULL
    """))
    
    print("✓ MySQL 迁移完成")


async def run_sqlite_migration(conn):
    """SQLite 迁移（需要重建表）"""
    
    print("注意: SQLite 需要重建表来添加外键约束")
    
    # Step 1: Create new table
    print("1. 创建新表...")
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS mcp_plugins_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NULL,
            plugin_name VARCHAR(100) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            plugin_type VARCHAR(50) NOT NULL DEFAULT 'http',
            server_url VARCHAR(500) NOT NULL,
            headers TEXT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            category VARCHAR(50) NULL DEFAULT 'general',
            config TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, plugin_name)
        )
    """))
    
    # Step 2: Copy data
    print("2. 复制数据...")
    await conn.execute(text("""
        INSERT INTO mcp_plugins_new (
            id, user_id, plugin_name, display_name, plugin_type, 
            server_url, headers, enabled, category, config, 
            created_at, updated_at
        )
        SELECT 
            id, NULL as user_id, plugin_name, display_name, plugin_type,
            server_url, headers, enabled, category, config,
            created_at, updated_at
        FROM mcp_plugins
    """))
    
    # Step 3: Drop old table
    print("3. 删除旧表...")
    await conn.execute(text("DROP TABLE mcp_plugins"))
    
    # Step 4: Rename new table
    print("4. 重命名新表...")
    await conn.execute(text("ALTER TABLE mcp_plugins_new RENAME TO mcp_plugins"))
    
    # Step 5: Create indexes
    print("5. 创建索引...")
    await conn.execute(text("CREATE INDEX idx_mcp_plugins_user ON mcp_plugins(user_id)"))
    await conn.execute(text("CREATE INDEX idx_mcp_plugins_name ON mcp_plugins(plugin_name)"))
    
    print("✓ SQLite 迁移完成")


async def run_postgresql_migration(conn):
    """PostgreSQL 迁移"""
    
    # Step 1: Add user_id column
    print("1. 添加 user_id 字段...")
    await conn.execute(text("""
        ALTER TABLE mcp_plugins 
        ADD COLUMN IF NOT EXISTS user_id INTEGER NULL
    """))
    
    # Step 2: Add foreign key
    print("2. 添加外键约束...")
    await conn.execute(text("""
        ALTER TABLE mcp_plugins
        ADD CONSTRAINT fk_mcp_plugins_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    """))
    
    # Step 3: Create index
    print("3. 创建索引...")
    await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_mcp_plugins_user ON mcp_plugins(user_id)
    """))
    
    # Step 4: Drop old unique constraint
    print("4. 删除旧的唯一约束...")
    try:
        await conn.execute(text("""
            ALTER TABLE mcp_plugins
            DROP CONSTRAINT IF EXISTS mcp_plugins_plugin_name_key
        """))
    except:
        pass
    
    # Step 5: Add composite unique constraint
    print("5. 添加复合唯一约束...")
    await conn.execute(text("""
        ALTER TABLE mcp_plugins
        ADD CONSTRAINT uq_user_plugin_name UNIQUE (user_id, plugin_name)
    """))
    
    # Step 6: Update category
    print("6. 更新分类默认值...")
    await conn.execute(text("""
        UPDATE mcp_plugins 
        SET category = 'general' 
        WHERE category IS NULL
    """))
    
    print("✓ PostgreSQL 迁移完成")


if __name__ == "__main__":
    asyncio.run(run_migration())
